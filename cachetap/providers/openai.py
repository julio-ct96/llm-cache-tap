"""What depends on the model being from OpenAI: cache TTL and minimum cacheable prefix."""

import re

from cachetap.providers import base

FIRST_TOKEN = (b"output_text.delta", b'"delta":{"content"', b"reasoning")


def owns(model):
    return bool(base.version(model, "gpt") or re.match(r"o\d", model))


def cache_ttl(req, model):
    gpt = base.version(model, "gpt")
    if gpt and gpt >= (5, 6):
        declared = isinstance(req.get("prompt_cache_options"), dict) and req["prompt_cache_options"].get("ttl")
        source = "declarado en prompt_cache_options" if declared else "por defecto de GPT-5.6 y posteriores"
        return {"ttl_s": 1800, "ttl_source": source, "ttl_anchor": "end"}
    if gpt or re.match(r"o\d", model):
        retention = req.get("prompt_cache_retention")
        if retention == "24h":
            return {"ttl_s": 1800, "ttl_max_s": 86400, "ttl_source": "declarado: retención 24h", "ttl_anchor": "end"}
        if retention == "in_memory":
            return {"ttl_s": 300, "ttl_max_s": 3600, "ttl_source": "declarado: retención in_memory", "ttl_anchor": "end"}
        if not (gpt == (4, 1) or (gpt and (5, 0) <= gpt)):
            return {"ttl_s": 300, "ttl_max_s": 3600, "ttl_source": "por defecto: este modelo solo admite in_memory", "ttl_anchor": "end"}
        # the default retention depends on the organisation (24h unless it has zero data retention)
        return {"ttl_s": 300, "ttl_max_s": 86400, "ttl_source": "supuesto: la retención por defecto depende de la organización", "ttl_anchor": "end"}


def min_cacheable(model):
    return 1024


def effort(req):
    r = req.get("reasoning")
    return (
        (r.get("effort") if isinstance(r, dict) else None)
        or req.get("reasoning_effort")
    )


def normalize(merged):
    inp = merged.get("input_tokens", merged.get("prompt_tokens")) or 0
    det = merged.get("input_tokens_details") or merged.get("prompt_tokens_details") or {}
    odet = merged.get("output_tokens_details") or merged.get("completion_tokens_details") or {}
    read = det.get("cached_tokens") or 0
    return {"read": read, "write": None, "uncached": inp - read, "input_total": inp,
            "output": merged.get("output_tokens", merged.get("completion_tokens")) or 0,
            "reasoning": odet.get("reasoning_tokens")}
