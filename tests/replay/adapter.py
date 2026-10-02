import queue

import tap
from cachetap import config


def hooks():
    return tap


def reset(log_path):
    tap.RECORDS.clear()
    tap.BODIES.clear()
    tap.CLIENTS.clear()
    tap.STATE["next_id"] = 1
    tap.STATE["next_conv"] = 1
    config.LOG = log_path


def records():
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in tap.RECORDS.values()]


def body_ids():
    return sorted(tap.BODIES)


def subscribe():
    q = queue.Queue()
    tap.CLIENTS.append(q)
    return q


def set_max(n):
    old = config.MAX
    config.MAX = n
    return old


def handler():
    return tap.Handler
