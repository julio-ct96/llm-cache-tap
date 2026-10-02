"""What depends on the model being from OpenAI: cache TTL and minimum cacheable prefix."""

import re

from cachetap.providers import base

FIRST_TOKEN = (b"output_text.delta", b'"delta":{"content"', b"reasoning")


def owns(model):
    return bool(base.version(model, "gpt") or re.match(r"o\d", model))


TTL_HELP = [
    {"models": "GPT-5.6 y posteriores", "ttl": "30 min (`prompt_cache_options.ttl`)", "anchor": "última escritura o lectura"},
    {"models": "GPT-5 a 5.5 y GPT-4.1", "ttl": "`in_memory`: 5–10 min, hasta 1 h · `24h`: unos 30 min, hasta 24 h", "anchor": "última actividad"},
    {"models": "GPT anteriores y serie o", "ttl": "5–10 min, hasta 1 h", "anchor": "última actividad"},
]


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


MIN_CACHEABLE_HELP = [
    {"models": "Modelos GPT", "tokens": 1024, "example": "gpt-5.6"},
]


def min_cacheable(model):
    return 1024


def effort(req):
    r = req.get("reasoning")
    return (
        (r.get("effort") if isinstance(r, dict) else None)
        or req.get("reasoning_effort")
    )


def deltas(ev):
    """Texts and stop reason carried by one streamed event."""
    if not isinstance(ev, dict):
        return [], None
    texts, stop = [], None
    d = ev.get("delta")
    if isinstance(d, str) and str(ev.get("type", "")).endswith("output_text.delta"):
        texts.append(d)
    choices = ev.get("choices")
    if not isinstance(choices, list):
        return texts, stop
    for ch in choices:
        if not isinstance(ch, dict):
            continue
        delta = ch.get("delta")
        c = delta.get("content") if isinstance(delta, dict) else None
        if isinstance(c, str):
            texts.append(c)
        reason = ch.get("finish_reason")
        if isinstance(reason, str):
            stop = reason or stop
    return texts, stop


def normalize(merged):
    inp = merged.get("input_tokens", merged.get("prompt_tokens", 0))
    inp = inp if isinstance(inp, int) and not isinstance(inp, bool) and inp >= 0 else 0
    det = merged.get("input_tokens_details") or merged.get("prompt_tokens_details") or {}
    det = det if isinstance(det, dict) else {}
    odet = merged.get("output_tokens_details") or merged.get("completion_tokens_details") or {}
    odet = odet if isinstance(odet, dict) else {}
    read = det.get("cached_tokens", 0)
    read = read if isinstance(read, int) and not isinstance(read, bool) and read >= 0 else 0
    read = min(read, inp)
    output = merged.get("output_tokens", merged.get("completion_tokens", 0))
    output = output if isinstance(output, int) and not isinstance(output, bool) and output >= 0 else 0
    reasoning = odet.get("reasoning_tokens")
    if not isinstance(reasoning, int) or isinstance(reasoning, bool) or reasoning < 0:
        reasoning = None
    return {"read": read, "write": None, "uncached": inp - read, "input_total": inp,
            "output": output, "reasoning": reasoning}
