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
from tests.test_websocket_hooks import play_fixture


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
            conn.close()
            self._release_subscribers()

        status, payload = self._request(f"/api/record/{rid}")
        self.assertEqual(status, 200)
        detail = json.loads(payload)
        self.assertEqual(detail["state"], "done")
        self.assertEqual(detail["status"], 101)
        self.assertEqual(detail["transport"], "websocket")
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
            _snapshot_conn.close()
            self._release_subscribers()

        log_text = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", log_text)


if __name__ == "__main__":
    unittest.main()
