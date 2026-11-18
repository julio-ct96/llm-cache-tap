"""mitmproxy addon for check_copilot_prices.py: keep Copilot's model billing, block every model call.

Writes to PROBE_OUT, after each change, only the `billing` object of each model returned by
GET /models and the inference calls it refused. Headers, tokens and prompts are never stored.
"""

from __future__ import annotations

import json
import os

from mitmproxy import http

INFERENCE = ("/messages", "/responses", "/chat/completions")
BILLING: dict[str, object] = {}
BLOCKED: list[str] = []


def _save() -> None:
    with open(os.environ["PROBE_OUT"], "w", encoding="utf-8") as handle:
        json.dump({"billing": BILLING, "blocked": BLOCKED}, handle, sort_keys=True)


def request(flow: http.HTTPFlow) -> None:
    path = flow.request.path.split("?", 1)[0].rstrip("/")
    if path.endswith(INFERENCE):
        BLOCKED.append(f"{flow.request.method} {flow.request.pretty_host}{path}")
        flow.response = http.Response.make(
            403, b'{"error":"blocked by local price check"}', {"content-type": "application/json"}
        )
        _save()


def response(flow: http.HTTPFlow) -> None:
    path = flow.request.path.split("?", 1)[0].rstrip("/")
    if flow.request.method != "GET" or not path.endswith("/models") or flow.response is None:
        return
    try:
        body = json.loads(flow.response.get_text() or "{}")
    except ValueError:
        return
    items = body.get("data") if isinstance(body, dict) else body
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            BILLING[item["id"]] = item.get("billing")
    _save()
