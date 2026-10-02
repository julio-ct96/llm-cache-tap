import json
import logging
import tempfile
import unittest
from pathlib import Path

from tests.replay import adapter
from tests.replay.flows import FakeFlow, FakeRequest


class FlowsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        adapter.reset(Path(tmp.name) / "requests.jsonl")

    def test_request_hook_records_pending_flow(self):
        body = {"model": "claude-opus-5-5", "messages": [{"role": "user", "content": "hola"}]}
        flow = FakeFlow(FakeRequest("POST", "api.anthropic.com", "/v1/messages", json.dumps(body), 1790000000.0))
        adapter.hooks().request(flow)
        recs = adapter.records()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["id"], 1)
        self.assertEqual(recs[0]["state"], "pending")
        self.assertEqual(recs[0]["model"], "claude-opus-5-5")
        self.assertEqual(flow.request.headers["accept-encoding"], "identity")
        self.assertEqual(flow.metadata["tap_id"], 1)
        self.assertEqual(adapter.body_ids(), [1])

    def test_ignored_routes_are_not_recorded(self):
        for method, path in (("GET", "/v1/messages"), ("POST", "/v1/models")):
            with self.subTest(method=method, path=path):
                flow = FakeFlow(FakeRequest(method, "api.anthropic.com", path, "{}", 1790000000.0))
                adapter.hooks().request(flow)
                self.assertEqual(adapter.records(), [])
                self.assertNotIn("tap_id", flow.metadata)

    def test_broken_json_is_recorded_without_model(self):
        flow = FakeFlow(FakeRequest("POST", "api.anthropic.com", "/v1/messages", "esto no es JSON", 1790000000.0))
        adapter.hooks().request(flow)
        recs = adapter.records()
        self.assertEqual(len(recs), 1)
        self.assertIsNone(recs[0]["model"])

    def test_uninspectable_request_is_not_recorded_and_warning_has_no_body(self):
        body = '{"messages": 7, "secret": "private body"}'
        flow = FakeFlow(FakeRequest("POST", "api.anthropic.com", "/v1/messages", body, 1790000000.0))
        with self.assertLogs("tap", level="WARNING") as logs:
            adapter.hooks().request(flow)
        self.assertEqual(adapter.records(), [])
        self.assertNotIn("tap_id", flow.metadata)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("messages debe ser una lista o null", logs.output[0])
        self.assertNotIn(body, logs.output[0])

    def test_input_string_counts_as_one_message(self):
        flow = FakeFlow(FakeRequest(
            "POST", "api.openai.com", "/v1/responses", '{"input":"hola"}', 1790000000.0
        ))
        adapter.hooks().request(flow)
        rec = adapter.records()[0]
        self.assertEqual(rec["n_msgs"], 1)
        self.assertEqual([segment["name"] for segment in rec["segs"]], ["msg0:text"])

    def test_input_list_keeps_scalar_elements(self):
        flow = FakeFlow(FakeRequest(
            "POST", "api.openai.com", "/v1/responses", '{"input":["texto",42]}', 1790000000.0
        ))
        adapter.hooks().request(flow)
        rec = adapter.records()[0]
        self.assertEqual(rec["n_msgs"], 2)
        self.assertEqual([segment["name"] for segment in rec["segs"]], ["msg0:text", "msg1:text"])


if __name__ == "__main__":
    unittest.main()
