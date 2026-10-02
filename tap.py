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
import time
from copy import deepcopy
from typing import TypedDict

import mitmproxy.addonmanager
import mitmproxy.http

if __name__.startswith("__mitmproxy_script__"):
    # mitmproxy re-executes this file on save; dropping cachetap modules reloads submodules too.
    for _name in [m for m in sys.modules if m == "cachetap" or m.startswith("cachetap.")]:
        del sys.modules[_name]

from cachetap import config, dashboard, linking, providers, record, request_body, response_body, segments, store, verdict

logger = logging.getLogger(__name__)


class StreamState(TypedDict):
    chunks: list[bytes]
    first: float | None
    bytes: int
    limited: record.CaptureLimit | None
    reserved: bool

LLM_PATHS = ("/messages", "/responses", "/chat/completions")
SAFE_HEADER = re.compile(r"request-id|region|geo|served|backend|azure|ratelimit|quota|processing|x-cache|via$", re.I)
UNSAFE_HEADER = re.compile(r"token|auth|cookie|secret|key", re.I)

# ---------- mitmproxy hooks ----------

def _is_llm(flow: mitmproxy.http.HTTPFlow) -> bool:
    return flow.request.method == "POST" and flow.request.path.split("?")[0].rstrip("/").endswith(LLM_PATHS)


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
    messages = req.get("messages") or req.get("input") or []
    n_msgs = int(bool(messages)) if isinstance(messages, str) else len(messages) if isinstance(messages, (list, dict)) else 0
    tools = req.get("tools")
    request_start = flow.request.timestamp_start
    model = req.get("model")
    with store.LOCK:
        rid = store.next_id()
        rec: record.Record = {
            "id": rid,
            "host": flow.request.pretty_host,
            "path": flow.request.path.split("?")[0],
            "model": model if isinstance(model, str) else None,
            "effort": providers.effort_of(req),
            "effort_fields": {k: req[k] for k in ("output_config", "thinking", "reasoning", "reasoning_effort", "tool_choice", "max_tokens", "max_output_tokens", "stream") if k in req},
            "_params": segments.dump({k: req.get(k) for k in ("thinking", "tool_choice")}),
            "req_bytes": len(flow.request.raw_content or b""),
            "n_tools": len(tools) if isinstance(tools, (list, dict)) else 0,
            "n_msgs": n_msgs,
            "cc_marks": text.count('"cache_control"'),
            "segs": segments.segments(req),
            "state": "pending",
        }
        if request_start is not None:
            rec["ts"] = request_start
            rec["time"] = time.strftime("%H:%M:%S", time.localtime(request_start))
        rec.update(providers.cache_ttl(req))
        linking.prepare_fingerprints(rec)
        previous, matched_message_count = linking.find_previous(rec, store.RECORDS.values())
        if previous is None:
            rec["conv"] = store.new_conv()
            rec["prev_id"] = None
        else:
            linking.link(rec, req, previous, matched_message_count, store.BODIES.get(previous["id"]))
        evicted_ids = store.add(rec, text)
        store.push(rec, evicted_ids)
    flow.metadata["tap_id"] = rid


def responseheaders(flow: mitmproxy.http.HTTPFlow) -> None:
    rid = flow.metadata.get("tap_id")
    if rid is None or flow.response is None:
        return
    with store.LOCK:
        reserved = store.begin_capture(rid)
        st: StreamState = {"chunks": [], "first": None, "bytes": 0, "limited": None, "reserved": reserved}
        if not reserved:
            st["limited"] = "active_captures"
        flow.metadata["tap_stream"] = st

        def stream(data: bytes) -> bytes:
            if data:
                if st["first"] is None and any(k in data for k in providers.FIRST_TOKEN):
                    st["first"] = time.time()
                if st["limited"] is None:
                    st["bytes"] += len(data)
                    if st["bytes"] > config.MAX_RESPONSE_BYTES:
                        st["chunks"].clear()
                        st["limited"] = "response_size"
                        if st["reserved"]:
                            with store.LOCK:
                                store.end_capture(rid)
                            st["reserved"] = False
                    else:
                        st["chunks"].append(data)
            return data

        flow.response.stream = stream
        rec = store.RECORDS.get(rid)
        if rec:
            rec["state"] = "streaming"
            rec["status"] = flow.response.status_code
            response_start = flow.response.timestamp_start
            request_end = flow.request.timestamp_end
            if response_start is not None and request_end is not None:
                rec["hdr_s"] = round(response_start - request_end, 3)
            rec["resp_headers"] = {k: v for k, v in flow.response.headers.items() if SAFE_HEADER.search(k) and not UNSAFE_HEADER.search(k)}
            store.push(rec)


def response(flow: mitmproxy.http.HTTPFlow) -> None:
    rid = flow.metadata.get("tap_id")
    st = flow.metadata.get("tap_stream")
    if rid is None or st is None or flow.response is None:
        return
    try:
        now = time.time()
        limited = st["limited"]
        body = b"".join(st["chunks"]).decode("utf8", "replace") if limited is None else ""
        events = response_body.usage_events(body) if limited is None else []
        output, stop = response_body.output_text(body) if limited is None else ("", None)
        t0 = flow.request.timestamp_end
        with store.LOCK:
            rec = store.RECORDS.get(rid)
            if not rec:
                return
            rec.update({
                "state": "done",
                "ts_end": now,
                "raw_usage": events,
                "usage": providers.normalize(events) if limited is None else None,
                "output": output if flow.response.status_code < 400 else body[:2000],
                "stop_reason": stop,
            })
            if t0 is not None:
                rec["total_s"] = round(now - t0, 3)
                rec["ttft_s"] = round(st["first"] - t0, 3) if st["first"] else None
            if limited:
                note = "captura incompleta: límite de tamaño de respuesta" if limited == "response_size" else "captura incompleta: límite de respuestas simultáneas"
                rec.update({"capture_limited": limited, "verdict": "N/A", "notes": [note]})
            else:
                written = providers.written_ttl(events)
                if written and not config.TTL_FORCED:
                    minutes = written // 60
                    rec.update({"ttl_s": written, "ttl_source": f"confirmado por usage: escritura a {minutes} min"})
                prev_id = rec.get("prev_id")
                verdict.judge(rec, store.RECORDS.get(prev_id) if prev_id is not None else None)
            store.push(rec)
            log_rec = deepcopy(record.light(rec))
        try:
            store.append_log(log_rec)
        except OSError as exc:
            logger.warning("No se pudo escribir el log del registro %s (%s)", rid, type(exc).__name__)
    finally:
        with store.LOCK:
            if st["reserved"]:
                store.end_capture(rid)
                st["reserved"] = False
            st["chunks"].clear()
            flow.metadata.pop("tap_stream", None)


def error(flow: mitmproxy.http.HTTPFlow) -> None:
    rid = flow.metadata.get("tap_id")
    if rid is None:
        return
    with store.LOCK:
        st = flow.metadata.pop("tap_stream", None)
        if st:
            if st["reserved"]:
                store.end_capture(rid)
                st["reserved"] = False
            st["chunks"].clear()
        rec = store.RECORDS.get(rid)
        if rec:
            rec.update({"state": "error", "ts_end": time.time(), "verdict": "ERR", "notes": [str(flow.error)]})
            store.push(rec)


def load(loader: mitmproxy.addonmanager.Loader) -> None:
    dashboard.start()
    logger.info("Panel disponible en http://127.0.0.1:%s", config.UI_PORT)


def done() -> None:
    dashboard.stop()
    with store.LOCK:
        store.ACTIVE_CAPTURES.clear()
