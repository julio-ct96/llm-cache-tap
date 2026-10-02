import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from cachetap import config, dashboard
from tests.replay import adapter, builders, scenario
from tests.replay.scenario import Step


class DashboardTest(unittest.TestCase):
    def setUp(self):
        steps = [
            Step(key="W1", t=0, host="api.anthropic.com", path="/v1/messages",
                 body=builders.claude_body("claude-opus-5-5", "W", 1), status=200,
                 chunks=builders.anthropic_sse(0, 3000, 20), expect="COLD"),
            Step(key="W2", t=60, host="api.anthropic.com", path="/v1/messages",
                 body=builders.claude_body("claude-opus-5-5", "W", 2), status=200,
                 chunks=builders.anthropic_sse(3000, 200, 20), expect="HIT"),
        ]
        scenario.run(steps)
        server = ThreadingHTTPServer(("127.0.0.1", 0), adapter.handler())
        server.daemon_threads = True
        self.port = server.server_address[1]
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

    def _request(self, method, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        conn.request(method, path, headers=headers or {})
        return conn.getresponse()

    def test_index(self):
        res = self._request("GET", "/")
        body = res.read().decode("utf-8")
        self.assertEqual(res.status, 200)
        self.assertTrue(res.getheader("Content-Type").startswith("text/html"))
        self.assertIn("<title>LLM cache tap</title>", body)
        self.assertEqual(res.getheader("Cache-Control"), "no-store")

    def test_static_file(self):
        res = self._request("GET", "/app.js")
        res.read()
        self.assertEqual(res.status, 200)
        self.assertTrue(res.getheader("Content-Type").startswith("text/javascript"))

    def test_font(self):
        res = self._request("GET", "/fonts/ibm-plex-mono-latin-400-normal.woff2")
        res.read()
        self.assertEqual(res.status, 200)
        self.assertEqual(res.getheader("Content-Type"), "font/woff2")
        self.assertEqual(res.getheader("Cache-Control"), "max-age=86400")

    def test_record(self):
        res = self._request("GET", "/api/record/2")
        rec = json.loads(res.read())
        self.assertEqual(res.status, 200)
        self.assertEqual(rec["id"], 2)
        self.assertEqual(rec["verdict"], "HIT")
        self.assertIn("segs", rec)
        self.assertEqual([k for k in rec if k.startswith("_")], [])

    def test_body(self):
        res = self._request("GET", "/api/body/1")
        body = json.loads(res.read())
        self.assertEqual(res.status, 200)
        self.assertEqual(body["model"], "claude-opus-5-5")

    def test_missing_record(self):
        res = self._request("GET", "/api/record/99")
        res.read()
        self.assertEqual(res.status, 404)

    def test_path_outside_ui(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        conn.putrequest("GET", "/../tap.py", skip_host=False, skip_accept_encoding=True)
        conn.endheaders()
        res = conn.getresponse()
        res.read()
        self.assertEqual(res.status, 404)

    def test_unserved_extension(self):
        res = self._request("GET", "/fonts/OFL.txt")
        res.read()
        self.assertEqual(res.status, 404)

    def test_foreign_host(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        conn.putrequest("GET", "/", skip_host=True)
        conn.putheader("Host", "evil.example")
        conn.endheaders()
        res = conn.getresponse()
        res.read()
        self.assertEqual(res.status, 403)

    def test_unknown_post_route(self):
        res = self._request("POST", "/api/otra")
        res.read()
        self.assertEqual(res.status, 404)

    def test_events(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/events")
        res = conn.getresponse()
        try:
            self.assertEqual(res.status, 200)
            self.assertEqual(res.getheader("Content-Type"), "text/event-stream")
            line = res.readline().decode("utf-8")
            self.assertTrue(line.startswith("data: "))
            event = json.loads(line[len("data: "):])
            self.assertEqual(event["type"], "snapshot")
            self.assertEqual(len(event["recs"]), 2)
            self.assertEqual(event["ttl"], 300)
        finally:
            conn.close()

    def test_clear(self):
        q = adapter.subscribe()
        res = self._request("POST", "/api/clear")
        res.read()
        self.assertEqual(res.status, 200)
        self.assertEqual(adapter.records(), [])
        self.assertEqual(adapter.body_ids(), [])
        self.assertEqual(q.get_nowait(), {"type": "clear"})

    def test_start_and_stop(self):
        with mock.patch.object(config, "UI_PORT", 0):
            servidor = dashboard.start()
        self.addCleanup(dashboard.stop)
        port = servidor.server_address[1]
        self.assertNotEqual(port, 0)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/")
        res = conn.getresponse()
        res.read()
        self.assertEqual(res.status, 200)
        dashboard.stop()
        dashboard.stop()


if __name__ == "__main__":
    unittest.main()
