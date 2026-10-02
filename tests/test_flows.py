import json
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


if __name__ == "__main__":
    unittest.main()
