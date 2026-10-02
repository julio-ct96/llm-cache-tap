"""In-memory records, panel subscribers and the jsonl log."""

import json
import threading
from collections import OrderedDict

from cachetap import config, record

LOCK = threading.Lock()
RECORDS: "OrderedDict[int, dict]" = OrderedDict()
BODIES: dict = {}
CLIENTS: list = []
ACTIVE_CAPTURES: set[int] = set()
STATE = {"next_id": 1, "next_conv": 1, "body_bytes": 0}


# Every function below except `publish` must be called with LOCK held by the caller.
# None of them takes LOCK itself.

def publish(ev):
    for q in list(CLIENTS):
        q.put(ev)


def push(rec, evicted_ids=()):
    if evicted_ids and rec["id"] not in RECORDS:
        publish({"type": "evict", "ids": list(evicted_ids)})
        return
    ev = {"type": "record", "rec": record.light(rec)}
    if evicted_ids:
        ev["evicted_ids"] = list(evicted_ids)
    publish(ev)


def next_id():
    rid = STATE["next_id"]
    STATE["next_id"] += 1
    return rid


def new_conv():
    conv = f"c{STATE['next_conv']}"
    STATE["next_conv"] += 1
    return conv


def begin_capture(rid):
    if rid in ACTIVE_CAPTURES or len(ACTIVE_CAPTURES) >= config.MAX_ACTIVE_CAPTURES:
        return False
    ACTIVE_CAPTURES.add(rid)
    return True


def end_capture(rid):
    ACTIVE_CAPTURES.discard(rid)


def add(rec, body):
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
    return evicted_ids


def clear():
    RECORDS.clear()
    BODIES.clear()
    STATE["body_bytes"] = 0
    publish({"type": "clear"})


def append_log(rec):
    config.LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(config.LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record.light(rec), ensure_ascii=False) + "\n")
