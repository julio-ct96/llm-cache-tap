"""Pair a request with the earlier request of its conversation."""

import re
from collections.abc import Iterable, Sequence

from cachetap import record, segments

STATIC_SEG = re.compile(r"^(tools|system)$|:(system|developer)$")


def common_prefix_length(a: Sequence[object], b: Sequence[object]) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def prepare_fingerprints(rec: record.Record) -> None:
    """Mutate rec by setting its _static and _msgs fields to segment fingerprints."""
    static = {s["name"]: s["hash"] for s in rec["segs"] if STATIC_SEG.search(s["name"])}
    msgs = [s["hash"] for s in rec["segs"] if not STATIC_SEG.search(s["name"])]
    rec["_static"], rec["_msgs"] = static, msgs


def find_previous(
    rec: record.Record,
    records: Iterable[record.Record],
) -> tuple[record.Record | None, int]:
    """Find the earlier request of the same conversation in O(R × M) time.

    Conversations are matched on their messages only, so a client that rewrites
    tools or system between turns still links to its previous turn and the
    rewrite shows up as the divergence. R is the number of candidate records and
    M is the message-prefix length compared for each candidate; comparisons stop
    at the first differing message.
    """
    matched_message_count = 0
    previous = None
    for candidate in records:
        prefix_length = common_prefix_length(rec["_msgs"], candidate["_msgs"])
        if prefix_length >= 1 and prefix_length >= matched_message_count:
            previous, matched_message_count = candidate, prefix_length
    return previous, matched_message_count


def link(
    rec: record.Record,
    req: record.JsonObject,
    previous: record.Record,
    matched_message_count: int,
    prev_body: str | None,
) -> None:
    """Mutate rec with conversation, timing, change, prefix and diff fields from previous."""
    rec["conv"] = previous["conv"]
    rec["prev_id"] = previous["id"]
    rec["gap_s"] = round(rec["ts"] - (previous.get("ts_end") or previous["ts"]), 1)
    # age of the previous cache entry, counted the way its provider counts it
    anchor = previous["ts"] if previous.get("ttl_anchor") == "start" else previous.get("ts_end") or previous["ts"]
    rec["age_s"] = round(rec["ts"] - anchor, 1)
    rec["prev_effort"] = previous.get("effort")
    rec["prev_model"] = previous.get("model")
    rec["effort_changed"] = previous.get("effort") != rec.get("effort")
    rec["model_changed"] = previous.get("model") != rec.get("model")
    rec["params_changed"] = previous.get("_params") != rec.get("_params")
    diverge, message_index = None, 0
    for s in rec["segs"]:
        if STATIC_SEG.search(s["name"]):
            same = previous["_static"].get(s["name"]) == s["hash"]
        else:
            same = message_index < matched_message_count
            in_prev = message_index < len(previous["_msgs"])
            message_index += 1
            if not same and not in_prev:
                s["same"] = False
                continue
        s["same"] = same and diverge is None
        if not same and diverge is None:
            diverge = s["name"]
    if diverge is None and set(previous["_static"]) - set(rec["_static"]):
        diverge = sorted(set(previous["_static"]) - set(rec["_static"]))[0] + " (eliminado)"
    rec["prefix_intact"] = diverge is None
    rec["diverge_at"] = diverge
    if diverge:
        rec["diff"] = segments.first_diff(prev_body, diverge, req)
