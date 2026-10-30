import http.client
import json
import threading
import time
import unittest
from collections import OrderedDict
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import tap
from cachetap import config, dashboard, store
from scripts import check_copilot as runner
from tests.test_websocket_hooks import play_failure_cases, play_fixture, play_symbol_failure_cases


class WebSocketDashboardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.log_path = Path(self.temp.name) / "requests.jsonl"
        self.log_patch = patch.object(config, "LOG", self.log_path)
        self.log_patch.start()
        self.addCleanup(self.log_patch.stop)

        self.store_patch = patch.multiple(
            store,
            RECORDS=OrderedDict(),
            BODIES={},
            CONV_TOTALS={},
            CLIENTS=[],
            ACTIVE_CAPTURES=set(),
            STATE={"next_id": 1, "next_conv": 1, "body_bytes": 0},
        )
        self.sockets_patch = patch.object(tap, "SOCKETS", {})
        with store.LOCK:
            self.store_patch.start()
            self.sockets_patch.start()
        self.addCleanup(self._restore_state)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True,
        )
        self.server_thread.start()
        self.addCleanup(self._stop_server)
        self.addCleanup(self._release_subscribers)

    def _restore_state(self) -> None:
        for session in tuple(tap.SOCKETS.values()):
            session.close()
        with store.LOCK:
            self.sockets_patch.stop()
            self.store_patch.stop()

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)
        self.assertFalse(self.server_thread.is_alive(), "dashboard server did not stop")

    def _release_subscribers(self) -> None:
        with store.LOCK:
            if store.CLIENTS:
                store.publish({"type": "disconnect"})

        deadline = time.monotonic() + 5
        while True:
            with store.LOCK:
                if not store.CLIENTS:
                    return
            if time.monotonic() >= deadline:
                self.fail("SSE subscriber was not removed")
            threading.Event().wait(0.01)

    def _request(self, path: str) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def _open_events(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/events")
        response = conn.getresponse()
        self.addCleanup(response.close)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/event-stream")
        return conn, response, self._read_event(response)

    @staticmethod
    def _read_event(response: http.client.HTTPResponse) -> dict:
        data: list[bytes] = []
        while True:
            line = response.readline()
            if not line:
                raise AssertionError("SSE stream closed before an event arrived")
            if line in (b"\n", b"\r\n"):
                if data:
                    return json.loads(b"".join(data).decode("utf-8"))
                continue
            if line.startswith(b"data: "):
                data.append(line[6:].rstrip(b"\r\n"))

    def test_fixture_is_exposed_by_record_body_and_sse(self) -> None:
        conn, response, initial = self._open_events()
        self.assertEqual(initial["type"], "snapshot")
        self.assertEqual(initial["recs"], [])

        try:
            _flow, rid = play_fixture()

            terminal = None
            while terminal is None:
                event = self._read_event(response)
                if (
                    event.get("type") == "record"
                    and event.get("rec", {}).get("id") == rid
                    and event.get("rec", {}).get("state") == "done"
                ):
                    terminal = event
        finally:
            response.close()
            conn.close()
            self._release_subscribers()

        status, payload = self._request(f"/api/record/{rid}")
        self.assertEqual(status, 200)
        detail = json.loads(payload)
        self.assertEqual(detail["state"], "done")
        self.assertEqual(detail["status"], 101)
        self.assertEqual(detail["transport"], "websocket")
        self.assertNotIn("ws_diagnostic", detail)
        self.assertEqual(detail["model"], "gpt-6-luna")
        self.assertEqual(detail["verdict"], "PARTIAL")
        self.assertEqual(
            detail["usage"],
            {
                "input_total": 13293,
                "read": 9004,
                "write": 4286,
                "uncached": 3,
                "output": 36,
                "reasoning": 21,
            },
        )
        self.assertEqual(detail["cost"]["tariff"], "Copilot")
        self.assertEqual(detail["cost"]["usd"], 0.00064409)
        self.assertFalse(any(key.startswith("_") for key in detail))

        status, payload = self._request(f"/api/body/{rid}")
        self.assertEqual(status, 200)
        body = json.loads(payload)
        self.assertEqual(body["model"], "gpt-6-luna")
        self.assertNotIn("type", body)
        self.assertNotIn("headers", body)
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", payload.decode("utf-8"))

        self.assertEqual(terminal["rec"]["id"], detail["id"])
        self.assertEqual(terminal["rec"]["state"], "done")
        totals = terminal["convs"][detail["conv"]]
        self.assertEqual(totals["priced"], 1)
        self.assertEqual(totals["usd"], detail["cost"]["usd"])

        _snapshot_conn, _snapshot_response, snapshot = self._open_events()
        try:
            self.assertEqual(snapshot["type"], "snapshot")
            self.assertEqual(len(snapshot["recs"]), 1)
            light = snapshot["recs"][0]
            self.assertEqual(light["id"], rid)
            self.assertNotIn("raw_usage", light)
            self.assertNotIn("segs", light)
            self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", json.dumps(snapshot))
            self.assertEqual(snapshot["convs"][detail["conv"]]["priced"], 1)
        finally:
            _snapshot_response.close()
            _snapshot_conn.close()
            self._release_subscribers()

        log_text = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", log_text)

    def test_hook_failures_are_diagnosable_only_from_api_detail(self) -> None:
        conn, response, initial = self._open_events()
        self.assertEqual(initial["type"], "snapshot")
        self.assertEqual(initial["recs"], [])

        try:
            _overlap_flow, overlap_rid, _close_flow, close_rid = play_failure_cases()
            expected_ids = {overlap_rid, close_rid}
            terminal: dict[int, dict] = {}
            while set(terminal) != expected_ids:
                event = self._read_event(response)
                if event.get("type") != "record":
                    continue
                rec = event.get("rec", {})
                if rec.get("id") in expected_ids and rec.get("state") == "error":
                    terminal[rec["id"]] = event
        finally:
            response.close()
            conn.close()
            self._release_subscribers()

        expected = {
            overlap_rid: (
                "captura WebSocket interrumpida: peticiones solapadas",
                "overlap",
            ),
            close_rid: (
                "conexión WebSocket cerrada antes de completar la respuesta",
                "closed_before_completed",
            ),
        }
        for rid, (note, category) in expected.items():
            with self.subTest(category=category):
                event = terminal[rid]
                light = event["rec"]
                self.assertEqual(light["state"], "error")
                self.assertEqual(light["status"], 101)
                self.assertEqual(light["verdict"], "ERR")
                self.assertEqual(light["notes"], [note])
                self.assertNotIn("ws_diagnostic", light)

                status, payload = self._request(f"/api/record/{rid}")
                self.assertEqual(status, 200)
                detail = json.loads(payload)
                self.assertEqual(detail["state"], "error")
                self.assertEqual(detail["status"], 101)
                self.assertEqual(detail["notes"], [note])
                self.assertEqual(detail["ws_diagnostic"]["truncated"], False)

                with self.assertRaises(runner.RunnerError) as raised:
                    runner.decode_completed_record(detail, rid)
                failure_text = str(raised.exception)
                prefix = "the WebSocket record did not complete successfully; diagnostic="
                self.assertTrue(failure_text.startswith(prefix))
                failure = json.loads(failure_text[len(prefix) :])
                self.assertEqual(failure["reason"], category)
                self.assertEqual(failure["state"], "error")
                self.assertEqual(failure["ws_diagnostic"], detail["ws_diagnostic"])
                self.assertEqual(
                    set(failure),
                    {"transport", "status", "state", "verdict", "reason", "ws_diagnostic"},
                )
                failure_keys = set(failure)
                for step in failure["ws_diagnostic"]["events"]:
                    failure_keys.update(step)
                self.assertFalse(
                    {"id", "response_id", "input", "headers", "output", "reasoning"} & failure_keys
                )
                for sentinel in (
                    "WS_OVERLAP_INPUT_SENTINEL",
                    "WS_OVERLAP_SECOND_INPUT_SENTINEL",
                    "WS_CLOSE_INPUT_SENTINEL",
                    "WS_FAILURE_OUTPUT_SENTINEL",
                    "WEBSOCKET_TRANSPORT_SENTINEL",
                    "synthetic-overlap-response-id",
                    "synthetic-close-response-id",
                    "synthetic-previous-response-id",
                ):
                    self.assertNotIn(sentinel, failure_text)

                status, payload = self._request(f"/api/body/{rid}")
                self.assertEqual(status, 200)
                body = json.loads(payload)
                self.assertNotIn("headers", body)
                self.assertNotIn("ws_diagnostic", body)
                self.assertNotIn("WEBSOCKET_TRANSPORT_SENTINEL", payload.decode("utf-8"))
                self.assertNotIn("WS_FAILURE_OUTPUT_SENTINEL", payload.decode("utf-8"))

        _snapshot_conn, _snapshot_response, snapshot = self._open_events()
        try:
            self.assertEqual(snapshot["type"], "snapshot")
            snapshot_rows = {row["id"]: row for row in snapshot["recs"]}
            self.assertEqual(set(snapshot_rows), set(expected))
            for rid, (note, _category) in expected.items():
                self.assertEqual(snapshot_rows[rid]["state"], "error")
                self.assertEqual(snapshot_rows[rid]["notes"], [note])
                self.assertNotIn("ws_diagnostic", snapshot_rows[rid])
        finally:
            _snapshot_response.close()
            _snapshot_conn.close()
            self._release_subscribers()

        with store.LOCK:
            self.assertFalse(store.ACTIVE_CAPTURES)
            self.assertEqual(store.CONV_TOTALS, {})
            for rid in expected:
                self.assertNotIn("cost", store.RECORDS[rid])
                self.assertNotIn("cost_missing", store.RECORDS[rid])

        log_text = self.log_path.read_text(encoding="utf-8") if self.log_path.exists() else ""
        self.assertEqual(log_text, "")
        for sentinel in (
            "ws_diagnostic",
            "WS_OVERLAP_INPUT_SENTINEL",
            "WS_CLOSE_INPUT_SENTINEL",
            "WEBSOCKET_TRANSPORT_SENTINEL",
            "WS_FAILURE_OUTPUT_SENTINEL",
        ):
            self.assertNotIn(sentinel, log_text)

    def test_symbolic_failures_are_private_across_dashboard_surfaces(self) -> None:
        conn, response, initial = self._open_events()
        self.assertEqual(initial["type"], "snapshot")
        self.assertEqual(initial["recs"], [])

        try:
            cases = play_symbol_failure_cases()
            expected_ids = {rid for _flow, rid in cases.values()}
            terminal: dict[int, dict] = {}
            while set(terminal) != expected_ids:
                event = self._read_event(response)
                rec = event.get("rec", {})
                if (
                    event.get("type") == "record"
                    and rec.get("id") in expected_ids
                    and rec.get("state") == "error"
                ):
                    terminal[rec["id"]] = event
        finally:
            response.close()
            conn.close()
            self._release_subscribers()

        wire_ids = (
            "WS_WIRE_RESPONSE_ID_SAME_A_SECRET",
            "WS_WIRE_RESPONSE_ID_SAME_B_SECRET",
            "WS_WIRE_RESPONSE_ID_DIFFERENT_A_SECRET",
            "WS_WIRE_RESPONSE_ID_DIFFERENT_B_SECRET",
            "WS_WIRE_RESPONSE_ID_DIFFERENT_C_SECRET",
        )
        details: dict[str, dict] = {}
        sanitized_diagnostics: dict[str, dict] = {}
        for name, (_flow, rid) in cases.items():
            with self.subTest(case=name):
                event = terminal[rid]
                light = event["rec"]
                self.assertEqual(light["state"], "error")
                self.assertEqual(
                    light["notes"], ["captura WebSocket interrumpida: peticiones solapadas"]
                )
                self.assertNotIn("ws_diagnostic", light)
                self.assertNotIn("id_symbol", json.dumps(event))
                self.assertFalse(any(sentinel in json.dumps(event) for sentinel in wire_ids))

                status, payload = self._request(f"/api/record/{rid}")
                self.assertEqual(status, 200)
                detail = json.loads(payload)
                details[name] = detail
                self.assertEqual(detail["state"], "error")
                self.assertEqual(detail["status"], 101)
                self.assertEqual(detail["notes"], light["notes"])
                self.assertIn("model", detail)  # Normal record fields are not diagnostic leaks.
                self.assertNotIn("usage", detail)
                self.assertNotIn("cost", detail)
                self.assertNotIn("cost_missing", detail)
                diagnostic = detail["ws_diagnostic"]
                symbols = [
                    step.get("id_symbol")
                    for step in diagnostic["events"]
                    if step["direction"] == "server"
                ]
                self.assertEqual(symbols, [1, 2, 2] if name == "other_same" else [1, 2, 3])
                detail_text = payload.decode("utf-8")
                for sentinel in wire_ids:
                    self.assertNotIn(sentinel, detail_text)

                with self.assertRaises(runner.RunnerError) as raised:
                    runner.decode_completed_record(detail, rid)
                failure_text = str(raised.exception)
                prefix = "the WebSocket record did not complete successfully; diagnostic="
                self.assertTrue(failure_text.startswith(prefix))
                failure = json.loads(failure_text[len(prefix) :])
                self.assertEqual(
                    set(failure),
                    {"transport", "status", "state", "verdict", "reason", "ws_diagnostic"},
                )
                self.assertEqual(failure["reason"], "overlap")
                self.assertEqual(failure["ws_diagnostic"], diagnostic)
                sanitized_diagnostics[name] = failure["ws_diagnostic"]
                allowed_step_keys = {
                    "direction",
                    "event",
                    "action",
                    "identified",
                    "id_relation",
                    "generate",
                    "incremental",
                    "id_symbol",
                }
                for step in failure["ws_diagnostic"]["events"]:
                    self.assertLessEqual(set(step), allowed_step_keys)
                    if step["direction"] == "server" and "id_symbol" in step:
                        self.assertIs(type(step["id_symbol"]), int)
                        self.assertGreaterEqual(step["id_symbol"], 1)
                        self.assertLessEqual(step["id_symbol"], 32)
                    else:
                        self.assertNotIn("id_symbol", step)
                for sentinel in wire_ids:
                    self.assertNotIn(sentinel, failure_text)

                status, payload = self._request(f"/api/body/{rid}")
                self.assertEqual(status, 200)
                body = json.loads(payload)
                self.assertNotIn("headers", body)
                self.assertNotIn("ws_diagnostic", body)
                body_text = payload.decode("utf-8")
                for sentinel in wire_ids:
                    self.assertNotIn(sentinel, body_text)

        same = json.loads(json.dumps(details["other_same"]["ws_diagnostic"]))
        different = json.loads(json.dumps(details["other_different"]["ws_diagnostic"]))
        for diagnostic in (same, different):
            for step in diagnostic["events"]:
                step.pop("id_symbol", None)
        self.assertEqual(same, different)
        self.assertEqual(
            sanitized_diagnostics["other_same"]["events"],
            details["other_same"]["ws_diagnostic"]["events"],
        )
        self.assertEqual(
            sanitized_diagnostics["other_different"]["events"],
            details["other_different"]["ws_diagnostic"]["events"],
        )

        _snapshot_conn, _snapshot_response, snapshot = self._open_events()
        try:
            self.assertEqual(snapshot["type"], "snapshot")
            snapshot_rows = {row["id"]: row for row in snapshot["recs"]}
            self.assertEqual(set(snapshot_rows), expected_ids)
            snapshot_text = json.dumps(snapshot)
            self.assertNotIn("ws_diagnostic", snapshot_text)
            self.assertNotIn("id_symbol", snapshot_text)
            for sentinel in wire_ids:
                self.assertNotIn(sentinel, snapshot_text)
            for rid in expected_ids:
                self.assertEqual(snapshot_rows[rid]["state"], "error")
                self.assertEqual(
                    snapshot_rows[rid]["notes"],
                    ["captura WebSocket interrumpida: peticiones solapadas"],
                )
        finally:
            _snapshot_response.close()
            _snapshot_conn.close()
            self._release_subscribers()

        with store.LOCK:
            self.assertFalse(store.ACTIVE_CAPTURES)
            self.assertEqual(store.CONV_TOTALS, {})
            for rid in expected_ids:
                self.assertNotIn("usage", store.RECORDS[rid])
                self.assertNotIn("cost", store.RECORDS[rid])
                self.assertNotIn("cost_missing", store.RECORDS[rid])

        log_text = self.log_path.read_text(encoding="utf-8") if self.log_path.exists() else ""
        self.assertEqual(log_text, "")
        for sentinel in ("ws_diagnostic", "output", *wire_ids):
            self.assertNotIn(sentinel, log_text)


if __name__ == "__main__":
    unittest.main()
