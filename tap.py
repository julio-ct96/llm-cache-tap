"""mitmproxy addon: live prompt-cache inspector for LLM calls.

Captures every POST to */messages, */responses or */chat/completions that goes
through the proxy, and serves a live dashboard on http://127.0.0.1:8900.

Privacy: request headers are never read or stored (that is where the auth token
lives). Request bodies are kept in memory only (last MAX requests) so the UI can
show them; data/requests.jsonl only stores metrics.
"""

import logging
import math
import re
import sys

import mitmproxy.addonmanager
import mitmproxy.http
import mitmproxy.websocket

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
    websocket,
)

logger = logging.getLogger(__name__)
SOCKETS: dict[str, websocket.Session] = {}


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
    flow_id = getattr(flow, "id", None)
    session = SOCKETS.pop(flow_id, None) if isinstance(flow_id, str) else None
    try:
        rid = flow.metadata.get("tap_id")
        if rid is None:
            return
        st = flow.metadata.pop("tap_stream", None)
        capture.fail(rid, st, str(flow.error))
    finally:
        if session is not None:
            session.close(_websocket_end_at(flow))


def _is_copilot_host(host: object) -> bool:
    if not isinstance(host, str) or not host or len(host) > 254:
        return False
    normalized = host[:-1] if host.endswith(".") else host
    if not normalized or len(normalized) > 253:
        return False
    labels = normalized.split(".")
    if any(
        not label
        or len(label) > 63
        or not label.isascii()
        or not label[0].isalnum()
        or not label[-1].isalnum()
        or any(not (char.isalnum() or char == "-") for char in label)
        for label in labels
    ):
        return False
    normalized = normalized.lower()
    return normalized == "githubcopilot.com" or normalized.endswith(".githubcopilot.com")


def _websocket_target(flow: mitmproxy.http.HTTPFlow) -> tuple[str, str] | None:
    request = flow.request
    response = flow.response
    if (
        not isinstance(request, mitmproxy.http.Request)
        or not isinstance(response, mitmproxy.http.Response)
        or not isinstance(flow.websocket, mitmproxy.websocket.WebSocketData)
    ):
        return None
    if (
        request.method != "GET"
        or type(response.status_code) is not int
        or response.status_code != 101
    ):
        return None

    host = request.pretty_host
    path = request.path
    if not _is_copilot_host(host) or not isinstance(path, str):
        return None
    stored_path = path.split("?", 1)[0]
    comparison_path = stored_path.rstrip("/")
    if comparison_path not in {"/responses", "/v1/responses"}:
        return None
    canonical_host = host.lower()
    if canonical_host.endswith("."):
        canonical_host = canonical_host[:-1]
    return canonical_host, stored_path


def _valid_timestamp(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        timestamp = float(value)
    except OverflowError:
        return None
    return timestamp if math.isfinite(timestamp) else None


def _websocket_end_at(flow: mitmproxy.http.HTTPFlow) -> float | None:
    data = flow.websocket
    if data is None:
        return None
    return _valid_timestamp(data.timestamp_end)


def websocket_start(flow: mitmproxy.http.HTTPFlow) -> None:
    target = _websocket_target(flow)
    if target is None or not isinstance(flow.id, str) or not flow.id:
        return
    if flow.id in SOCKETS:
        return
    host, path = target
    SOCKETS[flow.id] = websocket.Session(host, path, logger)


def websocket_message(flow: mitmproxy.http.HTTPFlow) -> None:
    flow_id = flow.id
    if not isinstance(flow_id, str):
        return
    session = SOCKETS.get(flow_id)
    if session is None or _websocket_target(flow) is None:
        return
    data = flow.websocket
    if (
        not isinstance(data, mitmproxy.websocket.WebSocketData)
        or not isinstance(data.messages, list)
        or not data.messages
    ):
        return
    message = data.messages[-1]
    if not isinstance(message, mitmproxy.websocket.WebSocketMessage):
        return
    timestamp = _valid_timestamp(message.timestamp)
    if timestamp is None:
        return
    if type(message.dropped) is not bool or type(message.injected) is not bool:
        session.uninspectable(timestamp)
        return
    if message.dropped or message.injected:
        return
    if type(message.from_client) is not bool or type(message.content) is not bytes:
        session.uninspectable(timestamp)
        return
    is_text = message.is_text
    if type(is_text) is not bool:
        session.uninspectable(timestamp)
    elif not is_text:
        session.uninspectable(timestamp)
    elif message.from_client:
        session.client(message.content, timestamp)
    else:
        session.server(message.content, timestamp)


def websocket_end(flow: mitmproxy.http.HTTPFlow) -> None:
    session = SOCKETS.pop(flow.id, None)
    if session is not None:
        session.close(_websocket_end_at(flow))


def load(loader: mitmproxy.addonmanager.Loader) -> None:
    dashboard.start()
    logger.info("Panel disponible en http://127.0.0.1:%s", config.UI_PORT)


def done() -> None:
    sessions = tuple(SOCKETS.values())
    SOCKETS.clear()
    close_error: Exception | None = None
    try:
        for session in sessions:
            try:
                session.close()
            except Exception as exc:
                if close_error is None:
                    close_error = exc
    finally:
        try:
            dashboard.stop()
        finally:
            with store.LOCK:
                store.ACTIVE_CAPTURES.clear()
    if close_error is not None:
        raise close_error
