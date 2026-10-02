"""What each LLM provider does differently: cache lifetime, limits and wire format."""

from typing import TypedDict

from cachetap import config
from cachetap import record
from cachetap.providers import anthropic, openai


# the order is the order in which providers are tried
PROVIDERS = (anthropic, openai)

FIRST_TOKEN = anthropic.FIRST_TOKEN + openai.FIRST_TOKEN

class Reference(TypedDict):
    ttl: list[anthropic.TTLHelpRow]
    min_cacheable: list[anthropic.MinimumHelpRow]
    reviewed: str


DEFAULT_TTL_HELP: anthropic.TTLHelpRow = {
    "models": "Otros proveedores",
    "ttl": "5 min, supuesto",
    "anchor": "final de la petición",
}

# date on which the providers' prompt caching guides were last reviewed
REVIEWED = "octubre de 2026"


def reference() -> Reference:
    """Help tables about cache lifetime and minimum cacheable prefix, for the dashboard."""
    ttl = [row for provider in PROVIDERS for row in provider.TTL_HELP] + [DEFAULT_TTL_HELP]
    min_cacheable_rows = [row for provider in PROVIDERS for row in provider.MIN_CACHEABLE_HELP]
    return {"ttl": ttl, "min_cacheable": min_cacheable_rows, "reviewed": REVIEWED}


def cache_ttl(req: record.JsonObject) -> record.CacheTTL:
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


def min_cacheable(model: str | None) -> int:
    """Shortest prefix the provider will cache, in tokens."""
    model = str(model or "").lower()
    for provider in PROVIDERS:
        if provider.owns(model):
            return provider.min_cacheable(model)
    return 1024


def written_ttl(events: list[record.UsageEvent]) -> int | None:
    return anthropic.written_ttl(events)


def effort_of(req: record.JsonObject) -> str | None:
    """Reasoning effort, judged by the shape of the message and not by the model name."""
    return anthropic.effort(req) or openai.effort(req)


def deltas(ev: record.JsonObject) -> tuple[list[str], str | None]:
    """Texts and stop reason carried by one streamed event, whichever provider sent it."""
    if not isinstance(ev, dict):
        return [], None
    a_texts, a_stop = anthropic.deltas(ev)
    o_texts, o_stop = openai.deltas(ev)
    return a_texts + o_texts, o_stop or a_stop


def normalize(events: list[record.UsageEvent]) -> record.Usage | None:
    """Token usage of a response, in one shape for every provider."""
    merged: record.JsonObject = {}
    counters = {
        "input_tokens", "prompt_tokens", "output_tokens", "completion_tokens",
        "cache_read_input_tokens", "cache_creation_input_tokens", "cached_tokens",
        "reasoning_tokens",
    }
    for e in events:
        if not isinstance(e, dict) or not isinstance(e.get("usage"), dict):
            continue
        usage = e["usage"]
        for key, value in usage.items():
            if key in counters and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                continue
            if key in ("input_tokens_details", "prompt_tokens_details", "output_tokens_details", "completion_tokens_details"):
                if not isinstance(value, dict):
                    continue
                value = {
                    detail_key: detail_value
                    for detail_key, detail_value in value.items()
                    if detail_key not in {"cached_tokens", "reasoning_tokens"}
                    or (
                        isinstance(detail_value, int)
                        and not isinstance(detail_value, bool)
                        and detail_value >= 0
                    )
                }
            if value is not None:
                merged[key] = value
    if not merged:
        return None
    for provider in PROVIDERS:
        usage = provider.normalize(merged)
        if usage is not None:
            return usage
    return None
