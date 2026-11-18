"""Gemini Developer API wire format and implicit cache limits."""

import re
from typing import TypedDict

from cachetap import config, record
from cachetap.providers import base

HOST = "generativelanguage.googleapis.com"
_GENERATION = re.compile(
    r"/v1(?:beta)?/models/(gemini-[a-z0-9.-]+):(?:generateContent|streamGenerateContent)"
)
USAGE_COUNTERS = {
    "promptTokenCount",
    "cachedContentTokenCount",
    "candidatesTokenCount",
    "thoughtsTokenCount",
    "toolUsePromptTokenCount",
    "totalTokenCount",
}


class TTLHelpRow(TypedDict):
    models: str
    ttl: str
    anchor: str


class MinimumHelpRow(TypedDict):
    models: str
    tokens: int
    example: str


TTL_HELP: list[TTLHelpRow] = [
    {
        "models": "Gemini (caché implícita)",
        "ttl": "sin TTL publicado; 5 min, supuesto",
        "anchor": "final de la petición, supuesto",
    },
]
MIN_CACHEABLE_HELP: list[MinimumHelpRow] = [
    {"models": "Gemini 4, 3.8 y 3.6 Flash, 3.1 Pro", "tokens": 4096, "example": "gemini-4-carbon"},
    {"models": "Gemini 2.5 Pro y 2.5 Flash", "tokens": 2048, "example": "gemini-2.5-flash"},
]


def generation_model(host: str, path: str) -> str | None:
    match = _GENERATION.fullmatch(path.rstrip("/")) if host.lower().rstrip(".") == HOST else None
    return match[1] if match else None


def owns(model: str) -> bool:
    return model.startswith("gemini-")


def cache_ttl(req: record.JsonObject, model: str) -> record.CacheTTL:
    return {
        "ttl_s": config.TTL_S,
        "ttl_source": "supuesto: Google no publica el TTL de la caché implícita",
        "ttl_anchor": "end",
    }


def min_cacheable(model: str) -> int:
    version = base.version(model, "gemini")
    if version == (4, 0) or model.startswith(
        ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-pro")
    ):
        return 4096
    if model.startswith(("gemini-2.5-pro", "gemini-2.5-flash")) and not model.startswith(
        "gemini-2.5-flash-lite"
    ):
        return 2048
    # Google publishes no minimum for the remaining models (Flash-Lite, 3 Flash Preview)
    return 1024


def counter(value: record.JsonValue) -> int:
    return value if type(value) is int and value >= 0 else 0


def normalize(usage: record.JsonObject) -> record.Usage | None:
    prompt = usage.get("promptTokenCount")
    if type(prompt) is not int or prompt < 0:
        return None
    cached = min(counter(usage.get("cachedContentTokenCount")), prompt)
    thinking = usage.get("thoughtsTokenCount")
    reasoning = thinking if type(thinking) is int and thinking >= 0 else None
    total = prompt + counter(usage.get("toolUsePromptTokenCount"))
    return {
        "read": cached,
        "write": None,
        "uncached": total - cached,
        "input_total": total,
        "output": counter(usage.get("candidatesTokenCount")) + (reasoning or 0),
        "reasoning": reasoning,
    }


def deltas(ev: record.JsonObject) -> tuple[list[str], str | None]:
    candidates = ev.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return [], None
    candidate = candidates[0]
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    texts: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and not part.get("thought"):
                text = part.get("text")
                if isinstance(text, str):
                    texts.append(text)
    stop = candidate.get("finishReason")
    return texts, stop if isinstance(stop, str) else None
