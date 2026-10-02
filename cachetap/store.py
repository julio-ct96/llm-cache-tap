"""In-memory records, panel subscribers and the jsonl log."""

import json
import threading
from collections import OrderedDict

from cachetap import config, record

LOCK = threading.Lock()
RECORDS: "OrderedDict[int, dict]" = OrderedDict()
BODIES: dict = {}
CLIENTS: list = []
STATE = {"next_id": 1, "next_conv": 1}


# Every function below except `publish` must be called with LOCK held by the caller.
# None of them takes LOCK itself.

def publish(ev):
    for q in list(CLIENTS):
        q.put(ev)


def push(rec):
    publish({"type": "record", "rec": record.light(rec)})


def next_id():
    rid = STATE["next_id"]
    STATE["next_id"] += 1
    return rid


def new_conv():
    conv = f"c{STATE['next_conv']}"
    STATE["next_conv"] += 1
    return conv


def add(rec, body):
    RECORDS[rec["id"]] = rec
    BODIES[rec["id"]] = body
    while len(RECORDS) > config.MAX:
        old, _ = RECORDS.popitem(last=False)
        BODIES.pop(old, None)


def clear():
    RECORDS.clear()
    BODIES.clear()
    publish({"type": "clear"})


def append_log(rec):
    config.LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(config.LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record.light(rec), ensure_ascii=False) + "\n")
