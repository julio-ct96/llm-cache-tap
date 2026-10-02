import queue

import tap
from cachetap import config, dashboard, store


def hooks():
    return tap


def reset(log_path):
    store.RECORDS.clear()
    store.BODIES.clear()
    store.CLIENTS.clear()
    store.ACTIVE_CAPTURES.clear()
    store.STATE["next_id"] = 1
    store.STATE["next_conv"] = 1
    store.STATE["body_bytes"] = 0
    config.LOG = log_path


def records():
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in store.RECORDS.values()]


def body_ids():
    return sorted(store.BODIES)


def subscribe():
    q = queue.Queue()
    store.CLIENTS.append(q)
    return q


def set_max(n):
    old = config.MAX
    config.MAX = n
    return old


def handler():
    return dashboard.Handler
