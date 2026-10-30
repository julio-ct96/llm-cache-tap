"""Offline orchestration tests against the verified Copilot output contracts."""

import contextlib
import io
import json
import signal
import subprocess
import tempfile
import unittest
import urllib.error
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

import scripts.check_copilot as runner

MODEL = "gpt-6-luna"
RECORD_ID = 17
NANO_AIU = 57_968_100
RECORD_USAGE = {"read": 9004, "write": 4286, "output": 36, "input_total": 13293}


def model_row(*, request_count=1):
    return {
        "requests": {"count": request_count, "cost": 1},
        "usage": {
            "inputTokens": 13293,
            "outputTokens": 36,
            "cacheReadTokens": 9004,
            "cacheWriteTokens": 4286,
            "reasoningTokens": 21,
        },
        "tokenDetails": {
            "input": {"tokenCount": 3},
            "cache_read": {"tokenCount": 9004},
            "cache_write": {"tokenCount": 4286},
            "output": {"tokenCount": 36},
        },
    }


def cli_usage(*, request_count=1, mirrors=True, total_nano_aiu=NANO_AIU):
    row = model_row(request_count=request_count)
    result = {"modelMetrics": {MODEL: row}}
    if mirrors:
        # These are repeated views, not additional model requests.
        result["agentMetrics"] = {"agent": {MODEL: row}}
        result["providerModelMetrics"] = {"provider": {MODEL: row}}
    if total_nano_aiu is not None:
        result["totalNanoAiu"] = total_nano_aiu
    return result


def completed_record(*, record_id=RECORD_ID, verdict="PARTIAL", usage=None):
    return {
        "id": record_id,
        "transport": "websocket",
        "status": 101,
        "state": "done",
        "model": MODEL,
        "usage": RECORD_USAGE if usage is None else usage,
        "verdict": verdict,
    }


class Response:
    def __init__(self, content=b"", lines=None):
        self.content = content
        self.lines = list(lines or [])
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def close(self):
        self.closed = True

    def read(self, _limit=-1):
        return self.content

    def readline(self, _limit=-1):
        return self.lines.pop(0) if self.lines else b""


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class FakeReservation:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, pid, *, kind, timeout=False, returncode=None):
        self.pid = pid
        self.kind = kind
        self.timeout = timeout
        self.returncode = returncode
        self.wait_calls = []

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.timeout and timeout == runner.CLI_TIMEOUT_SECONDS:
            raise subprocess.TimeoutExpired("copilot", timeout)
        if self.returncode is None:
            self.returncode = -signal.SIGTERM
        return self.returncode


class ProcessGroups:
    def __init__(self):
        self.alive = {}
        self.calls = []

    def start(self, process_id):
        self.alive[process_id] = True

    def kill(self, process_id, signum):
        self.calls.append((process_id, signum))
        if signum == signal.SIGTERM:
            self.alive[process_id] = False
        if signum == signal.SIGKILL:
            self.alive[process_id] = False

    def exists(self, process_id):
        return self.alive.get(process_id, False)


class FakePopen:
    def __init__(self, groups, *, mode="success", usage=None):
        self.groups = groups
        self.mode = mode
        self.usage = cli_usage() if usage is None else usage
        self.calls = []
        self.processes = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if self.mode == "proxy-start-fails" and len(self.calls) == 1:
            raise OSError("synthetic start failure")
        if self.mode == "cli-start-fails" and len(self.calls) == 2:
            raise OSError("synthetic CLI start failure")
        is_cli = len(self.calls) == 2
        process = FakeProcess(
            4100 + len(self.calls),
            kind="cli" if is_cli else "proxy",
            timeout=is_cli and self.mode == "cli-timeout",
            returncode=0 if is_cli and self.mode != "cli-timeout" else None,
        )
        self.groups.start(process.pid)
        self.processes.append(process)
        if is_cli:
            usage_argument = next(
                argument for argument in command if argument.startswith("--usage-output-file=")
            )
            usage_path = Path(usage_argument.partition("=")[2])
            usage_path.write_text(json.dumps(self.usage), encoding="utf-8")
        return process


class FakeHTTP:
    def __init__(self, *, mode="success", recs=None, record=None):
        self.mode = mode
        self.recs = [{"id": RECORD_ID, "transport": "websocket"}] if recs is None else recs
        self.record = completed_record() if record is None else record
        self.urls = []
        self.http_error = None
        self.responses = []

    def _response(self, response):
        self.responses.append(response)
        return response

    def __call__(self, url, *, timeout):
        self.urls.append((url, timeout))
        path = urlsplit(url).path
        if path.endswith("/api/reference"):
            if self.mode == "proxy-not-ready":
                raise urllib.error.URLError("synthetic connection failure")
            return self._response(Response(b"{}"))
        if path == "/events":
            if self.mode == "events-http-error":
                self.http_error = urllib.error.HTTPError(
                    url, 503, "synthetic", {}, io.BytesIO(b"private response")
                )
                raise self.http_error
            data = json.dumps({"type": "snapshot", "recs": self.recs}).encode("utf-8")
            # The real dashboard sends one `data:` frame without an `event:` line.
            response = Response(lines=[b"data: " + data + b"\n", b"\n"])
            self.snapshot_lines = tuple(response.lines)
            return self._response(response)
        if path.startswith("/api/record/"):
            requested_id = int(path.rsplit("/", 1)[1])
            if requested_id != RECORD_ID:
                raise AssertionError("runner requested an unexpected record id")
            return self._response(Response(json.dumps(self.record).encode("utf-8")))
        raise AssertionError("unexpected local HTTP route")


class CheckCopilotTest(unittest.TestCase):
    def setUp(self):
        self.root_dir = tempfile.TemporaryDirectory(prefix="check-copilot-fixture-")
        self.root = Path(self.root_dir.name) / "checkout"
        self.root.mkdir()
        (self.root / "venv" / "bin").mkdir(parents=True)
        (self.root / "ca").mkdir()
        self.mitmdump = self.root / "venv" / "bin" / "mitmdump"
        self.mitmdump.touch()
        self.mitmdump.chmod(0o755)
        self.via = self.root / "via.sh"
        self.via.touch()
        self.copilot = self.root / "copilot"
        self.copilot.touch()
        self.copilot.chmod(0o755)
        (self.root / "ca" / "mitmproxy-ca.pem").touch()
        (self.root / "ca" / "mitmproxy-ca-cert.pem").touch()
        self.temporary_dirs = []
        self.reservations = [FakeReservation(), FakeReservation()]
        self.clock = FakeClock()
        self.groups = ProcessGroups()

    def tearDown(self):
        self.root_dir.cleanup()

    def temporary_directory(self, **kwargs):
        directory = tempfile.TemporaryDirectory(**kwargs)
        self.temporary_dirs.append(directory)
        return directory

    def reserve(self):
        return self.reservations, (20001, 20002)

    def run_runner(self, *, mode="success", recs=None, usage=None, http_mode=None):
        popen = FakePopen(self.groups, mode=mode, usage=usage)
        http = FakeHTTP(mode=http_mode or mode, recs=recs)
        summary = runner.run_real(
            str(self.copilot),
            root=self.root,
            popen=popen,
            http_open=http,
            clock=self.clock,
            sleep=self.clock.sleep,
            temporary_directory=self.temporary_directory,
            reserve=self.reserve,
            kill_group=self.groups.kill,
            group_exists=self.groups.exists,
        )
        return summary, popen, http

    def assert_temp_dirs_removed(self):
        self.assertTrue(self.temporary_dirs)
        for directory in self.temporary_dirs:
            self.assertFalse(Path(directory.name).exists())

    def run_with_failure(
        self, *, mode="success", recs=None, usage=None, http_mode=None, message=None
    ):
        popen = FakePopen(self.groups, mode=mode, usage=usage)
        http = FakeHTTP(mode=http_mode or mode, recs=recs)
        with self.assertRaisesRegex(runner.RunnerError, message or ".*"):
            runner.run_real(
                str(self.copilot),
                root=self.root,
                popen=popen,
                http_open=http,
                clock=self.clock,
                sleep=self.clock.sleep,
                temporary_directory=self.temporary_directory,
                reserve=self.reserve,
                kill_group=self.groups.kill,
                group_exists=self.groups.exists,
            )
        self.assert_temp_dirs_removed()
        self.assertTrue(all(reservation.closed for reservation in self.reservations))
        return popen, http

    def test_default_is_exact_ready_without_subprocess_or_http(self):
        output = io.StringIO()
        with (
            patch.object(runner, "run_real") as run_real,
            patch.object(runner.subprocess, "Popen") as popen,
            patch.object(runner, "_http_open") as http_open,
            contextlib.redirect_stdout(output),
        ):
            status = runner.main(["--copilot", "/not/a/copilot"])
        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue(), "READY: no model calls; use --run-real\n")
        run_real.assert_not_called()
        popen.assert_not_called()
        http_open.assert_not_called()

    def test_missing_executable_and_missing_ca_fail_before_process_start(self):
        with self.assertRaisesRegex(runner.RunnerError, "Copilot executable"):
            runner.run_real(str(self.root / "absent"), root=self.root, popen=Mock(), reserve=Mock())

        (self.root / "ca" / "mitmproxy-ca.pem").unlink()
        popen = Mock()
        with self.assertRaisesRegex(runner.RunnerError, "existing CA files"):
            runner.run_real(str(self.copilot), root=self.root, popen=popen, reserve=Mock())
        popen.assert_not_called()

    def test_mitmdump_start_failure_closes_ports_and_temp_without_cli(self):
        popen = FakePopen(self.groups, mode="proxy-start-fails")
        with self.assertRaisesRegex(runner.RunnerError, "could not start.*mitmdump"):
            runner.run_real(
                str(self.copilot),
                root=self.root,
                popen=popen,
                clock=self.clock,
                sleep=self.clock.sleep,
                temporary_directory=self.temporary_directory,
                reserve=self.reserve,
                kill_group=self.groups.kill,
                group_exists=self.groups.exists,
            )
        self.assertEqual(len(popen.calls), 1)
        self.assert_temp_dirs_removed()
        self.assertTrue(all(reservation.closed for reservation in self.reservations))

    def test_cli_start_failure_stops_started_proxy_and_cleans_temp(self):
        popen = FakePopen(self.groups, mode="cli-start-fails")
        with self.assertRaisesRegex(runner.RunnerError, "could not start the Copilot CLI"):
            runner.run_real(
                str(self.copilot),
                root=self.root,
                popen=popen,
                http_open=FakeHTTP(),
                clock=self.clock,
                sleep=self.clock.sleep,
                temporary_directory=self.temporary_directory,
                reserve=self.reserve,
                kill_group=self.groups.kill,
                group_exists=self.groups.exists,
            )
        self.assertEqual(len(popen.calls), 2)
        self.assertEqual(self.groups.calls, [(popen.processes[0].pid, signal.SIGTERM)])
        self.assert_temp_dirs_removed()

    def test_proxy_readiness_timeout_does_not_launch_cli_and_cleans_group(self):
        popen = FakePopen(self.groups, mode="proxy-not-ready")
        http = FakeHTTP(mode="proxy-not-ready")
        with self.assertRaisesRegex(runner.RunnerError, "10-second deadline"):
            runner.run_real(
                str(self.copilot),
                root=self.root,
                popen=popen,
                http_open=http,
                clock=self.clock,
                sleep=self.clock.sleep,
                temporary_directory=self.temporary_directory,
                reserve=self.reserve,
                kill_group=self.groups.kill,
                group_exists=self.groups.exists,
            )
        self.assertEqual(len(popen.calls), 1)
        self.assertEqual(self.groups.calls, [(popen.processes[0].pid, signal.SIGTERM)])
        self.assert_temp_dirs_removed()

    def test_http_error_closes_response_and_cleans_both_process_groups(self):
        popen = FakePopen(self.groups)
        http = FakeHTTP(mode="events-http-error")
        with self.assertRaisesRegex(runner.RunnerError, "snapshot"):
            runner.run_real(
                str(self.copilot),
                root=self.root,
                popen=popen,
                http_open=http,
                clock=self.clock,
                sleep=self.clock.sleep,
                temporary_directory=self.temporary_directory,
                reserve=self.reserve,
                kill_group=self.groups.kill,
                group_exists=self.groups.exists,
            )
        self.assertIsNotNone(http.http_error)
        self.assertTrue(http.http_error.fp.closed)
        self.assertEqual(len(popen.calls), 2)
        self.assert_temp_dirs_removed()
        self.assertEqual(
            self.groups.calls,
            [
                (popen.processes[1].pid, signal.SIGTERM),
                (popen.processes[0].pid, signal.SIGTERM),
            ],
        )

    def test_cli_timeout_launches_one_prompt_and_cleans_cli_before_proxy(self):
        popen = FakePopen(self.groups, mode="cli-timeout")
        http = FakeHTTP()
        with self.assertRaisesRegex(runner.RunnerError, "90-second deadline"):
            runner.run_real(
                str(self.copilot),
                root=self.root,
                popen=popen,
                http_open=http,
                clock=self.clock,
                sleep=self.clock.sleep,
                temporary_directory=self.temporary_directory,
                reserve=self.reserve,
                kill_group=self.groups.kill,
                group_exists=self.groups.exists,
            )
        self.assertEqual(len(popen.calls), 2)
        command = popen.calls[1][0]
        self.assertEqual(command.count("--prompt"), 1)
        self.assertEqual(command[command.index("--prompt") + 1], "hola")
        self.assertNotIn("--allow-all-tools", command)
        self.assertNotIn("--allow-all", command)
        self.assertNotIn("--yolo", command)
        self.assertEqual(
            [process_id for process_id, _ in self.groups.calls],
            [popen.processes[1].pid, popen.processes[0].pid],
        )
        self.assertTrue(all(options["start_new_session"] for _, options in popen.calls))
        self.assert_temp_dirs_removed()

    def test_cleanup_signals_owned_group_even_after_its_leader_exited(self):
        leader = FakeProcess(7701, kind="cli", returncode=0)
        unrelated = FakeProcess(7702, kind="cli", returncode=0)
        calls = []
        clock = FakeClock()

        def kill_group(process_group_id, signum):
            calls.append((process_group_id, signum))

        runner.stop_process(
            leader,
            kill_group=kill_group,
            group_exists=lambda _process_group_id: True,
            clock=clock,
            sleep=clock.sleep,
            grace=0.1,
        )
        self.assertEqual(
            calls,
            [(leader.pid, signal.SIGTERM), (leader.pid, signal.SIGKILL)],
        )
        self.assertNotIn(unrelated.pid, [process_id for process_id, _ in calls])

    def test_snapshot_is_data_only_and_ids_are_positive_integers(self):
        http = FakeHTTP()
        snapshot = runner.read_snapshot(20002, http_open=http)
        self.assertEqual(
            snapshot, {"type": "snapshot", "recs": [{"id": RECORD_ID, "transport": "websocket"}]}
        )
        self.assertEqual(len(http.snapshot_lines), 2)
        self.assertTrue(http.snapshot_lines[0].startswith(b"data:"))
        self.assertFalse(any(line.startswith(b"event:") for line in http.snapshot_lines))

        for invalid_id in (True, False, 0, -1, "17"):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(runner.RunnerError):
                    runner.decode_snapshot({"type": "snapshot", "recs": [{"id": invalid_id}]})

    def test_read_record_rejects_bad_ids_before_http_and_uses_integer_path(self):
        http = Mock()
        for invalid_id in (True, False, 0, -1, "17"):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(runner.RunnerError):
                    runner.read_record(20002, invalid_id, http_open=http)
        http.assert_not_called()

        valid_http = FakeHTTP()
        runner.read_record(20002, RECORD_ID, http_open=valid_http)
        self.assertIn(f"/api/record/{RECORD_ID}", valid_http.urls[0][0])

    def test_unknown_cli_usage_schema_fails_without_guessing(self):
        with self.assertRaisesRegex(runner.RunnerError, "modelMetrics"):
            runner.decode_cli_usage({"models": {MODEL: model_row()}})
        with self.assertRaisesRegex(runner.RunnerError, "requests"):
            runner.decode_cli_usage(
                {"modelMetrics": {MODEL: {"requests": 1, "usage": {}, "tokenDetails": {}}}}
            )

    def test_deep_json_recursion_becomes_a_fixed_runner_error(self):
        with patch.object(runner.json, "loads", side_effect=RecursionError):
            with self.assertRaisesRegex(runner.RunnerError, "was not valid JSON"):
                runner._json_value("{}", "external JSON")

    def test_additional_model_request_fails_and_cleans_temporary_data(self):
        usage = cli_usage(mirrors=False)
        usage["modelMetrics"]["other-model"] = model_row(request_count=1)
        popen, _http = self.run_with_failure(usage=usage, message="other than one")
        self.assertEqual(len(popen.calls), 2)

    def test_zero_websocket_records_fail_and_cleanup(self):
        popen, _http = self.run_with_failure(recs=[], message="exactly one WebSocket")
        self.assertEqual(len(popen.calls), 2)

    def test_metric_mismatch_fails_and_cleans_temporary_data(self):
        usage = cli_usage(mirrors=False)
        usage["modelMetrics"][MODEL]["tokenDetails"]["cache_read"]["tokenCount"] = 1
        popen, _http = self.run_with_failure(usage=usage, message="counters differ")
        self.assertEqual(len(popen.calls), 2)

    def test_model_usage_contradicting_matching_token_details_fails(self):
        usage = cli_usage(mirrors=False)
        usage["modelMetrics"][MODEL]["usage"]["cacheReadTokens"] = 1
        popen, _http = self.run_with_failure(usage=usage, message="counters differ")
        self.assertEqual(len(popen.calls), 2)

    def test_success_ignores_mirror_metrics_and_reports_verdict_and_credits(self):
        summary, popen, http = self.run_runner()
        self.assertEqual(
            summary,
            {
                "requests": 1,
                "model": MODEL,
                **RECORD_USAGE,
                "verdict": "PARTIAL",
                "credits_reported": Decimal("0.0579681"),
            },
        )
        self.assertEqual(len(popen.calls), 2)
        proxy_command, proxy_options = popen.calls[0]
        cli_command, cli_options = popen.calls[1]
        self.assertEqual(proxy_command[0], str(self.mitmdump))
        self.assertTrue(proxy_options["start_new_session"])
        self.assertEqual(cli_command[0], str(self.via))
        self.assertEqual(cli_options["cwd"].name, "workspace")
        self.assertTrue(cli_options["start_new_session"])
        for required in (
            "--model=auto",
            "--auto-tier=efficiency",
            "--no-custom-instructions",
            "--no-ask-user",
            "--disable-builtin-mcps",
            "--no-auto-update",
            "--disable-client-telemetry",
            "--sync-session=off",
            "--log-level=error",
        ):
            self.assertIn(required, cli_command)
        self.assertEqual(cli_command.count("--deny-tool"), 3)
        self.assertTrue(any("/api/reference" in url for url, _ in http.urls))
        self.assertTrue(any(url.endswith("/events") for url, _ in http.urls))
        self.assertTrue(all(reservation.closed for reservation in self.reservations))
        self.assert_temp_dirs_removed()

    def test_missing_total_nano_aiu_does_not_invent_reported_credits(self):
        summary, _popen, _http = self.run_runner(usage=cli_usage(total_nano_aiu=None))
        self.assertNotIn("credits_reported", summary)

    def test_done_record_accepts_every_closed_verdict_and_rejects_err(self):
        for verdict in ("HIT", "PARTIAL", "MISS", "N/A", "COLD"):
            with self.subTest(verdict=verdict):
                record = runner.decode_completed_record(
                    completed_record(verdict=verdict), RECORD_ID
                )
                self.assertEqual(record["verdict"], verdict)
        for verdict in ("ERR", "UNREVIEWED"):
            with self.subTest(verdict=verdict):
                with self.assertRaisesRegex(runner.RunnerError, "unknown cache verdict"):
                    runner.decode_completed_record(completed_record(verdict=verdict), RECORD_ID)

    def test_main_prints_only_validated_summary_fields(self):
        output = io.StringIO()
        summary = {
            "requests": 1,
            "model": MODEL,
            **RECORD_USAGE,
            "verdict": "PARTIAL",
            "credits_reported": Decimal("0.0579681"),
        }
        with patch.object(runner, "run_real", return_value=summary):
            with contextlib.redirect_stdout(output):
                status = runner.main(["--run-real"])
        rendered = output.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("verdict=PARTIAL", rendered)
        self.assertIn("credits_reported=0.0579681", rendered)
        self.assertNotIn("usd", rendered.lower())
        self.assertNotIn("token", rendered.lower())
        self.assertNotIn("output text", rendered.lower())


if __name__ == "__main__":
    unittest.main()
