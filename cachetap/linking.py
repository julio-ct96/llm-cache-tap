"""Pair a request with the earlier request of its conversation."""

import re

from cachetap import segments

STATIC_SEG = re.compile(r"^(tools|system)$|:(system|developer)$")


def common(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def find_previous(rec, records):
    """Find the earlier request of the same conversation and describe what changed since.

    Conversations are matched on their messages only, so a client that rewrites
    tools or system between turns still links to its previous turn and the
    rewrite shows up as the divergence.
    """
    static = {s["name"]: s["hash"] for s in rec["segs"] if STATIC_SEG.search(s["name"])}
    msgs = [s["hash"] for s in rec["segs"] if not STATIC_SEG.search(s["name"])]
    rec["_static"], rec["_msgs"] = static, msgs
    best, best_n = None, 0
    for prev in records:
        n = common(msgs, prev["_msgs"])
        if n >= 1 and n >= best_n:
            best, best_n = prev, n
    return best, best_n


def link(rec, req, best, best_n, prev_body):
    """Set on rec its conversation, its gap and age from best, and where its prefix diverges from best."""
    rec["conv"] = best["conv"]
    rec["prev_id"] = best["id"]
    rec["gap_s"] = round(rec["ts"] - (best.get("ts_end") or best["ts"]), 1)
    # age of the previous cache entry, counted the way its provider counts it
    anchor = best["ts"] if best.get("ttl_anchor") == "start" else best.get("ts_end") or best["ts"]
    rec["age_s"] = round(rec["ts"] - anchor, 1)
    rec["prev_effort"] = best.get("effort")
    rec["prev_model"] = best.get("model")
    rec["effort_changed"] = best.get("effort") != rec.get("effort")
    rec["model_changed"] = best.get("model") != rec.get("model")
    rec["params_changed"] = best.get("_params") != rec.get("_params")
    diverge, mi = None, 0
    for s in rec["segs"]:
        if STATIC_SEG.search(s["name"]):
            same = best["_static"].get(s["name"]) == s["hash"]
        else:
            same = mi < best_n
            in_prev = mi < len(best["_msgs"])
            mi += 1
            if not same and not in_prev:
                s["same"] = False
                continue
        s["same"] = same and diverge is None
        if not same and diverge is None:
            diverge = s["name"]
    if diverge is None and set(best["_static"]) - set(rec["_static"]):
        diverge = sorted(set(best["_static"]) - set(rec["_static"]))[0] + " (eliminado)"
    rec["prefix_intact"] = diverge is None
    rec["diverge_at"] = diverge
    if diverge:
        rec["diff"] = segments.first_diff(prev_body, diverge, req)
