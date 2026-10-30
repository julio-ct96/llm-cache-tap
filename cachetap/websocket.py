"""Decode and project GitHub Copilot Responses WebSocket messages."""

import json
import logging
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, cast

from cachetap import capture, config, record, request_body, store

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
_CLIENT_UNICODE_ERROR = "JSON WebSocket cliente contiene Unicode no válido"
_SERVER_UTF8_ERROR = "mensaje WebSocket servidor no es UTF-8 válido"
_SERVER_JSON_ERROR = "JSON WebSocket servidor no válido"
_SERVER_OBJECT_ERROR = "mensaje WebSocket servidor debe ser un objeto"
_SERVER_TYPE_ERROR = "type WebSocket servidor debe ser texto"
_EVENT_TYPE_ERROR = "type de evento WebSocket debe ser texto"
_EVENT_RESPONSE_ERROR = "response de evento WebSocket debe ser un objeto"
_EVENT_DELTA_ERROR = "delta de evento WebSocket debe ser texto"
_EVENT_RESPONSE_ID_ERROR = "response_id de evento WebSocket debe ser texto"
_EVENT_USAGE_ERROR = "usage de evento WebSocket debe ser un objeto o null"
_EVENT_UNICODE_ERROR = "evento WebSocket contiene Unicode no válido"
_CLOSE_ERROR = "conexión WebSocket cerrada antes de completar la respuesta"
_OVERLAP_ERROR = "captura WebSocket interrumpida: peticiones solapadas"
_UNINSPECTABLE_ERROR = "evento WebSocket no inspeccionable"
_INTERNAL_ERROR = "error interno al inspeccionar WebSocket"
_CLIENT_WARNING = "Petición WebSocket no inspeccionable"
_FAILURE_ERRORS = {
    "response.failed": "respuesta WebSocket fallida",
    "response.incomplete": "respuesta WebSocket incompleta",
    "error": "error del protocolo WebSocket",
}
_TERMINAL_ERRORS = frozenset(_FAILURE_ERRORS)
_DIAGNOSTIC_EVENT_LIMIT = 32
_DIAGNOSTIC_OMITTED_LIMIT = 255
_DIAGNOSTIC_ID_SYMBOL_LIMIT = 32


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


@dataclass(frozen=True)
class _ClientMessage:
    request: record.JsonObject | None
    generate: record.WebSocketGenerate


def _decode_client_message(content: bytes) -> _ClientMessage:
    """Return the normalized request and safe create metadata from one parse."""
    if len(content) > config.MAX_REQUEST_BYTES:
        raise ValueError(_CLIENT_SIZE_ERROR)

    raw = _loads(content, _CLIENT_UTF8_ERROR, _CLIENT_JSON_ERROR)
    if not isinstance(raw, dict):
        raise ValueError(_CLIENT_OBJECT_ERROR)
    message = cast(record.JsonObject, raw)
    message_type = message.get("type")
    if not isinstance(message_type, str):
        raise ValueError(_CLIENT_TYPE_ERROR)
    generate_value = message.get("generate")
    if "generate" not in message:
        generate: record.WebSocketGenerate = "absent"
    elif generate_value is True:
        generate = "true"
    elif generate_value is False:
        generate = "false"
    else:
        generate = "invalid"
    if message_type != "response.create":
        return _ClientMessage(None, generate)

    normalized: dict[str, record.JsonValue] = {
        key: value for key, value in message.items() if key in _CLIENT_FIELDS
    }
    previous_response_id = normalized.get("previous_response_id")
    if previous_response_id is not None and not isinstance(previous_response_id, str):
        raise ValueError(_CLIENT_PREVIOUS_ID_ERROR)

    # The parser is the common request validation boundary; nested input/tools
    # remain semantically untouched while transport-only root keys are omitted.
    try:
        normalized_text = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        normalized_text.encode("utf-8")
        return _ClientMessage(request_body.parse(normalized_text), generate)
    except UnicodeEncodeError:
        raise ValueError(_CLIENT_UNICODE_ERROR) from None
    except RecursionError:
        raise ValueError(_CLIENT_JSON_ERROR) from None


def decode_client(content: bytes) -> record.JsonObject | None:
    """Return a validated, transport-free response.create request, if applicable."""
    return _decode_client_message(content).request


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
            try:
                projected["usage"] = _copy_json(cast(record.JsonValue, usage))
            except RecursionError:
                raise ValueError(_EVENT_USAGE_ERROR) from None
    return projected


def _encode_projection(event: record.JsonObject) -> bytes:
    """Encode a sanitized event, translating unrepresentable external JSON."""
    try:
        return json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(_EVENT_UNICODE_ERROR) from None
    except RecursionError:
        raise ValueError(_SERVER_JSON_ERROR) from None


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
        if "response_id" in event:
            response_id = event["response_id"]
            if not isinstance(response_id, str):
                raise ValueError(_EVENT_RESPONSE_ID_ERROR)
            projected["response_id"] = response_id
        return projected

    return None


@dataclass
class _ActiveCapture:
    rid: int
    state: capture.StreamState
    client_at: float
    response_id: str | None = None
    server_bytes: int = 0
    diagnostic_events: deque[record.WebSocketDiagnosticStep] = field(
        default_factory=lambda: deque(maxlen=_DIAGNOSTIC_EVENT_LIMIT)
    )
    id_symbols: dict[str, int] = field(default_factory=dict)
    diagnostic_truncated: bool = False
    omitted_server_events: int = 0


def _id_relation(
    active: _ActiveCapture,
    response_id: str | None,
    last_response_id: str | None,
) -> record.WebSocketIdRelation:
    if response_id is None:
        return "missing"
    if last_response_id is not None and response_id == last_response_id:
        return "last"
    if active.response_id is None:
        return "unbound"
    if response_id == active.response_id:
        return "active"
    return "other"


def _append_diagnostic_step(
    active: _ActiveCapture,
    direction: record.WebSocketDirection,
    event: record.WebSocketControlEvent,
    action: record.WebSocketAction,
    *,
    response_id: str | None = None,
    last_response_id: str | None = None,
    identified: bool | None = None,
    id_relation: record.WebSocketIdRelation | None = None,
    generate: record.WebSocketGenerate | None = None,
    incremental: bool | None = None,
    id_symbol: int | None = None,
) -> None:
    step: record.WebSocketDiagnosticStep = {
        "direction": direction,
        "event": event,
        "action": action,
        "identified": active.response_id is not None if identified is None else identified,
        "id_relation": id_relation
        if id_relation is not None
        else _id_relation(active, response_id, last_response_id),
    }
    if generate is not None:
        step["generate"] = generate
    if incremental is not None:
        step["incremental"] = incremental
    if id_symbol is not None:
        step["id_symbol"] = id_symbol
    if len(active.diagnostic_events) == _DIAGNOSTIC_EVENT_LIMIT:
        active.diagnostic_truncated = True
    active.diagnostic_events.append(step)


def _omit_server_event(active: _ActiveCapture) -> None:
    active.omitted_server_events = min(_DIAGNOSTIC_OMITTED_LIMIT, active.omitted_server_events + 1)


def _diagnostic_copy(active: _ActiveCapture) -> record.WebSocketDiagnostic:
    return {
        "events": [
            cast(record.WebSocketDiagnosticStep, dict(step)) for step in active.diagnostic_events
        ],
        "truncated": active.diagnostic_truncated,
        "omitted_server_events": active.omitted_server_events,
    }


def _clear_diagnostic(active: _ActiveCapture) -> None:
    active.diagnostic_events.clear()
    active.id_symbols.clear()
    active.diagnostic_truncated = False
    active.omitted_server_events = 0


def _append_server_diagnostic_step(
    active: _ActiveCapture,
    event_type: str,
    action: record.WebSocketAction,
    *,
    identified: bool,
    id_relation: record.WebSocketIdRelation,
    response_id: str | None = None,
) -> None:
    if event_type == "response.output_text.delta":
        return
    id_symbol = None
    if response_id is not None:
        id_symbol = active.id_symbols.get(response_id)
        if id_symbol is None and len(active.id_symbols) < _DIAGNOSTIC_ID_SYMBOL_LIMIT:
            id_symbol = len(active.id_symbols) + 1
            active.id_symbols[response_id] = id_symbol
    _append_diagnostic_step(
        active,
        "server",
        cast(record.WebSocketControlEvent, event_type),
        action,
        identified=identified,
        id_relation=id_relation,
        id_symbol=id_symbol,
    )


class Session:
    """Inspect sequential Responses requests on one WebSocket connection."""

    def __init__(self, host: str, path: str, logger: logging.Logger) -> None:
        self.host = host
        self.path = path
        self.logger = logger
        self._active: _ActiveCapture | None = None
        self._last_response_id: str | None = None
        self._disabled = False

    def _disable(self) -> None:
        self._disabled = True
        self._last_response_id = None

    @contextmanager
    def _guard(
        self,
        at: float,
        active: _ActiveCapture | None = None,
        *,
        rid: int | None = None,
    ) -> Iterator[None]:
        """Clean a failed operation once; terminal committed results are immutable."""
        try:
            yield
        except BaseException as original:
            self._disable()
            target = active
            if target is None and self._active is not None:
                if rid is None or self._active.rid == rid:
                    target = self._active

            if target is not None:
                if self._active is target:
                    self._active = None
                try:
                    if not target.state["committed"]:
                        self._attach_diagnostic(target)
                        capture.fail(
                            target.rid,
                            target.state,
                            _INTERNAL_ERROR,
                            ended_at=at,
                        )
                except BaseException as cleanup_error:
                    self._release(target)
                    raise original from cleanup_error
                self._release(target)
            elif rid is not None:
                try:
                    capture.fail(rid, None, _INTERNAL_ERROR, ended_at=at)
                except BaseException as cleanup_error:
                    with store.LOCK:
                        store.end_capture(rid)
                    raise original from cleanup_error
                with store.LOCK:
                    store.end_capture(rid)
            raise

    @staticmethod
    def _release(active: _ActiveCapture) -> None:
        """Release local and shared capture state without publishing anything."""
        state = active.state
        state["closed"] = True
        try:
            with store.LOCK:
                if state["reserved"]:
                    store.end_capture(active.rid)
                    state["reserved"] = False
        finally:
            state["chunks"].clear()
            state["bytes"] = 0
            state["first"] = None
            active.server_bytes = 0
            _clear_diagnostic(active)

    def _abandon(self, active: _ActiveCapture) -> None:
        """Forget a cleared or evicted record without resuscitating it."""
        if self._active is active:
            self._active = None
        self._disable()
        self._release(active)

    def _active_if_present(self) -> _ActiveCapture | None:
        active = self._active
        if active is None:
            return None
        with store.LOCK:
            present = active.rid in store.RECORDS
        if not present:
            self._abandon(active)
            return None
        return active

    def _fail_active(self, active: _ActiveCapture, message: str, at: float | None) -> None:
        self._disable()
        if self._active is active:
            self._active = None
        try:
            self._attach_diagnostic(active)
            capture.fail(active.rid, active.state, message, ended_at=at)
        finally:
            self._release(active)

    @staticmethod
    def _attach_diagnostic(active: _ActiveCapture) -> None:
        diagnostic = _diagnostic_copy(active)
        with store.LOCK:
            if active.state["committed"]:
                return
            rec = store.RECORDS.get(active.rid)
            if rec is not None:
                rec["ws_diagnostic"] = diagnostic

    def _finish_limited(self, active: _ActiveCapture, at: float) -> None:
        self._disable()
        capture.finish(
            active.rid,
            active.state,
            101,
            active.client_at,
            self.logger,
            ended_at=at,
        )
        self._release(active)
        if self._active is active:
            self._active = None

    def client(self, content: bytes, at: float) -> None:
        """Start one capture for a validated response.create message."""
        if self._disabled:
            return

        active = self._active_if_present()
        if self._disabled:
            return

        if active is not None:
            with self._guard(at, active):
                try:
                    message = _decode_client_message(content)
                except ValueError:
                    self.logger.warning(_CLIENT_WARNING)
                    _append_diagnostic_step(
                        active,
                        "client",
                        "invalid",
                        "fail",
                        id_relation="missing",
                    )
                    self._fail_active(active, _UNINSPECTABLE_ERROR, at)
                    return
                if message.request is not None:
                    previous_response_id = message.request.get("previous_response_id")
                    incremental = isinstance(previous_response_id, str) and bool(
                        previous_response_id
                    )
                    _append_diagnostic_step(
                        active,
                        "client",
                        "response.create",
                        "overlap",
                        id_relation="missing",
                        generate=message.generate,
                        incremental=incremental,
                    )
                    self._fail_active(active, _OVERLAP_ERROR, at)
            return

        with self._guard(at):
            try:
                message = _decode_client_message(content)
            except ValueError:
                self.logger.warning(_CLIENT_WARNING)
                self._disable()
                return
        req = message.request
        if req is None:
            return

        text = json.dumps(req, ensure_ascii=False, separators=(",", ":"))
        previous_response_id = req.get("previous_response_id")
        context_partial = isinstance(previous_response_id, str) and bool(previous_response_id)
        with self._guard(at):
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

        with self._guard(at, rid=rid):
            state = capture.start(rid, 101, {}, at, None)
            active = _ActiveCapture(rid, state, at)
            self._active = active
            _append_diagnostic_step(
                active,
                "client",
                "response.create",
                "start",
                id_relation="missing",
                identified=False,
                generate=message.generate,
                incremental=context_partial,
            )
            if state["limited"] is not None:
                self._finish_limited(active, at)

    def server(self, content: bytes, at: float) -> None:
        """Feed sanitized server projections and finish the matching response."""
        if self._disabled:
            return
        active = self._active_if_present()
        if active is None:
            return

        with self._guard(at, active):
            # Count wire bytes before decoding/projection; no event history is kept.
            active.server_bytes += len(content)
            if active.server_bytes > config.MAX_RESPONSE_BYTES:
                capture.limit(active.rid, active.state, "response_size")
                self._finish_limited(active, at)
                return

            self._process_server_message(active, content, at)

    def _process_server_message(self, active: _ActiveCapture, content: bytes, at: float) -> None:
        try:
            event = decode_server(content)
            projected = project_event(event)
        except ValueError:
            _append_diagnostic_step(
                active,
                "server",
                "invalid",
                "fail",
                id_relation="missing",
            )
            self._fail_active(active, _UNINSPECTABLE_ERROR, at)
            return

        if projected is None:
            _omit_server_event(active)
            return

        event_type = projected.get("type")
        if not isinstance(event_type, str):
            raise RuntimeError("projected WebSocket event has no type")
        response_id = self._projected_response_id(projected)
        identified_before = active.response_id is not None
        relation_before = _id_relation(active, response_id, self._last_response_id)

        if event_type == "response.output_text.delta":
            _omit_server_event(active)

        if (
            event_type in _TERMINAL_ERRORS | {"response.completed"}
            and response_id is not None
            and response_id == self._last_response_id
        ):
            _append_server_diagnostic_step(
                active,
                event_type,
                "ignore_previous",
                identified=identified_before,
                id_relation=relation_before,
                response_id=response_id,
            )
            return

        if event_type in _FAILURE_ERRORS:
            if (
                active.response_id is not None
                and response_id is not None
                and response_id != active.response_id
            ):
                _append_server_diagnostic_step(
                    active,
                    event_type,
                    "ignore_other_id",
                    identified=identified_before,
                    id_relation=relation_before,
                    response_id=response_id,
                )
                return
            _append_server_diagnostic_step(
                active,
                event_type,
                "fail",
                identified=identified_before,
                id_relation=relation_before,
                response_id=response_id,
            )
            self._fail_active(active, _FAILURE_ERRORS[event_type], at)
            return

        if event_type == "response.created":
            if response_id is None:
                _append_server_diagnostic_step(
                    active,
                    event_type,
                    "ignore_no_id",
                    identified=identified_before,
                    id_relation=relation_before,
                    response_id=response_id,
                )
                return
            if active.response_id is not None and response_id != active.response_id:
                _append_server_diagnostic_step(
                    active,
                    event_type,
                    "ignore_other_id",
                    identified=identified_before,
                    id_relation=relation_before,
                    response_id=response_id,
                )
                return
            active.response_id = response_id
        elif active.response_id is None:
            _append_server_diagnostic_step(
                active,
                event_type,
                "ignore_no_id",
                identified=identified_before,
                id_relation=relation_before,
                response_id=response_id,
            )
            return
        elif response_id is not None:
            if response_id != active.response_id:
                _append_server_diagnostic_step(
                    active,
                    event_type,
                    "ignore_other_id",
                    identified=identified_before,
                    id_relation=relation_before,
                    response_id=response_id,
                )
                return

        if event_type == "response.completed":
            if active.response_id is None or response_id != active.response_id:
                _append_server_diagnostic_step(
                    active,
                    event_type,
                    "ignore_no_id",
                    identified=identified_before,
                    id_relation=relation_before,
                    response_id=response_id,
                )
                return

        if event_type == "response.output_text.delta" and projected.get("delta") == "":
            return

        try:
            data = _encode_projection(projected)
        except ValueError:
            _append_diagnostic_step(
                active,
                "server",
                "invalid",
                "fail",
                identified=identified_before,
                id_relation=relation_before,
            )
            self._fail_active(active, _UNINSPECTABLE_ERROR, at)
            return
        _append_server_diagnostic_step(
            active,
            event_type,
            "finish" if event_type == "response.completed" else "observe",
            identified=identified_before,
            id_relation=relation_before,
            response_id=response_id,
        )
        capture.feed(active.rid, active.state, b"data: " + data + b"\n\n", at=at)
        if active.state["limited"] is not None:
            self._finish_limited(active, at)
            return

        if event_type == "response.completed":
            capture.finish(
                active.rid,
                active.state,
                101,
                active.client_at,
                self.logger,
                ended_at=at,
            )
            self._active = None
            self._last_response_id = active.response_id
            _clear_diagnostic(active)

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
        if self._disabled and self._active is None:
            return
        active = self._active_if_present()
        self._disable()
        if active is not None:
            with self._guard(at if at is not None else active.client_at, active):
                _append_diagnostic_step(
                    active,
                    "local",
                    "close",
                    "fail",
                    id_relation="missing",
                )
                self._fail_active(active, _CLOSE_ERROR, at)

    def uninspectable(self, at: float) -> None:
        """Fail an active capture when the transport message is not text."""
        if self._disabled:
            return
        active = self._active_if_present()
        if active is None:
            return
        with self._guard(at, active):
            _append_diagnostic_step(
                active,
                "local",
                "uninspectable",
                "fail",
                id_relation="missing",
            )
            self._fail_active(active, _UNINSPECTABLE_ERROR, at)
