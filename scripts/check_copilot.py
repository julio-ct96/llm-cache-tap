"""Opt-in, single-prompt smoke check for the local Copilot CLI."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import AbstractContextManager, contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterator, Literal, NoReturn, NotRequired, Protocol, TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]
READY = "READY: no model calls; use --run-real"
FORBIDDEN_PORTS = {8899, 8900}
PROXY_READY_SECONDS = 10.0
CLI_TIMEOUT_SECONDS = 90.0
TERMINATE_SECONDS = 5.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_USAGE_BYTES = 2 * 1024 * 1024
MAX_RECORD_FAILURE_BYTES = 8192
MODEL_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
ALLOWED_VERDICTS = {"HIT", "PARTIAL", "MISS", "N/A", "COLD"}

FailureTransport = Literal["websocket", "http", "unknown"]
FailureState = Literal["pending", "streaming", "done", "error", "unknown"]
FailureVerdict = Literal["HIT", "PARTIAL", "MISS", "COLD", "N/A", "ERR", "unknown"]
FailureReason = Literal[
    "overlap",
    "closed_before_completed",
    "response_failed",
    "response_incomplete",
    "protocol_error",
    "uninspectable",
    "internal_error",
    "response_size_limit",
    "active_capture_limit",
    "unknown",
]
FailureDirection = Literal["client", "server", "local"]
FailureEvent = Literal[
    "response.create",
    "response.created",
    "response.in_progress",
    "response.completed",
    "response.failed",
    "response.incomplete",
    "error",
    "invalid",
    "close",
    "uninspectable",
]
FailureAction = Literal[
    "start",
    "observe",
    "ignore_no_id",
    "ignore_other_id",
    "ignore_previous",
    "finish",
    "fail",
    "overlap",
]
FailureIdRelation = Literal["missing", "last", "unbound", "active", "other"]
FailureGenerate = Literal["absent", "true", "false", "invalid"]


class FailureDiagnosticStep(TypedDict):
    direction: FailureDirection
    event: FailureEvent
    action: FailureAction
    identified: bool
    id_relation: FailureIdRelation
    generate: NotRequired[FailureGenerate]
    incremental: NotRequired[bool]


class FailureWebSocketDiagnostic(TypedDict):
    events: list[FailureDiagnosticStep]
    truncated: bool
    omitted_server_events: int


class RecordFailureDiagnostic(TypedDict):
    transport: FailureTransport
    status: int | None
    state: FailureState
    verdict: FailureVerdict
    reason: FailureReason
    ws_diagnostic: FailureWebSocketDiagnostic | None


Verdict = Literal["HIT", "PARTIAL", "MISS", "N/A", "COLD"]


class SnapshotRow(TypedDict):
    id: int
    transport: NotRequired[str]


class SnapshotData(TypedDict):
    type: Literal["snapshot"]
    recs: list[SnapshotRow]


class UsageCounters(TypedDict):
    read: int
    write: int
    output: int
    input_total: int


class CompletedRecord(TypedDict):
    id: int
    transport: Literal["websocket"]
    status: Literal[101]
    state: Literal["done"]
    model: str
    usage: UsageCounters
    verdict: Verdict


class ModelRequests(TypedDict):
    count: int
    cost: int | float


class ModelUsage(TypedDict):
    inputTokens: int
    outputTokens: int
    cacheReadTokens: int
    cacheWriteTokens: int
    reasoningTokens: int


class TokenCount(TypedDict):
    tokenCount: int


class TokenDetails(TypedDict):
    input: TokenCount
    cache_read: TokenCount
    cache_write: TokenCount
    output: TokenCount


class ModelMetrics(TypedDict):
    requests: ModelRequests
    usage: ModelUsage
    tokenDetails: TokenDetails


class CLIUsage(TypedDict):
    modelMetrics: dict[str, ModelMetrics]
    totalNanoAiu: NotRequired[int]


class SmokeSummary(TypedDict):
    requests: Literal[1]
    model: str
    read: int
    write: int
    output: int
    input_total: int
    verdict: Verdict
    credits_reported: NotRequired[Decimal]


class RunnerError(Exception):
    """An expected runner failure safe to show without subprocess output."""


class HTTPResponse(Protocol):
    def __enter__(self) -> HTTPResponse: ...

    def __exit__(self, *args: object) -> object: ...

    def read(self, amount: int = -1) -> bytes: ...

    def readline(self, limit: int = -1) -> bytes: ...


class ManagedProcess(Protocol):
    pid: int
    returncode: int | None

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


HTTPOpen = Callable[..., HTTPResponse]
Popen = Callable[..., ManagedProcess]
Clock = Callable[[], float]
Sleep = Callable[[float], None]
KillGroup = Callable[[int, int], None]
GroupExists = Callable[[int], bool]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-real",
        action="store_true",
        help="send exactly one prompt to the authenticated Copilot CLI",
    )
    parser.add_argument("--copilot", help="path to the Copilot CLI executable")
    return parser


def find_copilot(argument: str | None) -> Path:
    if argument:
        candidate = Path(argument).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
        raise RunnerError("Copilot executable is missing or not executable")

    in_path = shutil.which("copilot")
    if in_path:
        return Path(in_path).resolve()

    local = Path.home() / ".local" / "bin" / "copilot"
    if local.is_file() and os.access(local, os.X_OK):
        return local.resolve()
    raise RunnerError("Copilot executable was not found")


def reserve_ports() -> tuple[list[socket.socket], tuple[int, int]]:
    """Reserve two distinct loopback ports until immediately before mitmdump."""
    reservations: list[socket.socket] = []
    ports: list[int] = []
    try:
        for _ in range(2):
            for _attempt in range(32):
                reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    reservation.bind(("127.0.0.1", 0))
                except OSError:
                    reservation.close()
                    raise
                port = int(reservation.getsockname()[1])
                if port in FORBIDDEN_PORTS or port in ports:
                    reservation.close()
                    continue
                reservations.append(reservation)
                ports.append(port)
                break
            else:
                raise RunnerError("could not reserve two safe loopback ports")
        return reservations, (ports[0], ports[1])
    except BaseException:
        for reservation in reservations:
            reservation.close()
        raise


def write_bootstrap(path: Path, *, root: Path, data: Path, log: Path, ui_port: int) -> None:
    """Write a temporary mitmproxy addon loader using this checkout's tap.py."""
    source = "\n".join(
        (
            "import sys",
            "from pathlib import Path",
            f"sys.path.insert(0, {json.dumps(str(root))})",
            "from cachetap import config",
            f"config.DATA = Path({json.dumps(str(data))})",
            f"config.LOG = Path({json.dumps(str(log))})",
            f"config.UI_PORT = {ui_port}",
            "import tap",
            "addons = [tap]",
            "",
        )
    )
    path.write_text(source, encoding="utf-8")


@contextmanager
def temporary_environment(values: dict[str, str]) -> Iterator[None]:
    """Temporarily set only non-secret runner controls; preserve user auth."""
    missing = object()
    previous: dict[str, str | object] = {key: os.environ.get(key, missing) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in previous.items():
            if value is missing:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)


def _http_open(url: str, *, timeout: float) -> HTTPResponse:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(url, timeout=timeout)


def _json_value(raw: bytes | str, description: str) -> object:
    try:
        decoded: object = json.loads(raw, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise RunnerError(f"{description} was not valid JSON") from error
    return decoded


def _reject_json_constant(_value: str) -> NoReturn:
    raise ValueError("non-standard JSON number")


def _object(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RunnerError(f"{description} must be a JSON object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise RunnerError(f"{description} has a non-string key")
        result[key] = item
    return result


def _count(value: object, description: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RunnerError(f"{description} must be a non-negative integer")
    return value


def _positive_id(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RunnerError("dashboard record id must be a positive integer")
    return value


def _read_json_response(http_open: HTTPOpen, url: str, *, timeout: float) -> object:
    try:
        with http_open(url, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        error.close()
        raise RunnerError("local dashboard returned an HTTP error") from error
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RunnerError("local dashboard response exceeded the smoke-check limit")
    return _json_value(raw, "local dashboard response")


def wait_for_dashboard(
    port: int,
    proxy_process: ManagedProcess,
    *,
    http_open: HTTPOpen,
    clock: Clock,
    sleep: Sleep,
) -> None:
    deadline = clock() + PROXY_READY_SECONDS
    url = f"http://127.0.0.1:{port}/api/reference"
    while True:
        if proxy_process.poll() is not None:
            raise RunnerError("proxy exited before the dashboard became ready")
        try:
            reference = _read_json_response(
                http_open, url, timeout=min(0.5, max(0.05, deadline - clock()))
            )
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            reference = None
        if isinstance(reference, dict):
            return
        remaining = deadline - clock()
        if remaining <= 0:
            raise RunnerError("dashboard was not ready before the 10-second deadline")
        sleep(min(0.1, remaining))


def decode_snapshot(value: object) -> SnapshotData:
    snapshot = _object(value, "dashboard snapshot")
    if snapshot.get("type") != "snapshot":
        raise RunnerError("dashboard did not provide a snapshot event")
    raw_rows = snapshot.get("recs")
    if not isinstance(raw_rows, list):
        raise RunnerError("dashboard snapshot did not contain a record list")
    rows: list[SnapshotRow] = []
    for raw_row in raw_rows:
        row = _object(raw_row, "dashboard snapshot record")
        record_id = _positive_id(row.get("id"))
        decoded_row: SnapshotRow = {"id": record_id}
        if "transport" in row:
            transport = row["transport"]
            if not isinstance(transport, str):
                raise RunnerError("dashboard record transport must be text")
            decoded_row["transport"] = transport
        rows.append(decoded_row)
    return {"type": "snapshot", "recs": rows}


def read_snapshot(port: int, *, http_open: HTTPOpen) -> SnapshotData:
    """Read and validate the first data-only SSE frame from the local dashboard."""
    url = f"http://127.0.0.1:{port}/events"
    data_lines: list[str] = []
    total_bytes = 0
    try:
        with http_open(url, timeout=5.0) as response:
            while True:
                line = response.readline(MAX_RESPONSE_BYTES + 1)
                if not line:
                    break
                total_bytes += len(line)
                if total_bytes > MAX_RESPONSE_BYTES:
                    raise RunnerError("dashboard snapshot exceeded the smoke-check limit")
                if line in (b"\n", b"\r\n"):
                    if data_lines:
                        break
                    continue
                if line.startswith(b"data:"):
                    data_lines.append(line.partition(b":")[2].lstrip().decode("utf-8"))
    except urllib.error.HTTPError as error:
        error.close()
        raise RunnerError("could not read the local dashboard snapshot") from error
    except (UnicodeDecodeError, urllib.error.URLError, OSError, TimeoutError) as error:
        raise RunnerError("could not read the local dashboard snapshot") from error

    if not data_lines:
        raise RunnerError("local dashboard did not provide an initial snapshot")
    return decode_snapshot(_json_value("\n".join(data_lines), "dashboard snapshot"))


def _failure_enum(value: object, allowed: frozenset[str]) -> str | None:
    if type(value) is str and value in allowed:
        return value
    return None


def _failure_step(value: object) -> FailureDiagnosticStep | None:
    if not isinstance(value, dict):
        return None
    required = ("direction", "event", "action", "identified", "id_relation")
    if any(key not in value for key in required):
        return None

    direction = _failure_enum(value.get("direction"), frozenset({"client", "server", "local"}))
    event = _failure_enum(
        value.get("event"),
        frozenset(
            {
                "response.create",
                "response.created",
                "response.in_progress",
                "response.completed",
                "response.failed",
                "response.incomplete",
                "error",
                "invalid",
                "close",
                "uninspectable",
            }
        ),
    )
    action = _failure_enum(
        value.get("action"),
        frozenset(
            {
                "start",
                "observe",
                "ignore_no_id",
                "ignore_other_id",
                "ignore_previous",
                "finish",
                "fail",
                "overlap",
            }
        ),
    )
    id_relation = _failure_enum(
        value.get("id_relation"), frozenset({"missing", "last", "unbound", "active", "other"})
    )
    identified = value.get("identified")
    if (
        direction is None
        or event is None
        or action is None
        or id_relation is None
        or type(identified) is not bool
    ):
        return None

    step: FailureDiagnosticStep = {
        "direction": cast(FailureDirection, direction),
        "event": cast(FailureEvent, event),
        "action": cast(FailureAction, action),
        "identified": identified,
        "id_relation": cast(FailureIdRelation, id_relation),
    }
    if event != "response.create" and ("generate" in value or "incremental" in value):
        return None
    if "generate" in value:
        generate = _failure_enum(
            value.get("generate"), frozenset({"absent", "true", "false", "invalid"})
        )
        if generate is None:
            return None
        step["generate"] = cast(FailureGenerate, generate)
    if "incremental" in value:
        incremental = value.get("incremental")
        if type(incremental) is not bool:
            return None
        step["incremental"] = incremental
    return step


def _failure_websocket_diagnostic(value: object) -> FailureWebSocketDiagnostic | None:
    if not isinstance(value, dict):
        return None
    events = value.get("events")
    truncated = value.get("truncated")
    omitted_server_events = value.get("omitted_server_events")
    if (
        not isinstance(events, list)
        or len(events) > 32
        or type(truncated) is not bool
        or type(omitted_server_events) is not int
        or not 0 <= omitted_server_events <= 255
    ):
        return None
    decoded_events: list[FailureDiagnosticStep] = []
    for event in events:
        decoded = _failure_step(event)
        if decoded is None:
            return None
        decoded_events.append(decoded)
    return {
        "events": decoded_events,
        "truncated": truncated,
        "omitted_server_events": omitted_server_events,
    }


def _failure_reason(notes: object) -> FailureReason:
    reasons = {
        "captura WebSocket interrumpida: peticiones solapadas": "overlap",
        "conexión WebSocket cerrada antes de completar la respuesta": "closed_before_completed",
        "respuesta WebSocket fallida": "response_failed",
        "respuesta WebSocket incompleta": "response_incomplete",
        "error del protocolo WebSocket": "protocol_error",
        "evento WebSocket no inspeccionable": "uninspectable",
        "error interno al inspeccionar WebSocket": "internal_error",
        "captura incompleta: límite de tamaño de respuesta": "response_size_limit",
        "captura incompleta: límite de respuestas simultáneas": "active_capture_limit",
    }
    if isinstance(notes, list):
        for note in notes[:8]:
            if type(note) is str and note in reasons:
                return cast(FailureReason, reasons[note])
    return "unknown"


def format_record_failure(record: dict[str, object]) -> str:
    """Return a bounded JSON projection of an unsuccessful dashboard record."""
    transport = record.get("transport", "http")
    if type(transport) is not str or transport not in {"websocket", "http"}:
        transport = "unknown"
    status = record.get("status")
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    state = _failure_enum(record.get("state"), frozenset({"pending", "streaming", "done", "error"}))
    verdict = _failure_enum(
        record.get("verdict"), frozenset({"HIT", "PARTIAL", "MISS", "COLD", "N/A", "ERR"})
    )
    result: RecordFailureDiagnostic = {
        "transport": cast(FailureTransport, transport),
        "status": status,
        "state": cast(FailureState, state if state is not None else "unknown"),
        "verdict": cast(FailureVerdict, verdict if verdict is not None else "unknown"),
        "reason": _failure_reason(record.get("notes")),
        "ws_diagnostic": _failure_websocket_diagnostic(record.get("ws_diagnostic")),
    }
    rendered = json.dumps(result, ensure_ascii=True, separators=(",", ":"))
    if len(rendered.encode("utf-8")) > MAX_RECORD_FAILURE_BYTES:
        result["ws_diagnostic"] = None
        rendered = json.dumps(result, ensure_ascii=True, separators=(",", ":"))
    return rendered


def decode_completed_record(value: object, expected_id: int) -> CompletedRecord:
    record = _object(value, "dashboard record")
    record_id = _positive_id(record.get("id"))
    if record_id != expected_id:
        raise RunnerError("dashboard returned a different record id")
    if (
        record.get("transport") != "websocket"
        or record.get("status") != 101
        or record.get("state") != "done"
    ):
        diagnostic = format_record_failure(record)
        raise RunnerError(
            f"the WebSocket record did not complete successfully; diagnostic={diagnostic}"
        )
    model = record.get("model")
    if not isinstance(model, str) or MODEL_IDENTIFIER.fullmatch(model) is None:
        raise RunnerError("the completed WebSocket record lacks an explicit model")
    raw_usage = _object(record.get("usage"), "WebSocket record usage")
    usage: UsageCounters = {
        "read": _count(raw_usage.get("read"), "record usage.read"),
        "write": _count(raw_usage.get("write"), "record usage.write"),
        "output": _count(raw_usage.get("output"), "record usage.output"),
        "input_total": _count(raw_usage.get("input_total"), "record usage.input_total"),
    }
    verdict = record.get("verdict")
    if not isinstance(verdict, str) or verdict not in ALLOWED_VERDICTS:
        raise RunnerError("the WebSocket record has an unknown cache verdict")
    return {
        "id": record_id,
        "transport": "websocket",
        "status": 101,
        "state": "done",
        "model": model,
        "usage": usage,
        "verdict": cast(Verdict, verdict),
    }


def read_record(port: int, record_id: int, *, http_open: HTTPOpen) -> CompletedRecord:
    record_id = _positive_id(record_id)
    try:
        payload = _read_json_response(
            http_open,
            f"http://127.0.0.1:{port}/api/record/{record_id}",
            timeout=5.0,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise RunnerError("could not read the local dashboard record") from error
    return decode_completed_record(payload, record_id)


def _model_metrics(value: object) -> ModelMetrics:
    row = _object(value, "CLI modelMetrics row")
    requests = _object(row.get("requests"), "CLI modelMetrics.requests")
    request_count = _count(requests.get("count"), "CLI modelMetrics.requests.count")
    request_cost = requests.get("cost")
    if not isinstance(request_cost, (int, float)) or isinstance(request_cost, bool):
        raise RunnerError("CLI modelMetrics.requests.cost is invalid")
    if request_cost < 0 or (isinstance(request_cost, float) and not math.isfinite(request_cost)):
        raise RunnerError("CLI modelMetrics.requests.cost is invalid")

    usage = _object(row.get("usage"), "CLI modelMetrics.usage")
    decoded_usage: ModelUsage = {
        "inputTokens": _count(usage.get("inputTokens"), "usage.inputTokens"),
        "outputTokens": _count(usage.get("outputTokens"), "usage.outputTokens"),
        "cacheReadTokens": _count(usage.get("cacheReadTokens"), "usage.cacheReadTokens"),
        "cacheWriteTokens": _count(usage.get("cacheWriteTokens"), "usage.cacheWriteTokens"),
        "reasoningTokens": _count(usage.get("reasoningTokens"), "usage.reasoningTokens"),
    }

    raw_details = _object(row.get("tokenDetails"), "CLI modelMetrics.tokenDetails")
    details: TokenDetails = {
        "input": _decode_token_count(raw_details.get("input"), "tokenDetails.input"),
        "cache_read": _decode_token_count(raw_details.get("cache_read"), "tokenDetails.cache_read"),
        "cache_write": _decode_token_count(
            raw_details.get("cache_write"), "tokenDetails.cache_write"
        ),
        "output": _decode_token_count(raw_details.get("output"), "tokenDetails.output"),
    }
    return {
        "requests": {"count": request_count, "cost": request_cost},
        "usage": decoded_usage,
        "tokenDetails": details,
    }


def _decode_token_count(value: object, label: str) -> TokenCount:
    token_detail = _object(value, label)
    return {"tokenCount": _count(token_detail.get("tokenCount"), f"{label}.tokenCount")}


def decode_cli_usage(value: object) -> CLIUsage:
    """Decode only the verified `modelMetrics` schema; ignore mirror sections."""
    root = _object(value, "Copilot usage output")
    raw_models = _object(root.get("modelMetrics"), "Copilot modelMetrics")
    model_metrics: dict[str, ModelMetrics] = {}
    for model, raw_metrics in raw_models.items():
        if MODEL_IDENTIFIER.fullmatch(model) is None:
            raise RunnerError("Copilot modelMetrics contains an invalid model name")
        model_metrics[model] = _model_metrics(raw_metrics)
    decoded: CLIUsage = {"modelMetrics": model_metrics}
    if "totalNanoAiu" in root:
        decoded["totalNanoAiu"] = _count(root["totalNanoAiu"], "totalNanoAiu")
    return decoded


def compare_usage(record: CompletedRecord, cli_usage: CLIUsage) -> SmokeSummary:
    model = record["model"]
    request_total = sum(
        metrics["requests"]["count"] for metrics in cli_usage["modelMetrics"].values()
    )
    if request_total != 1:
        raise RunnerError("CLI usage reports a model request count other than one")
    metrics = cli_usage["modelMetrics"].get(model)
    if metrics is None or metrics["requests"]["count"] != 1:
        raise RunnerError("CLI model metrics do not match the WebSocket record")

    expected = record["usage"]
    details = metrics["tokenDetails"]
    usage = metrics["usage"]
    if (
        usage["cacheReadTokens"] != expected["read"]
        or usage["cacheReadTokens"] != details["cache_read"]["tokenCount"]
        or usage["cacheWriteTokens"] != expected["write"]
        or usage["cacheWriteTokens"] != details["cache_write"]["tokenCount"]
        or usage["outputTokens"] != expected["output"]
        or usage["outputTokens"] != details["output"]["tokenCount"]
        or details["cache_read"]["tokenCount"] != expected["read"]
        or usage["inputTokens"] != expected["input_total"]
    ):
        raise RunnerError("CLI usage counters differ from the WebSocket record")

    summary: SmokeSummary = {
        "requests": 1,
        "model": model,
        "read": expected["read"],
        "write": expected["write"],
        "output": expected["output"],
        "input_total": expected["input_total"],
        "verdict": record["verdict"],
    }
    if "totalNanoAiu" in cli_usage:
        summary["credits_reported"] = Decimal(cli_usage["totalNanoAiu"]) / Decimal(1_000_000_000)
    return summary


def read_cli_usage(path: Path) -> CLIUsage:
    try:
        with path.open("rb") as usage_file:
            raw = usage_file.read(MAX_USAGE_BYTES + 1)
    except OSError as error:
        raise RunnerError("Copilot did not create its usage output file") from error
    if len(raw) > MAX_USAGE_BYTES:
        raise RunnerError("Copilot usage output exceeded the smoke-check limit")
    return decode_cli_usage(_json_value(raw, "Copilot usage output"))


def process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True


def stop_process(
    process: ManagedProcess | None,
    *,
    kill_group: KillGroup,
    group_exists: GroupExists,
    clock: Clock,
    sleep: Sleep,
    grace: float = TERMINATE_SECONDS,
) -> None:
    """Stop a runner-owned session, even if its process-group leader exited."""
    if process is None:
        return
    process_group_id = process.pid
    try:
        kill_group(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        pass

    deadline = clock() + grace
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass

    while group_exists(process_group_id):
        remaining = deadline - clock()
        if remaining <= 0:
            try:
                kill_group(process_group_id, signal.SIGKILL)
            except ProcessLookupError:
                pass
            break
        sleep(min(0.05, remaining))

    if process.poll() is None:
        process.wait(timeout=grace)


def _close_reservations(reservations: list[socket.socket]) -> None:
    for reservation in reservations:
        reservation.close()
    reservations.clear()


def run_real(
    copilot_argument: str | None = None,
    *,
    root: Path = ROOT,
    popen: Popen | None = None,
    http_open: HTTPOpen | None = None,
    clock: Clock | None = None,
    sleep: Sleep | None = None,
    temporary_directory: Callable[..., AbstractContextManager[str]] | None = None,
    reserve: Callable[[], tuple[list[socket.socket], tuple[int, int]]] | None = None,
    kill_group: KillGroup | None = None,
    group_exists: GroupExists | None = None,
) -> SmokeSummary:
    """Run one isolated prompt and verify its local inspector record."""
    popen = subprocess.Popen if popen is None else popen
    http_open = _http_open if http_open is None else http_open
    clock = time.monotonic if clock is None else clock
    sleep = time.sleep if sleep is None else sleep
    temporary_directory = (
        tempfile.TemporaryDirectory if temporary_directory is None else temporary_directory
    )
    reserve = reserve_ports if reserve is None else reserve
    kill_group = os.killpg if kill_group is None else kill_group
    group_exists = process_group_exists if group_exists is None else group_exists

    copilot = find_copilot(copilot_argument)
    mitmdump = root / "venv" / "bin" / "mitmdump"
    via_script = root / "via.sh"
    ca_dir = root / "ca"
    required_ca = (ca_dir / "mitmproxy-ca.pem", ca_dir / "mitmproxy-ca-cert.pem")
    if not all(path.is_file() for path in required_ca):
        raise RunnerError("existing CA files are required in the checkout's ca/ directory")
    if not mitmdump.is_file() or not os.access(mitmdump, os.X_OK):
        raise RunnerError("the checkout's venv mitmdump executable is missing")
    if not via_script.is_file():
        raise RunnerError("the checkout's via.sh is missing")

    with temporary_directory(prefix="llm-cache-tap-copilot-") as temporary_name:
        reservations: list[socket.socket] = []
        proxy_process: ManagedProcess | None = None
        cli_process: ManagedProcess | None = None
        try:
            reservations, (proxy_port, ui_port) = reserve()
            temporary = Path(temporary_name)
            workdir = temporary / "workspace"
            data_dir = temporary / "metrics"
            log_path = data_dir / "requests.jsonl"
            bootstrap = temporary / "bootstrap.py"
            usage_path = temporary / "usage.json"
            cli_logs = temporary / "copilot-logs"
            workdir.mkdir()
            data_dir.mkdir()
            cli_logs.mkdir()
            write_bootstrap(
                bootstrap,
                root=root,
                data=data_dir,
                log=log_path,
                ui_port=ui_port,
            )

            with temporary_environment(
                {
                    "TAP_PROXY_PORT": str(proxy_port),
                    "TAP_UI_PORT": str(ui_port),
                    "COPILOT_OTEL_ENABLED": "false",
                }
            ):
                _close_reservations(reservations)
                try:
                    proxy_process = popen(
                        [
                            str(mitmdump),
                            "--listen-host",
                            "127.0.0.1",
                            "-p",
                            str(proxy_port),
                            "--set",
                            f"confdir={ca_dir}",
                            "--set",
                            "termlog_verbosity=error",
                            "--set",
                            "flow_detail=0",
                            "-s",
                            str(bootstrap),
                        ],
                        cwd=root,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except OSError as error:
                    raise RunnerError("could not start the checkout's mitmdump") from error
                wait_for_dashboard(
                    ui_port,
                    proxy_process,
                    http_open=http_open,
                    clock=clock,
                    sleep=sleep,
                )

                cli_arguments = [
                    str(via_script),
                    str(copilot),
                    "--model=auto",
                    "--auto-tier=efficiency",
                    "--no-custom-instructions",
                    "--no-ask-user",
                    "--disable-builtin-mcps",
                    "--no-auto-update",
                    "--disable-client-telemetry",
                    "--sync-session=off",
                    "--log-level=error",
                    f"--log-dir={cli_logs}",
                    f"--usage-output-file={usage_path}",
                    "--deny-tool",
                    "shell",
                    "--deny-tool",
                    "write",
                    "--deny-tool",
                    "url",
                    "--prompt",
                    "hola",
                ]
                try:
                    cli_process = popen(
                        cli_arguments,
                        cwd=workdir,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except OSError as error:
                    raise RunnerError("could not start the Copilot CLI") from error
                try:
                    cli_process.wait(timeout=CLI_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired as error:
                    raise RunnerError("Copilot CLI exceeded the 90-second deadline") from error
                if cli_process.returncode != 0:
                    raise RunnerError("Copilot CLI exited unsuccessfully")

                snapshot = read_snapshot(ui_port, http_open=http_open)
                websocket_rows = [
                    row for row in snapshot["recs"] if row.get("transport") == "websocket"
                ]
                if len(websocket_rows) != 1:
                    raise RunnerError("dashboard did not contain exactly one WebSocket record")
                record = read_record(ui_port, websocket_rows[0]["id"], http_open=http_open)
                return compare_usage(record, read_cli_usage(usage_path))
        finally:
            try:
                stop_process(
                    cli_process,
                    kill_group=kill_group,
                    group_exists=group_exists,
                    clock=clock,
                    sleep=sleep,
                )
            finally:
                try:
                    stop_process(
                        proxy_process,
                        kill_group=kill_group,
                        group_exists=group_exists,
                        clock=clock,
                        sleep=sleep,
                    )
                finally:
                    _close_reservations(reservations)


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if not arguments.run_real:
        print(READY)
        return 0
    try:
        summary = run_real(arguments.copilot)
    except RunnerError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    rendered = (
        "OK: "
        f"requests={summary['requests']} model={summary['model']} "
        f"read={summary['read']} write={summary['write']} "
        f"output={summary['output']} input_total={summary['input_total']} "
        f"verdict={summary['verdict']}"
    )
    if "credits_reported" in summary:
        rendered += f" credits_reported={summary['credits_reported']}"
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
