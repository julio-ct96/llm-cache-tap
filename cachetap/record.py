"""Contract of a request record and helpers to expose it."""

from typing import Literal, Mapping, NotRequired, Required, TypedDict


type JsonValue = None | bool | int | float | str | list["JsonValue"] | JsonObject
type JsonObject = dict[str, JsonValue]
type CacheTTLAnchor = Literal["start", "end"]
type RecordState = Literal["pending", "streaming", "done", "error"]
type Verdict = Literal["HIT", "PARTIAL", "MISS", "COLD", "N/A", "ERR"]
type CaptureLimit = Literal["response_size", "active_captures"]


class CacheTTL(TypedDict):
    ttl_s: Required[int]
    ttl_source: Required[str]
    ttl_anchor: Required[CacheTTLAnchor]
    ttl_max_s: NotRequired[int]


class UsageEvent(TypedDict):
    event: Required[str]
    usage: Required[JsonObject]


class Segment(TypedDict):
    name: Required[str]  # tools, system or msg<i>:<role>
    hash: Required[str]  # fingerprint of the content without cache_control marks
    bytes: Required[int]  # size of the serialized segment
    cc: Required[bool]  # whether it carries a cache_control mark
    preview: Required[str]  # short text for the table
    same: NotRequired[bool]  # only present when there is a previous request


class Diff(TypedDict):
    segment: Required[str]  # segment that changed
    offset: Required[int]  # position of the first differing character
    before: Required[str]  # text of the previous request around the change
    after: Required[str]  # text of this request


class Usage(TypedDict):
    read: Required[int]  # tokens read from cache
    write: Required[int | None]  # tokens written to cache; None if unreported
    uncached: Required[int]  # tokens not served from cache
    input_total: Required[int]  # total input tokens
    output: Required[int]  # output tokens
    reasoning: Required[int | None]  # reasoning tokens


class Record(TypedDict):
    id: Required[int]  # request number
    ts: NotRequired[float]  # request start, epoch
    time: NotRequired[str]  # local time HH:MM:SS
    host: NotRequired[str]  # destination host
    path: NotRequired[str]  # path without query
    model: NotRequired[str | None]  # requested model
    effort: NotRequired[str | None]  # declared effort
    effort_fields: NotRequired[JsonObject]  # request parameters shown in the detail
    _params: NotRequired[str]  # serialized thinking and tool_choice
    req_bytes: NotRequired[int]  # body size
    n_tools: NotRequired[int]  # number of tools
    n_msgs: NotRequired[int]  # number of messages
    cc_marks: NotRequired[int]  # number of cache_control marks
    segs: NotRequired[list[Segment]]  # sliced prefix
    state: NotRequired[RecordState]  # pending, streaming, done or error
    ttl_s: NotRequired[int]  # guaranteed lifetime of the cache entry
    ttl_max_s: NotRequired[int]  # maximum possible lifetime; only some models
    ttl_source: NotRequired[str]  # where the TTL comes from
    ttl_anchor: NotRequired[CacheTTLAnchor]  # provider's TTL counting anchor
    _static: NotRequired[dict[str, str]]  # static segment fingerprints by name
    _msgs: NotRequired[list[str]]  # message fingerprints, in order
    conv: NotRequired[str]  # conversation, c<n>
    prev_id: NotRequired[int | None]  # previous request of the conversation
    gap_s: NotRequired[float]  # seconds since the end of the previous one
    age_s: NotRequired[float]  # cache age of the previous one
    prev_effort: NotRequired[str | None]  # effort of the previous one
    prev_model: NotRequired[str | None]  # model of the previous one
    effort_changed: NotRequired[bool]  # whether the effort changed
    model_changed: NotRequired[bool]  # whether the model changed
    params_changed: NotRequired[bool]  # thinking or tool_choice changed
    prefix_intact: NotRequired[bool]  # whether the prefix matches the previous one
    diverge_at: NotRequired[str | None]  # first differing segment
    diff: NotRequired[Diff | None]  # only exists when there is divergence
    status: NotRequired[int]  # status code
    hdr_s: NotRequired[float]  # seconds until the headers
    resp_headers: NotRequired[dict[str, str]]  # safe response headers
    ts_end: NotRequired[float]  # end of the response, epoch
    ttft_s: NotRequired[float | None]  # seconds until the first token
    total_s: NotRequired[float]  # total duration
    raw_usage: NotRequired[list[UsageEvent]]  # usage events as they arrived
    usage: NotRequired[Usage | None]  # usage in common form
    output: NotRequired[str]  # response text, trimmed
    stop_reason: NotRequired[str | None]  # stop reason
    verdict: NotRequired[Verdict]  # cache verdict
    notes: NotRequired[list[str]]  # explanation of the verdict
    server_side: NotRequired[bool]  # failure not attributable to the client
    capture_limited: NotRequired[CaptureLimit]


# Fields that only travel in /api/record/<id>, not in the list nor in the jsonl.
HEAVY = ("segs", "raw_usage", "output", "effort_fields", "resp_headers", "diff")


def light(rec: Mapping[str, object]) -> dict[str, object]:
    return {k: v for k, v in rec.items() if k not in HEAVY and not k.startswith("_")}


def public(rec: Mapping[str, object]) -> dict[str, object]:
    return {k: v for k, v in rec.items() if not k.startswith("_")}
