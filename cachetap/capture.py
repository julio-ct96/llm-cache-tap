"""Shared setup for an inspected request capture."""

import time

from cachetap import linking, providers, record, segments, store


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
