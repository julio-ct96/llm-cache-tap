"""In-memory records, panel subscribers and the jsonl log."""

import json
import queue
import threading
from collections import OrderedDict
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias

from cachetap import config, record

LOCK = threading.Lock()
EventQueue: TypeAlias = queue.Queue[record.Event]

RECORDS: OrderedDict[int, record.Record] = OrderedDict()
BODIES: dict[int, str] = {}
CLIENTS: list[EventQueue] = []
ACTIVE_CAPTURES: set[int] = set()
CONV_TOTALS: dict[str, record.ConvTotal] = {}
STATE: dict[str, int] = {"next_id": 1, "next_conv": 1, "body_bytes": 0}


# State functions require LOCK held by the caller. None of them takes LOCK itself.
# append_log is the exception: it performs filesystem I/O and must run outside LOCK.


def subscribe() -> EventQueue:
    q: EventQueue = queue.Queue(maxsize=config.MAX_CLIENT_EVENTS)
    CLIENTS.append(q)
    return q


def unsubscribe(q: EventQueue) -> None:
    if q in CLIENTS:
        CLIENTS.remove(q)


def publish(ev: record.Event) -> None:
    for q in list(CLIENTS):
        try:
            q.put_nowait(ev)
        except queue.Full:
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
            q.put_nowait({"type": "disconnect"})
            unsubscribe(q)


def push(rec: record.Record, evicted_ids: tuple[int, ...] | list[int] = ()) -> None:
    if evicted_ids and rec["id"] not in RECORDS:
        publish({"type": "evict", "ids": list(evicted_ids)})
        return
    ev: record.RecordEvent = {"type": "record", "rec": record.light(rec)}
    if evicted_ids:
        ev["evicted_ids"] = list(evicted_ids)
    conv = rec.get("conv")
    if conv in CONV_TOTALS:
        ev["convs"] = {conv: CONV_TOTALS[conv].copy()}
    publish(ev)


def next_id() -> int:
    rid = STATE["next_id"]
    STATE["next_id"] += 1
    return rid


def new_conv() -> str:
    conv = f"c{STATE['next_conv']}"
    STATE["next_conv"] += 1
    return conv


def begin_capture(rid: int) -> bool:
    if rid in ACTIVE_CAPTURES or len(ACTIVE_CAPTURES) >= config.MAX_ACTIVE_CAPTURES:
        return False
    ACTIVE_CAPTURES.add(rid)
    return True


def end_capture(rid: int) -> None:
    ACTIVE_CAPTURES.discard(rid)


def add(rec: record.Record, body: str) -> list[int]:
    rid = rec["id"]
    old_body = BODIES.pop(rid, None)
    if old_body is not None:
        STATE["body_bytes"] -= len(old_body.encode("utf-8"))
    RECORDS[rec["id"]] = rec
    BODIES[rec["id"]] = body
    STATE["body_bytes"] += len(body.encode("utf-8"))
    evicted_ids = []
    while len(RECORDS) > config.MAX or STATE["body_bytes"] > config.MAX_BODY_BYTES:
        old, _ = RECORDS.popitem(last=False)
        old_body = BODIES.pop(old, None)
        if old_body is not None:
            STATE["body_bytes"] -= len(old_body.encode("utf-8"))
        evicted_ids.append(old)
    if evicted_ids:
        # a total lives as long as any request of its conversation does
        alive = {r.get("conv") for r in RECORDS.values()}
        for conv in [c for c in CONV_TOTALS if c not in alive]:
            del CONV_TOTALS[conv]
    return evicted_ids


def count_cost(rec: record.Record) -> None:
    """Add a finished request to the running total of its conversation. Call it once per request."""
    conv, cost = rec.get("conv"), rec.get("cost")
    if conv is None or (cost is None and "cost_missing" not in rec):
        return
    total = CONV_TOTALS.setdefault(
        conv,
        {
            "priced": 0,
            "unpriced": 0,
            "usd": 0.0,
            "no_cache_usd": 0.0,
            "saved_usd": 0.0,
            "lost_usd": 0.0,
        },
    )
    if cost is None:
        total["unpriced"] += 1
        return
    total["priced"] += 1
    total["usd"] = round(total["usd"] + cost["usd"], 8)
    total["no_cache_usd"] = round(total["no_cache_usd"] + cost["no_cache_usd"], 8)
    total["saved_usd"] = round(total["saved_usd"] + cost["saved_usd"], 8)
    total["lost_usd"] = round(total["lost_usd"] + cost.get("lost_usd", 0.0), 8)


def clear() -> None:
    RECORDS.clear()
    BODIES.clear()
    CONV_TOTALS.clear()
    STATE["body_bytes"] = 0
    publish({"type": "clear"})


def append_log(rec: Mapping[str, object]) -> None:
    config.LOG.parent.mkdir(parents=True, exist_ok=True)
    with Path(config.LOG).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.light(rec), ensure_ascii=False) + "\n")
