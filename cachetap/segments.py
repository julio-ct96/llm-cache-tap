"""Split a request into cacheable segments, fingerprint them and diff them."""

import hashlib
import json
import re


def strip_cache_control(value):
    """Drop cache_control markers: moving a breakpoint does not change the cached content."""
    if isinstance(value, dict):
        return {key: strip_cache_control(item) for key, item in value.items() if key != "cache_control"}
    if isinstance(value, list):
        return [strip_cache_control(item) for item in value]
    return value


def dump(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False)


def digest(o):
    return hashlib.sha1(dump(strip_cache_control(o)).encode()).hexdigest()[:10]


def preview(value, limit=140):
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        text = " ".join(preview(item, 80) for item in value[:4])
    elif isinstance(value, dict):
        content = value.get("content", value.get("text", value.get("output", value.get("arguments"))))
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


def build_segment(name, obj, preview_text=None):
    raw = dump(obj)
    return {
        "name": name,
        "hash": digest(obj),
        "bytes": len(raw.encode()),
        "cc": '"cache_control"' in raw,
        "preview": preview_text if preview_text is not None else preview(obj),
    }


def _tool_name(tool):
    return tool.get("name") or (tool.get("function") or {}).get("name") or tool.get("type", "?")


def segment_objects(request):
    """(name, object, preview) for every cacheable block of the request, in prefix order."""
    segments = []
    tools = request.get("tools")
    if tools:
        names = [_tool_name(tool) for tool in tools if isinstance(tool, dict)]
        segments.append(("tools", tools, f"{len(tools)} tools: " + ", ".join(map(str, names))[:200]))
    system = request.get("system", request.get("instructions"))
    if system:
        segments.append(("system", system, None))
    messages = request.get("messages") or request.get("input") or []
    if isinstance(messages, str):
        messages = [messages]
    for index, message in enumerate(messages):
        role = (message.get("role") or message.get("type") or "?") if isinstance(message, dict) else "text"
        segments.append((f"msg{index}:{role}", message, None))
    return segments


def segments(request):
    return [build_segment(name, obj, preview_text) for name, obj, preview_text in segment_objects(request)]


def first_diff(prev_body, name, req):
    """Text around the first differing character of segment `name` between two requests."""
    if prev_body is None:
        return None
    try:
        old = dict((segment_name, value) for segment_name, value, _ in segment_objects(json.loads(prev_body)))[name]
        new = dict((segment_name, value) for segment_name, value, _ in segment_objects(req))[name]
    except (KeyError, ValueError):
        return None
    before, after = dump(strip_cache_control(old)), dump(strip_cache_control(new))
    offset = next((index for index, (before_char, after_char) in enumerate(zip(before, after)) if before_char != after_char), min(len(before), len(after)))
    context_start = max(0, offset - 200)
    return {
        "segment": name,
        "offset": offset,
        "before": before[context_start:offset + 300],
        "after": after[context_start:offset + 300],
    }
