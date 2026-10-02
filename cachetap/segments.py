"""Split a request into cacheable segments, fingerprint them and diff them."""

import hashlib
import json
import re


def strip(o):
    """Drop cache_control markers: moving a breakpoint does not change the cached content."""
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k != "cache_control"}
    if isinstance(o, list):
        return [strip(x) for x in o]
    return o


def dump(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False)


def digest(o):
    return hashlib.sha1(dump(strip(o)).encode()).hexdigest()[:10]


def preview(o, n=140):
    if isinstance(o, str):
        t = o
    elif isinstance(o, list):
        t = " ".join(preview(x, 80) for x in o[:4])
    elif isinstance(o, dict):
        c = o.get("content", o.get("text", o.get("output", o.get("arguments"))))
        ty = o.get("type", "")
        if ty == "tool_use":
            t = f"[tool_use {o.get('name')}]"
        elif ty == "tool_result":
            t = "[tool_result] " + preview(c, 80)
        elif ty in ("thinking", "redacted_thinking", "reasoning"):
            t = f"[{ty}]"
        elif isinstance(c, (list, str)):
            t = preview(c, n)
        elif o.get("name"):
            t = f"[{ty} {o['name']}]"
        else:
            t = dump(o)
    else:
        t = str(o)
    return re.sub(r"\s+", " ", t)[:n]


def seg(name, obj, prev=None):
    raw = dump(obj)
    return {
        "name": name,
        "hash": digest(obj),
        "bytes": len(raw.encode()),
        "cc": '"cache_control"' in raw,
        "preview": prev if prev is not None else preview(obj),
    }


def seg_objs(req):
    """(name, object, preview) for every cacheable block of the request, in prefix order."""
    out = []
    tools = req.get("tools")
    if tools:
        names = [t.get("name") or (t.get("function") or {}).get("name") or t.get("type", "?") for t in tools if isinstance(t, dict)]
        out.append(("tools", tools, f"{len(tools)} tools: " + ", ".join(map(str, names))[:200]))
    system = req.get("system", req.get("instructions"))
    if system:
        out.append(("system", system, None))
    msgs = req.get("messages") or req.get("input") or []
    if isinstance(msgs, str):
        msgs = [msgs]
    for i, m in enumerate(msgs):
        role = (m.get("role") or m.get("type") or "?") if isinstance(m, dict) else "text"
        out.append((f"msg{i}:{role}", m, None))
    return out


def segments(req):
    return [seg(name, obj, prev) for name, obj, prev in seg_objs(req)]


def first_diff(prev_body, name, req):
    """Text around the first differing character of segment `name` between two requests."""
    if prev_body is None:
        return None
    try:
        old = dict((n, o) for n, o, _ in seg_objs(json.loads(prev_body)))[name]
        new = dict((n, o) for n, o, _ in seg_objs(req))[name]
    except (KeyError, ValueError):
        return None
    a, b = dump(strip(old)), dump(strip(new))
    i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    lo = max(0, i - 200)
    return {"segment": name, "offset": i, "before": a[lo:i + 300], "after": b[lo:i + 300]}
