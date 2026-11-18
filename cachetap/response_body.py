"""Reads usage and generated text out of a response body, JSON or SSE."""

import json
from typing import Any

from cachetap import providers, record


def usage_events(body: str) -> list[record.UsageEvent]:
    events: list[record.UsageEvent] = []

    def grab(ev: Any) -> None:
        if not isinstance(ev, dict):
            return
        for holder in (ev, ev.get("message"), ev.get("response")):
            if not isinstance(holder, dict):
                continue
            usage = holder.get("usage", holder.get("usageMetadata"))
            if isinstance(usage, dict):
                # Any is confined to the json.loads boundary; event and usage retain wire values.
                events.append(
                    {
                        "event": ev.get("type") or ev.get("object") or "json",
                        "usage": usage,
                    }
                )
                return

    stripped = body.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(stripped)
            for event in decoded if isinstance(decoded, list) else [decoded]:
                grab(event)
        except (json.JSONDecodeError, RecursionError):
            pass
        return events
    for line in body.splitlines():
        if line.startswith("data:") and ('"usage"' in line or '"usageMetadata"' in line):
            try:
                grab(json.loads(line[5:]))
            except (json.JSONDecodeError, RecursionError):
                continue
    return events


def completed(body: str) -> bool:
    """Whether a streamed body already holds the provider's final event, such as response.completed."""
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return True
        if not any(name in data for name in providers.FINAL_EVENTS):
            continue
        try:
            event = json.loads(data)
        except (json.JSONDecodeError, RecursionError):
            continue
        if isinstance(event, dict) and event.get("type") in providers.FINAL_EVENTS:
            return True
    return False


def output_text(body: str) -> tuple[str, str | None]:
    out, stop = [], None
    if body.lstrip().startswith(("{", "[")):
        try:
            decoded = json.loads(body)
        except (json.JSONDecodeError, RecursionError):
            return "", None
        for event in decoded if isinstance(decoded, list) else [decoded]:
            if isinstance(event, dict) and "candidates" in event:
                texts, reason = providers.google.deltas(event)
                out.extend(texts)
                stop = reason or stop
        return "".join(out)[:2000], stop
    for line in body.splitlines():
        if not line.startswith("data:") or line.strip() == "data: [DONE]":
            continue
        try:
            ev = json.loads(line[5:])
        except (json.JSONDecodeError, RecursionError):
            continue
        if not isinstance(ev, dict):
            continue
        texts, reason = providers.deltas(ev)
        out.extend(texts)
        if reason:
            stop = reason
    return "".join(out)[:2000], stop
