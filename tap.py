"""mitmproxy addon: live prompt-cache inspector for LLM calls.

Captures every POST to */messages, */responses or */chat/completions that goes
through the proxy, and serves a live dashboard on http://127.0.0.1:8900.

Privacy: request headers are never read or stored (that is where the auth token
lives). Request bodies are kept in memory only (last MAX requests) so the UI can
show them; data/requests.jsonl only stores metrics.
"""

import logging
import re
import sys

import mitmproxy.addonmanager
import mitmproxy.http

if __name__.startswith("__mitmproxy_script__"):
    # mitmproxy re-executes this file on save; dropping cachetap modules reloads submodules too.
    for _name in [m for m in sys.modules if m == "cachetap" or m.startswith("cachetap.")]:
        del sys.modules[_name]

from cachetap import (  # noqa: E402  # mitmproxy reloads cachetap modules above before this import.
    capture,
    config,
    dashboard,
    request_body,
    store,
)

logger = logging.getLogger(__name__)


LLM_PATHS = ("/messages", "/responses", "/chat/completions")
SAFE_HEADER = re.compile(
    r"request-id|region|geo|served|backend|azure|ratelimit|quota|processing|x-cache|via$", re.I
)
UNSAFE_HEADER = re.compile(r"token|auth|cookie|secret|key", re.I)

# ---------- mitmproxy hooks ----------


def _is_llm(flow: mitmproxy.http.HTTPFlow) -> bool:
    return flow.request.method == "POST" and flow.request.path.split("?")[0].rstrip("/").endswith(
        LLM_PATHS
    )


def request(flow: mitmproxy.http.HTTPFlow) -> None:
    if not _is_llm(flow):
        return
    # the stream hook below sees raw bytes, so ask for an uncompressed response
    flow.request.headers["accept-encoding"] = "identity"
    if len(flow.request.raw_content or b"") > config.MAX_REQUEST_BYTES:
        logger.warning("Petición no inspeccionable: límite de tamaño de petición")
        return
    text = flow.request.get_text(strict=False) or ""
    try:
        req = request_body.parse(text)
    except ValueError as exc:
        logger.warning("Petición no inspeccionable: %s", exc)
        return
    rid = capture.begin(
        req,
        text,
        flow.request.pretty_host,
        flow.request.path.split("?")[0],
        len(flow.request.raw_content or b""),
        flow.request.timestamp_start,
    )
    flow.metadata["tap_id"] = rid


def responseheaders(flow: mitmproxy.http.HTTPFlow) -> None:
    rid = flow.metadata.get("tap_id")
    if rid is None or flow.response is None:
        return
    response_headers = {
        k: v
        for k, v in flow.response.headers.items()
        if SAFE_HEADER.search(k) and not UNSAFE_HEADER.search(k)
    }
    st = capture.start(
        rid,
        flow.response.status_code,
        response_headers,
        flow.request.timestamp_end,
        flow.response.timestamp_start,
    )
    flow.metadata["tap_stream"] = st

    def stream(data: bytes) -> bytes:
        return capture.feed(rid, st, data)

    flow.response.stream = stream


def response(flow: mitmproxy.http.HTTPFlow) -> None:
    rid = flow.metadata.get("tap_id")
    st = flow.metadata.get("tap_stream")
    if rid is None or st is None or flow.response is None:
        return
    try:
        capture.finish(
            rid,
            st,
            flow.response.status_code,
            flow.request.timestamp_end,
            logger,
        )
    finally:
        flow.metadata.pop("tap_stream", None)


def error(flow: mitmproxy.http.HTTPFlow) -> None:
    rid = flow.metadata.get("tap_id")
    if rid is None:
        return
    st = flow.metadata.pop("tap_stream", None)
    capture.fail(rid, st, str(flow.error))


def load(loader: mitmproxy.addonmanager.Loader) -> None:
    dashboard.start()
    logger.info("Panel disponible en http://127.0.0.1:%s", config.UI_PORT)


def done() -> None:
    dashboard.stop()
    with store.LOCK:
        store.ACTIVE_CAPTURES.clear()
