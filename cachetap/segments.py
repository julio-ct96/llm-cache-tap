"""Split a request into cacheable segments, fingerprint them and diff them."""

import hashlib
import json
import re
from typing import Any

from cachetap import record


def strip_cache_control(value: record.JsonValue) -> record.JsonValue:
    """Drop cache_control markers: moving a breakpoint does not change the cached content."""
    if isinstance(value, dict):
        return {
            key: strip_cache_control(item) for key, item in value.items() if key != "cache_control"
        }
    if isinstance(value, list):
        return [strip_cache_control(item) for item in value]
    return value


def dump(o: record.JsonValue) -> str:
    return json.dumps(o, sort_keys=True, ensure_ascii=False)


def digest(o: record.JsonValue) -> str:
    return hashlib.sha1(dump(strip_cache_control(o)).encode()).hexdigest()[:10]


def preview(value: record.JsonValue, limit: int = 140) -> str:
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        text = " ".join(preview(item, 80) for item in value[:4])
    elif isinstance(value, dict):
        content = value.get(
            "content", value.get("text", value.get("output", value.get("arguments")))
        )
        block_type = value.get("type", "")
        if block_type == "tool_use":
            text = f"[tool_use {value.get('name')}]"
        elif block_type == "tool_result":
            text = "[tool_result] " + preview(content, 80)
        elif block_type in ("thinking", "redacted_thinking", "reasoning"):
            text = f"[{block_type}]"
        elif isinstance(content, (list, str)):
            text = preview(content, limit)
        elif value.get("name"):
            text = f"[{block_type} {value['name']}]"
        else:
            text = dump(value)
    else:
        text = str(value)
    return re.sub(r"\s+", " ", text)[:limit]


def build_segment(
    name: str, obj: record.JsonValue, preview_text: str | None = None
) -> record.Segment:
    raw = dump(obj)
    return {
        "name": name,
        "hash": digest(obj),
        "bytes": len(raw.encode()),
        "cc": '"cache_control"' in raw,
        "preview": preview_text if preview_text is not None else preview(obj),
    }


def _tool_name(tool: record.JsonObject) -> record.JsonValue:
    name = tool.get("name")
    if name:
        return name
    function = tool.get("function")
    if isinstance(function, dict):
        function_name = function.get("name")
        if function_name:
            return function_name
    return tool.get("type", "?")


def segment_objects(request: record.JsonObject) -> list[tuple[str, record.JsonValue, str | None]]:
    """(name, object, preview) for every cacheable block of the request, in prefix order."""
    result: list[tuple[str, record.JsonValue, str | None]] = []
    tools = request.get("tools")
    if isinstance(tools, list) and tools:
        names = [_tool_name(tool) for tool in tools if isinstance(tool, dict)]
        result.append(("tools", tools, f"{len(tools)} tools: " + ", ".join(map(str, names))[:200]))
    system = request.get("system", request.get("instructions"))
    if system:
        result.append(("system", system, None))
    messages = request.get("messages") or request.get("input") or []
    if isinstance(messages, str):
        messages = [messages]
    if isinstance(messages, list):
        for index, message in enumerate(messages):
            role = (
                (message.get("role") or message.get("type") or "?")
                if isinstance(message, dict)
                else "text"
            )
            result.append((f"msg{index}:{role}", message, None))
    return result


def segments(request: record.JsonObject) -> list[record.Segment]:
    return [
        build_segment(name, obj, preview_text)
        for name, obj, preview_text in segment_objects(request)
    ]


def first_diff(
    prev_body: str | None,
    name: str,
    req: record.JsonObject,
) -> record.Diff | None:
    """Text around the first differing character of segment `name` between two requests."""
    if prev_body is None:
        return None
    try:
        # The previous request body is an external JSON decoder boundary.
        old_body: Any = json.loads(prev_body)
        old = dict((segment_name, value) for segment_name, value, _ in segment_objects(old_body))[
            name
        ]
        new = dict((segment_name, value) for segment_name, value, _ in segment_objects(req))[name]
    except (KeyError, ValueError):
        return None
    before, after = dump(strip_cache_control(old)), dump(strip_cache_control(new))
    offset = next(
        (
            index
            for index, (before_char, after_char) in enumerate(zip(before, after))
            if before_char != after_char
        ),
        min(len(before), len(after)),
    )
    context_start = max(0, offset - 200)
    return {
        "segment": name,
        "offset": offset,
        "before": before[context_start : offset + 300],
        "after": after[context_start : offset + 300],
    }
