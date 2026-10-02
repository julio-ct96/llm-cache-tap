import tap
from cachetap import config, dashboard, store


def hooks():
    return tap


def reset(log_path):
    with store.LOCK:
        store.RECORDS.clear()
        store.BODIES.clear()
        for q in list(store.CLIENTS):
            store.unsubscribe(q)
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
    with store.LOCK:
        return store.subscribe()


def set_max(n):
    old = config.MAX
    config.MAX = n
    return old


def handler():
    return dashboard.Handler
