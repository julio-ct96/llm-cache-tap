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

if __name__.startswith("__mitmproxy_script__"):
    # mitmproxy re-executes this file on save; dropping cachetap modules reloads submodules too.
    for _name in [m for m in sys.modules if m == "cachetap" or m.startswith("cachetap.")]:
        del sys.modules[_name]

from cachetap import config, dashboard, linking, providers, record, request_body, response_body, segments, store, verdict

logger = logging.getLogger(__name__)

LLM_PATHS = ("/messages", "/responses", "/chat/completions")
SAFE_HEADER = re.compile(r"request-id|region|geo|served|backend|azure|ratelimit|quota|processing|x-cache|via$", re.I)
UNSAFE_HEADER = re.compile(r"token|auth|cookie|secret|key", re.I)

# ---------- mitmproxy hooks ----------

def _is_llm(flow):
    return flow.request.method == "POST" and flow.request.path.split("?")[0].rstrip("/").endswith(LLM_PATHS)


def request(flow):
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
    n_msgs = int(bool(messages)) if isinstance(messages, str) else len(messages)
    with store.LOCK:
        rid = store.next_id()
        rec = {
            "id": rid,
            "ts": flow.request.timestamp_start,
            "time": time.strftime("%H:%M:%S", time.localtime(flow.request.timestamp_start)),
            "host": flow.request.pretty_host,
            "path": flow.request.path.split("?")[0],
            "model": req.get("model"),
            "effort": providers.effort_of(req),
            "effort_fields": {k: req[k] for k in ("output_config", "thinking", "reasoning", "reasoning_effort", "tool_choice", "max_tokens", "max_output_tokens", "stream") if k in req},
            "_params": segments.dump({k: req.get(k) for k in ("thinking", "tool_choice")}),
            "req_bytes": len(flow.request.raw_content or b""),
            "n_tools": len(req.get("tools") or []),
            "n_msgs": n_msgs,
            "cc_marks": text.count('"cache_control"'),
            "segs": segments.segments(req),
            "state": "pending",
            **providers.cache_ttl(req),
        }
        best, best_n = linking.find_previous(rec, store.RECORDS.values())
        if best is None:
            rec["conv"] = store.new_conv()
            rec["prev_id"] = None
        else:
            linking.link(rec, req, best, best_n, store.BODIES.get(best["id"]))
        evicted_ids = store.add(rec, text)
        store.push(rec, evicted_ids)
    flow.metadata["tap_id"] = rid


def responseheaders(flow):
    rid = flow.metadata.get("tap_id")
    if rid is None:
        return
    st = {"chunks": [], "first": None}
    flow.metadata["tap_stream"] = st

    def stream(data: bytes):
        if data:
            st["chunks"].append(data)
            if st["first"] is None and any(k in data for k in providers.FIRST_TOKEN):
                st["first"] = time.time()
        return data

    flow.response.stream = stream
    with store.LOCK:
        rec = store.RECORDS.get(rid)
        if rec:
            rec["state"] = "streaming"
            rec["status"] = flow.response.status_code
            rec["hdr_s"] = round(flow.response.timestamp_start - flow.request.timestamp_end, 3)
            rec["resp_headers"] = {k: v for k, v in flow.response.headers.items() if SAFE_HEADER.search(k) and not UNSAFE_HEADER.search(k)}
            store.push(rec)


def response(flow):
    rid = flow.metadata.get("tap_id")
    st = flow.metadata.get("tap_stream")
    if rid is None or st is None:
        return
    now = time.time()
    body = b"".join(st["chunks"]).decode("utf8", "replace")
    events = response_body.usage_events(body)
    output, stop = response_body.output_text(body)
    t0 = flow.request.timestamp_end
    with store.LOCK:
        rec = store.RECORDS.get(rid)
        if not rec:
            return
        rec.update({
            "state": "done",
            "ts_end": now,
            "ttft_s": round(st["first"] - t0, 3) if st["first"] else None,
            "total_s": round(now - t0, 3),
            "raw_usage": events,
            "usage": providers.normalize(events),
            "output": output if flow.response.status_code < 400 else body[:2000],
            "stop_reason": stop,
        })
        written = providers.written_ttl(events)
        if written and not config.TTL_FORCED:
            minutes = written // 60
            rec.update({"ttl_s": written, "ttl_source": f"confirmado por usage: escritura a {minutes} min"})
        verdict.judge(rec, store.RECORDS.get(rec.get("prev_id")))
        store.push(rec)
        store.append_log(rec)


def error(flow):
    rid = flow.metadata.get("tap_id")
    if rid is None:
        return
    with store.LOCK:
        rec = store.RECORDS.get(rid)
        if rec:
            rec.update({"state": "error", "ts_end": time.time(), "verdict": "ERR", "notes": [str(flow.error)]})
            store.push(rec)


def load(loader):
    dashboard.start()
    print(f"[tap] dashboard: http://127.0.0.1:{config.UI_PORT}", flush=True)


def done():
    dashboard.stop()
