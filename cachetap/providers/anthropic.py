"""What depends on the model being Claude: cache TTL and minimum cacheable prefix."""

import re
from collections.abc import Iterator
from typing import Required, TypedDict

from cachetap import record
from cachetap.providers import base

TTL_NAMES = {"5m": 300, "30m": 1800, "1h": 3600}
FIRST_TOKEN = (b"content_block_delta",)


def owns(model: str) -> bool:
    return "claude" in model


def cache_controls(o: record.JsonValue) -> Iterator[record.JsonObject]:
    """Every cache_control object of the request, at any depth."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "cache_control" and isinstance(v, dict):
                yield v
            else:
                yield from cache_controls(v)
    elif isinstance(o, list):
        for x in o:
            yield from cache_controls(x)


class TTLHelpRow(TypedDict):
    models: Required[str]
    ttl: Required[str]
    anchor: Required[str]


class MinimumHelpRow(TypedDict):
    models: Required[str]
    tokens: Required[int]
    example: Required[str]


TTL_HELP: list[TTLHelpRow] = [
    {"models": "Claude (todos)", "ttl": '5 min, o 1 h si `cache_control` lleva `ttl: "1h"`', "anchor": "inicio de la petición"},
]


def cache_ttl(req: record.JsonObject, model: str) -> record.CacheTTL:
    # 5 minutes unless a breakpoint asks for 1 hour; the shortest one is the first to go
    marks = list(cache_controls(req))
    ttl = min(
        (
            TTL_NAMES.get(ttl_value, 300) if isinstance(ttl_value, str) else 300
            for m in marks
            for ttl_value in (m.get("ttl", "5m"),)
        ),
        default=300,
    )
    if any("ttl" in m for m in marks):
        source = "declarado en cache_control"
    else:
        source = "por defecto de Claude"
    return {"ttl_s": ttl, "ttl_source": source, "ttl_anchor": "start"}


MIN_CACHEABLE_HELP: list[MinimumHelpRow] = [
    {"models": "Claude Fable y Mythos 5.x, Opus 5.x, Sonnet 5.x", "tokens": 512, "example": "claude-opus-5-5"},
    {"models": "Claude Opus 4.8, Sonnet 4.6 y 4.5", "tokens": 1024, "example": "claude-sonnet-4-5"},
    {"models": "Claude Opus 4.7", "tokens": 2048, "example": "claude-opus-4-7"},
    {"models": "Claude Opus 4.6 y 4.5, Haiku 4.5", "tokens": 4096, "example": "claude-haiku-4-5"},
]


def min_cacheable(model: str) -> int:
    if re.search(r"fable|mythos", model) and "preview" not in model:
        return 512
    opus, sonnet, haiku = (base.version(model, f"claude-{f}") for f in ("opus", "sonnet", "haiku"))
    if (opus and opus >= (5, 0)) or (sonnet and sonnet >= (5, 0)):
        return 512
    if opus == (4, 7) or haiku == (3, 5) or "mythos" in model:
        return 2048
    if opus in ((4, 6), (4, 5)) or haiku == (4, 5):
        return 4096
    return 1024


def effort(req: record.JsonObject) -> str | None:
    oc = req.get("output_config") or {}
    effort_value = oc.get("effort") if isinstance(oc, dict) else None
    return effort_value if isinstance(effort_value, str) else None


def normalize(merged: record.JsonObject) -> record.Usage | None:
    if "cache_read_input_tokens" in merged or "cache_creation_input_tokens" in merged:
        read = merged.get("cache_read_input_tokens", 0)
        write = merged.get("cache_creation_input_tokens", 0)
        unc = merged.get("input_tokens", 0)
        read = read if isinstance(read, int) and not isinstance(read, bool) and read >= 0 else 0
        write = write if isinstance(write, int) and not isinstance(write, bool) and write >= 0 else 0
        unc = unc if isinstance(unc, int) and not isinstance(unc, bool) and unc >= 0 else 0
        output = merged.get("output_tokens", 0)
        output = output if isinstance(output, int) and not isinstance(output, bool) and output >= 0 else 0
        return {"read": read, "write": write, "uncached": unc, "input_total": read + write + unc,
                "output": output, "reasoning": None}
    return None


def deltas(ev: record.JsonObject) -> tuple[list[str], str | None]:
    """Texts and stop reason carried by one streamed event."""
    d = ev.get("delta")
    if not isinstance(d, dict):
        return [], None
    text = d.get("text")
    texts = [text] if isinstance(text, str) else []
    reason = d.get("stop_reason")
    return texts, reason if isinstance(reason, str) else None


def written_ttl(events: list[record.UsageEvent]) -> int | None:
    """TTL of what Claude actually wrote to cache, when the usage breaks it down."""
    for e in events:
        made = e["usage"].get("cache_creation")
        if isinstance(made, dict):
            if made.get("ephemeral_5m_input_tokens"):
                return 300
            if made.get("ephemeral_1h_input_tokens"):
                return 3600
    return None
