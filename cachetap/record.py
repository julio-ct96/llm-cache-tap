"""Contract of a request record and helpers to expose it."""

from typing import TypedDict


class Segment(TypedDict, total=False):
    name: str  # tools, system or msg<i>:<role>
    hash: str  # fingerprint of the content without cache_control marks
    bytes: int  # size of the serialized segment
    cc: bool  # whether it carries a cache_control mark
    preview: str  # short text for the table
    same: bool  # whether it matches the previous request; only present when there is one


class Diff(TypedDict, total=False):
    segment: str  # segment that changed
    offset: int  # position of the first differing character
    before: str  # text of the previous request around the change
    after: str  # text of this request


class Usage(TypedDict, total=False):
    read: int  # tokens read from cache
    write: int | None  # tokens written to cache; None if the provider does not report it
    uncached: int  # tokens not served from cache
    input_total: int  # total input tokens
    output: int  # output tokens
    reasoning: int | None  # reasoning tokens


class Record(TypedDict, total=False):
    id: int  # request number
    ts: float  # request start, epoch
    time: str  # local time HH:MM:SS
    host: str  # destination host
    path: str  # path without query
    model: str | None  # requested model
    effort: str | None  # declared effort
    effort_fields: dict  # request parameters shown in the detail
    _params: str  # serialized thinking and tool_choice, to compare with the previous one
    req_bytes: int  # body size
    n_tools: int  # number of tools
    n_msgs: int  # number of messages
    cc_marks: int  # number of cache_control marks
    segs: list[Segment]  # sliced prefix
    state: str  # pending, streaming, done or error
    ttl_s: int  # guaranteed lifetime of the cache entry
    ttl_max_s: int  # maximum possible lifetime; only some models
    ttl_source: str  # where the TTL comes from
    ttl_anchor: str  # start or end: from where the provider counts
    _static: dict  # fingerprint of the static segments, by name
    _msgs: list[str]  # fingerprints of the messages, in order
    conv: str  # conversation, c<n>
    prev_id: int | None  # previous request of the conversation
    gap_s: float  # seconds since the end of the previous one
    age_s: float  # cache age of the previous one, counted as its provider does
    prev_effort: str | None  # effort of the previous one
    prev_model: str | None  # model of the previous one
    effort_changed: bool  # whether the effort changed
    model_changed: bool  # whether the model changed
    params_changed: bool  # thinking or tool_choice changed
    prefix_intact: bool  # the prefix matches the previous one
    diverge_at: str | None  # first differing segment
    diff: Diff | None  # only exists when there is divergence
    status: int  # status code
    hdr_s: float  # seconds until the headers
    resp_headers: dict  # safe response headers
    ts_end: float  # end of the response, epoch
    ttft_s: float | None  # seconds until the first token
    total_s: float  # total duration
    raw_usage: list  # usage events as they arrived
    usage: Usage | None  # usage in common form
    output: str  # response text, trimmed
    stop_reason: str | None  # stop reason
    verdict: str  # HIT, PARTIAL, MISS, COLD, N/A or ERR
    notes: list[str]  # explanation of the verdict
    server_side: bool  # failure with no cause attributable to the client


# Fields that only travel in /api/record/<id>, not in the list nor in the jsonl.
HEAVY = ("segs", "raw_usage", "output", "effort_fields", "resp_headers", "diff")


def light(rec):
    return {k: v for k, v in rec.items() if k not in HEAVY and not k.startswith("_")}


def public(rec):
    return {k: v for k, v in rec.items() if not k.startswith("_")}
