"""What depends on the model being Claude: cache TTL and minimum cacheable prefix."""

import re

from cachetap.providers import base

TTL_NAMES = {"5m": 300, "30m": 1800, "1h": 3600}
FIRST_TOKEN = (b"content_block_delta",)


def owns(model):
    return "claude" in model


def cache_controls(o):
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


TTL_HELP = [
    {"models": "Claude (todos)", "ttl": '5 min, o 1 h si `cache_control` lleva `ttl: "1h"`', "anchor": "inicio de la petición"},
]


def cache_ttl(req, model):
    # 5 minutes unless a breakpoint asks for 1 hour; the shortest one is the first to go
    marks = list(cache_controls(req))
    ttl = min((TTL_NAMES.get(m.get("ttl", "5m"), 300) for m in marks), default=300)
    if any("ttl" in m for m in marks):
        source = "declarado en cache_control"
    else:
        source = "por defecto de Claude"
    return {"ttl_s": ttl, "ttl_source": source, "ttl_anchor": "start"}


MIN_CACHEABLE_HELP = [
    {"models": "Claude Fable y Mythos 5.x, Opus 5.x, Sonnet 5.x", "tokens": 512, "example": "claude-opus-5-5"},
    {"models": "Claude Opus 4.8, Sonnet 4.6 y 4.5", "tokens": 1024, "example": "claude-sonnet-4-5"},
    {"models": "Claude Opus 4.7", "tokens": 2048, "example": "claude-opus-4-7"},
    {"models": "Claude Opus 4.6 y 4.5, Haiku 4.5", "tokens": 4096, "example": "claude-haiku-4-5"},
]


def min_cacheable(model):
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


def effort(req):
    oc = req.get("output_config") or {}
    return oc.get("effort") if isinstance(oc, dict) else None


def normalize(merged):
    if "cache_read_input_tokens" in merged or "cache_creation_input_tokens" in merged:
        read = merged.get("cache_read_input_tokens") or 0
        write = merged.get("cache_creation_input_tokens") or 0
        unc = merged.get("input_tokens") or 0
        return {"read": read, "write": write, "uncached": unc, "input_total": read + write + unc,
                "output": merged.get("output_tokens") or 0, "reasoning": None}
    return None


def deltas(ev):
    """Texts and stop reason carried by one streamed event."""
    d = ev.get("delta")
    if not isinstance(d, dict):
        return [], None
    texts = [d["text"]] if isinstance(d.get("text"), str) else []
    return texts, d.get("stop_reason")


def written_ttl(events):
    """TTL of what Claude actually wrote to cache, when the usage breaks it down."""
    for e in events:
        made = e["usage"].get("cache_creation")
        if isinstance(made, dict):
            if made.get("ephemeral_5m_input_tokens"):
                return 300
            if made.get("ephemeral_1h_input_tokens"):
                return 3600
    return None
