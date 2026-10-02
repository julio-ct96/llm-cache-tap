"""Parse and validate request bodies before they reach cache inspection."""

import json


MAX_CONTAINER_DEPTH = 100


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _optional_type(req, key, expected, reason):
    value = req.get(key)
    _require(value is None or isinstance(value, expected), reason)


def _validate_effort_container(req, key):
    value = req.get(key)
    _require(value is None or isinstance(value, dict), f"{key} debe ser un objeto o null")
    if isinstance(value, dict):
        effort = value.get("effort")
        _require(effort is None or isinstance(effort, str), f"{key}.effort debe ser texto o null")


def _validate_tree(root):
    stack = [(root, 1)]
    while stack:
        value, depth = stack.pop()
        if isinstance(value, dict):
            _require(depth <= MAX_CONTAINER_DEPTH, "profundidad JSON superior a 100 contenedores")
            cache_control = value.get("cache_control")
            if isinstance(cache_control, dict):
                ttl = cache_control.get("ttl")
                _require(ttl is None or isinstance(ttl, str), "cache_control.ttl debe ser texto o null")
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            _require(depth <= MAX_CONTAINER_DEPTH, "profundidad JSON superior a 100 contenedores")
            stack.extend((child, depth + 1) for child in value)


def parse(text):
    """Return an inspectable request object or raise ValueError with a fixed reason."""
    try:
        req = json.loads(text)
    except json.JSONDecodeError:
        return {}
    except RecursionError as exc:
        raise ValueError("JSON demasiado profundo para inspeccionar") from exc

    _require(isinstance(req, dict), "la raíz JSON debe ser un objeto")
    _optional_type(req, "model", str, "model debe ser texto o null")

    tools = req.get("tools")
    _require(tools is None or isinstance(tools, list), "tools debe ser una lista de objetos o null")
    if isinstance(tools, list):
        _require(all(isinstance(tool, dict) for tool in tools), "tools debe ser una lista de objetos o null")

    _optional_type(req, "messages", list, "messages debe ser una lista o null")
    _optional_type(req, "input", (str, list), "input debe ser texto, una lista o null")
    _validate_effort_container(req, "output_config")
    _validate_effort_container(req, "reasoning")
    _optional_type(req, "reasoning_effort", str, "reasoning_effort debe ser texto o null")
    _validate_tree(req)
    return req
