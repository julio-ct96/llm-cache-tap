"""Decode and project GitHub Copilot Responses WebSocket messages."""

import json
import logging
from dataclasses import dataclass
from typing import Any, cast

from cachetap import capture, config, record, request_body

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
_CLOSE_ERROR = "conexión WebSocket cerrada antes de completar la respuesta"


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


@dataclass
class _ActiveCapture:
    rid: int
    state: capture.StreamState
    client_at: float
    response_id: str | None = None
    server_bytes: int = 0


class Session:
    """Inspect sequential Responses requests on one WebSocket connection."""

    def __init__(self, host: str, path: str, logger: logging.Logger) -> None:
        self.host = host
        self.path = path
        self.logger = logger
        self._active: _ActiveCapture | None = None
        self._last_response_id: str | None = None

    def client(self, content: bytes, at: float) -> None:
        """Start one capture for a validated response.create message."""
        if self._active is not None:
            return

        req = decode_client(content)
        if req is None:
            return

        text = json.dumps(req, ensure_ascii=False, separators=(",", ":"))
        previous_response_id = req.get("previous_response_id")
        context_partial = isinstance(previous_response_id, str) and bool(previous_response_id)
        rid = capture.begin(
            req,
            text,
            self.host,
            self.path,
            len(content),
            at,
            transport="websocket",
            context_partial=context_partial,
        )
        state = capture.start(rid, 101, {}, at, None)
        self._active = _ActiveCapture(rid, state, at)

    def server(self, content: bytes, at: float) -> None:
        """Feed sanitized server projections and finish the matching response."""
        active = self._active
        if active is None:
            return

        # Count wire bytes before decoding/projection; no event history is kept.
        active.server_bytes += len(content)
        event = decode_server(content)
        projected = project_event(event)
        if projected is None:
            return

        event_type = projected.get("type")
        if not isinstance(event_type, str):
            return
        response_id = self._projected_response_id(projected)

        if event_type == "response.completed" and response_id == self._last_response_id:
            return

        if event_type == "response.created":
            if response_id is None:
                return
            if active.response_id is not None and response_id != active.response_id:
                return
            active.response_id = response_id
        elif active.response_id is None:
            return
        elif response_id is not None:
            if response_id != active.response_id:
                return

        if event_type == "response.completed":
            if active.response_id is None or response_id != active.response_id:
                return

        if event_type == "response.output_text.delta" and projected.get("delta") == "":
            return

        data = json.dumps(projected, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        capture.feed(active.rid, active.state, b"data: " + data + b"\n\n", at=at)

        if event_type == "response.completed":
            self._active = None
            self._last_response_id = active.response_id
            capture.finish(
                active.rid,
                active.state,
                101,
                active.client_at,
                self.logger,
                ended_at=at,
            )

    @staticmethod
    def _projected_response_id(event: record.JsonObject) -> str | None:
        response_id = event.get("response_id")
        if isinstance(response_id, str):
            return response_id
        response = event.get("response")
        if isinstance(response, dict):
            response_id = response.get("id")
            if isinstance(response_id, str):
                return response_id
        return None

    def close(self, at: float | None = None) -> None:
        """Fail and release an unfinished capture; safe to call repeatedly."""
        active = self._active
        self._active = None
        self._last_response_id = None
        if active is not None:
            capture.fail(active.rid, active.state, _CLOSE_ERROR, ended_at=at)
