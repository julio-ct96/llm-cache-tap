"""What each LLM provider does differently: cache lifetime, limits and wire format."""

from cachetap import config
from cachetap.providers import anthropic, openai

# the order is the order in which providers are tried
PROVIDERS = (anthropic, openai)

FIRST_TOKEN = anthropic.FIRST_TOKEN + openai.FIRST_TOKEN

DEFAULT_TTL_HELP = {"models": "Otros proveedores", "ttl": "5 min, supuesto", "anchor": "final de la petición"}

# date on which the providers' prompt caching guides were last reviewed
REVIEWED = "octubre de 2026"


def reference():
    """Help tables about cache lifetime and minimum cacheable prefix, for the dashboard."""
    ttl = [row for provider in PROVIDERS for row in provider.TTL_HELP] + [DEFAULT_TTL_HELP]
    min_cacheable_rows = [row for provider in PROVIDERS for row in provider.MIN_CACHEABLE_HELP]
    return {"ttl": ttl, "min_cacheable": min_cacheable_rows, "reviewed": REVIEWED}


def cache_ttl(req):
    """How long the provider keeps this prefix cached, and how we know.

    ttl_s is the lifetime that can be relied on; ttl_max_s, when present, is how
    long the entry may survive beyond that. ttl_anchor says whether the provider
    counts from the start or the end of the request. Sources: the prompt caching
    guides of Anthropic and OpenAI, as of October 2026.
    """
    if config.TTL_FORCED:
        return {"ttl_s": config.TTL_FORCED, "ttl_source": "forzado con TAP_TTL_S", "ttl_anchor": "end"}
    model = str(req.get("model") or "").lower()
    for provider in PROVIDERS:
        if provider.owns(model):
            return provider.cache_ttl(req, model)
    return {"ttl_s": config.TTL_S, "ttl_source": "supuesto: proveedor sin TTL conocido", "ttl_anchor": "end"}


def min_cacheable(model):
    """Shortest prefix the provider will cache, in tokens."""
    model = str(model or "").lower()
    for provider in PROVIDERS:
        if provider.owns(model):
            return provider.min_cacheable(model)
    return 1024


def written_ttl(events):
    return anthropic.written_ttl(events)


def effort_of(req):
    """Reasoning effort, judged by the shape of the message and not by the model name."""
    return anthropic.effort(req) or openai.effort(req)


def deltas(ev):
    """Texts and stop reason carried by one streamed event, whichever provider sent it."""
    a_texts, a_stop = anthropic.deltas(ev)
    o_texts, o_stop = openai.deltas(ev)
    return a_texts + o_texts, o_stop or a_stop


def normalize(events):
    """Token usage of a response, in one shape for every provider."""
    merged = {}
    for e in events:
        merged.update({k: v for k, v in e["usage"].items() if v is not None})
    if not merged:
        return None
    for provider in PROVIDERS:
        usage = provider.normalize(merged)
        if usage is not None:
            return usage
    return None
