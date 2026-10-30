"""Decode and project GitHub Copilot Responses WebSocket messages."""

import json
from typing import Any, cast

from cachetap import config, record, request_body

_CLIENT_FIELDS = frozenset(
    {
        "model",
        "input",
        "instructions",
        "tools",
        "reasoning",
        "reasoning_effort",
        "tool_choice",
        "parallel_tool_calls",
        "max_output_tokens",
        "prompt_cache_options",
        "prompt_cache_retention",
        "previous_response_id",
        "stream",
        "text",
        "store",
        "include",
    }
)
_CLIENT_SIZE_ERROR = "mensaje WebSocket cliente demasiado grande"
_CLIENT_UTF8_ERROR = "mensaje WebSocket cliente no es UTF-8 válido"
_CLIENT_JSON_ERROR = "JSON WebSocket cliente no válido"
_CLIENT_OBJECT_ERROR = "mensaje WebSocket cliente debe ser un objeto"
_CLIENT_TYPE_ERROR = "type WebSocket cliente debe ser texto"
_CLIENT_PREVIOUS_ID_ERROR = "previous_response_id debe ser texto o null"
_SERVER_UTF8_ERROR = "mensaje WebSocket servidor no es UTF-8 válido"
_SERVER_JSON_ERROR = "JSON WebSocket servidor no válido"
_SERVER_OBJECT_ERROR = "mensaje WebSocket servidor debe ser un objeto"
_SERVER_TYPE_ERROR = "type WebSocket servidor debe ser texto"
_EVENT_TYPE_ERROR = "type de evento WebSocket debe ser texto"
_EVENT_RESPONSE_ERROR = "response de evento WebSocket debe ser un objeto"
_EVENT_DELTA_ERROR = "delta de evento WebSocket debe ser texto"
_EVENT_RESPONSE_ID_ERROR = "response_id de evento WebSocket debe ser texto"
_EVENT_USAGE_ERROR = "usage de evento WebSocket debe ser un objeto o null"


def _loads(content: bytes, utf8_error: str, json_error: str) -> Any:
    """Decode external bytes; Any is confined to this JSON boundary."""
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ValueError(utf8_error) from None
    try:
        decoded: Any = json.loads(text)
    except (json.JSONDecodeError, RecursionError):
        raise ValueError(json_error) from None
    return decoded


def decode_client(content: bytes) -> record.JsonObject | None:
    """Return a validated, transport-free response.create request, if applicable."""
    if len(content) > config.MAX_REQUEST_BYTES:
        raise ValueError(_CLIENT_SIZE_ERROR)

    raw = _loads(content, _CLIENT_UTF8_ERROR, _CLIENT_JSON_ERROR)
    if not isinstance(raw, dict):
        raise ValueError(_CLIENT_OBJECT_ERROR)
    message = cast(record.JsonObject, raw)
    message_type = message.get("type")
    if not isinstance(message_type, str):
        raise ValueError(_CLIENT_TYPE_ERROR)
    if message_type != "response.create":
        return None

    normalized: dict[str, record.JsonValue] = {
        key: value for key, value in message.items() if key in _CLIENT_FIELDS
    }
    previous_response_id = normalized.get("previous_response_id")
    if previous_response_id is not None and not isinstance(previous_response_id, str):
        raise ValueError(_CLIENT_PREVIOUS_ID_ERROR)

    # The parser is the common request validation boundary; nested input/tools
    # remain semantically untouched while transport-only root keys are omitted.
    return request_body.parse(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")))


def decode_server(content: bytes) -> record.JsonObject:
    """Decode one server message to a validated JSON object."""
    raw = _loads(content, _SERVER_UTF8_ERROR, _SERVER_JSON_ERROR)
    if not isinstance(raw, dict):
        raise ValueError(_SERVER_OBJECT_ERROR)
    event = cast(record.JsonObject, raw)
    if not isinstance(event.get("type"), str):
        raise ValueError(_SERVER_TYPE_ERROR)
    return event


def _response(event: record.JsonObject) -> record.JsonObject | None:
    if "response" not in event:
        return None
    response = event["response"]
    if not isinstance(response, dict):
        raise ValueError(_EVENT_RESPONSE_ERROR)
    return cast(record.JsonObject, response)


def _copy_json(value: record.JsonValue) -> record.JsonValue:
    """Copy allowed nested JSON so a projection never aliases the wire object."""
    if isinstance(value, dict):
        return {key: _copy_json(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_copy_json(child) for child in value]
    return value


def _project_response(
    event: record.JsonObject,
    *,
    include_usage: bool = False,
    id_only: bool = False,
) -> record.JsonObject | None:
    response = _response(event)
    if response is None:
        return None

    projected: record.JsonObject = {}
    response_id = response.get("id")
    if isinstance(response_id, str):
        projected["id"] = response_id
    if not id_only:
        model = response.get("model")
        if isinstance(model, str):
            projected["model"] = model
    if include_usage and "usage" in response:
        usage = response["usage"]
        if usage is not None and not isinstance(usage, dict):
            raise ValueError(_EVENT_USAGE_ERROR)
        if isinstance(usage, dict):
            projected["usage"] = _copy_json(cast(record.JsonValue, usage))
    return projected


def project_event(event: record.JsonObject) -> record.JsonObject | None:
    """Project a decoded event to fields safe and useful for response inspection."""
    event_type = event.get("type")
    if not isinstance(event_type, str):
        raise ValueError(_EVENT_TYPE_ERROR)

    if event_type in {"response.created", "response.in_progress"}:
        projected: record.JsonObject = {"type": event_type}
        response = _project_response(event)
        if response is not None:
            projected["response"] = response
        return projected

    if event_type == "response.output_text.delta":
        delta = event.get("delta")
        if not isinstance(delta, str):
            raise ValueError(_EVENT_DELTA_ERROR)
        projected = {"type": event_type, "delta": delta}
        if "response_id" in event:
            response_id = event["response_id"]
            if not isinstance(response_id, str):
                raise ValueError(_EVENT_RESPONSE_ID_ERROR)
            projected["response_id"] = response_id
        return projected

    if event_type == "response.completed":
        projected = {"type": event_type}
        response = _project_response(event, include_usage=True)
        if response is not None:
            projected["response"] = response
        return projected

    if event_type in {"response.failed", "response.incomplete", "error"}:
        projected = {"type": event_type}
        response = _project_response(event, id_only=True)
        if response is not None and "id" in response:
            projected["response"] = response
        return projected

    return None
