"""Shared setup and lifecycle for an inspected request capture."""

import logging
import time
from copy import deepcopy
from typing import TypedDict

from cachetap import (
    config,
    cost,
    linking,
    providers,
    record,
    response_body,
    segments,
    store,
    verdict,
)


class StreamState(TypedDict):
    chunks: list[bytes]
    first: float | None
    bytes: int
    limited: record.CaptureLimit | None
    reserved: bool


def begin(
    req: record.JsonObject,
    text: str,
    host: str,
    path: str,
    request_bytes: int,
    started_at: float | None,
) -> int:
    """Create and publish a pending record for a validated request."""
    messages = req.get("messages") or req.get("input") or []
    n_msgs = (
        int(bool(messages))
        if isinstance(messages, str)
        else len(messages)
        if isinstance(messages, (list, dict))
        else 0
    )
    tools = req.get("tools")
    model = req.get("model")
    with store.LOCK:
        rid = store.next_id()
        rec: record.Record = {
            "id": rid,
            "host": host,
            "path": path,
            "model": model if isinstance(model, str) else None,
            "effort": providers.effort_of(req),
            "effort_fields": {
                k: req[k]
                for k in (
                    "output_config",
                    "thinking",
                    "reasoning",
                    "reasoning_effort",
                    "tool_choice",
                    "max_tokens",
                    "max_output_tokens",
                    "stream",
                )
                if k in req
            },
            "_params": segments.dump({k: req.get(k) for k in ("thinking", "tool_choice")}),
            "req_bytes": request_bytes,
            "n_tools": len(tools) if isinstance(tools, (list, dict)) else 0,
            "n_msgs": n_msgs,
            "cc_marks": text.count('"cache_control"'),
            "segs": segments.segments(req),
            "state": "pending",
        }
        if started_at is not None:
            rec["ts"] = started_at
            rec["time"] = time.strftime("%H:%M:%S", time.localtime(started_at))
        rec.update(providers.cache_ttl(req))
        linking.prepare_fingerprints(rec)
        previous, matched_message_count = linking.find_previous(rec, store.RECORDS.values())
        if previous is None:
            rec["conv"] = store.new_conv()
            rec["prev_id"] = None
        else:
            linking.link(
                rec, req, previous, matched_message_count, store.BODIES.get(previous["id"])
            )
        evicted_ids = store.add(rec, text)
        store.push(rec, evicted_ids)
    return rid


def start(
    rid: int,
    status: int,
    response_headers: dict[str, str],
    request_end: float | None,
    response_start: float | None,
) -> StreamState:
    """Reserve a response capture and publish its initial streaming state."""
    with store.LOCK:
        reserved = store.begin_capture(rid)
        state: StreamState = {
            "chunks": [],
            "first": None,
            "bytes": 0,
            "limited": None if reserved else "active_captures",
            "reserved": reserved,
        }
        rec = store.RECORDS.get(rid)
        if rec:
            rec["state"] = "streaming"
            rec["status"] = status
            if response_start is not None and request_end is not None:
                rec["hdr_s"] = round(response_start - request_end, 3)
            rec["resp_headers"] = response_headers
            store.push(rec)
    return state


def feed(rid: int, state: StreamState, data: bytes) -> bytes:
    """Observe response bytes for metrics while returning them unchanged."""
    if data:
        if state["first"] is None and any(k in data for k in providers.FIRST_TOKEN):
            state["first"] = time.time()
        if state["limited"] is None:
            state["bytes"] += len(data)
            if state["bytes"] > config.MAX_RESPONSE_BYTES:
                limit(rid, state, "response_size")
            else:
                state["chunks"].append(data)
    return data


def limit(rid: int, state: StreamState, reason: record.CaptureLimit) -> None:
    """Stop retaining response data and release its reservation once."""
    if state["limited"] is None:
        state["chunks"].clear()
        state["limited"] = reason
    if state["reserved"]:
        with store.LOCK:
            store.end_capture(rid)
        state["reserved"] = False


def finish(
    rid: int,
    state: StreamState,
    status: int,
    request_end: float | None,
    logger: logging.Logger,
) -> None:
    """Read the captured response, publish its verdict and log, then clean up."""
    try:
        now = time.time()
        limited = state["limited"]
        body = b"".join(state["chunks"]).decode("utf8", "replace") if limited is None else ""
        events = response_body.usage_events(body) if limited is None else []
        output, stop = response_body.output_text(body) if limited is None else ("", None)
        with store.LOCK:
            rec = store.RECORDS.get(rid)
            if not rec:
                return
            rec.update(
                {
                    "state": "done",
                    "ts_end": now,
                    "raw_usage": events,
                    "usage": providers.normalize(events) if limited is None else None,
                    "output": output if status < 400 else body[:2000],
                    "stop_reason": stop,
                }
            )
            if request_end is not None:
                rec["total_s"] = round(now - request_end, 3)
                rec["ttft_s"] = round(state["first"] - request_end, 3) if state["first"] else None
            if limited:
                note = (
                    "captura incompleta: límite de tamaño de respuesta"
                    if limited == "response_size"
                    else "captura incompleta: límite de respuestas simultáneas"
                )
                rec.update({"capture_limited": limited, "verdict": "N/A", "notes": [note]})
            else:
                written = providers.written_ttl(events)
                if written and not config.TTL_FORCED:
                    minutes = written // 60
                    rec.update(
                        {
                            "ttl_s": written,
                            "ttl_source": f"confirmado por usage: escritura a {minutes} min",
                        }
                    )
                prev_id = rec.get("prev_id")
                prev = store.RECORDS.get(prev_id) if prev_id is not None else None
                verdict.judge(rec, prev)
                cost.price_record(rec, prev, providers.written_1h(events))
                store.count_cost(rec)
            store.push(rec)
            log_rec = deepcopy(record.light(rec))
        try:
            store.append_log(log_rec)
        except OSError as exc:
            logger.warning(
                "No se pudo escribir el log del registro %s (%s)", rid, type(exc).__name__
            )
    finally:
        try:
            with store.LOCK:
                if state["reserved"]:
                    store.end_capture(rid)
                    state["reserved"] = False
        finally:
            state["chunks"].clear()


def fail(rid: int, state: StreamState | None, message: str) -> None:
    """Release an unfinished response capture and publish its error."""
    with store.LOCK:
        if state:
            if state["reserved"]:
                store.end_capture(rid)
                state["reserved"] = False
            state["chunks"].clear()
        rec = store.RECORDS.get(rid)
        if rec:
            rec.update(
                {
                    "state": "error",
                    "ts_end": time.time(),
                    "verdict": "ERR",
                    "notes": [message],
                }
            )
            store.push(rec)
