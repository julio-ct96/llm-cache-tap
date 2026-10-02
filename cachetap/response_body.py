"""Reads usage and generated text out of a response body, JSON or SSE."""

import json

from cachetap import providers


def usage_events(body):
    events = []

    def grab(ev):
        if not isinstance(ev, dict):
            return
        for holder in (ev, ev.get("message"), ev.get("response")):
            if isinstance(holder, dict) and isinstance(holder.get("usage"), dict):
                events.append({"event": ev.get("type") or ev.get("object") or "json", "usage": holder["usage"]})
                return

    stripped = body.lstrip()
    if stripped.startswith("{"):
        try:
            grab(json.loads(stripped))
        except (json.JSONDecodeError, RecursionError):
            pass
        return events
    for line in body.splitlines():
        if line.startswith("data:") and '"usage"' in line:
            try:
                grab(json.loads(line[5:]))
            except (json.JSONDecodeError, RecursionError):
                continue
    return events


def output_text(body):
    out, stop = [], None
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
