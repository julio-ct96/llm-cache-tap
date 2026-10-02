"""What each LLM provider does differently: cache lifetime, limits and wire format."""

from cachetap import config
from cachetap.providers import anthropic, openai

# the order is the order in which providers are tried
PROVIDERS = (anthropic, openai)


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
