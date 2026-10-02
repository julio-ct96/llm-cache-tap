import unittest

from tests.replay import builders, scenario


class ScenarioTest(unittest.TestCase):
    def test_single_cold_step(self):
        step = scenario.Step(
            key="X1", t=0, host="api.anthropic.com", path="/v1/messages?beta=true",
            body=builders.claude_body("claude-opus-5-5", "X", 1), status=200,
            chunks=builders.anthropic_sse(0, 3000, 20), expect="COLD",
        )
        result = scenario.run([step])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["body_ids"], [1])
        self.assertEqual(len(result["log_lines"]), 1)
        self.assertEqual(len(result["events"]), 3)
        self.assertEqual([e["rec"]["state"] for e in result["events"]], ["pending", "streaming", "done"])
        rec = result["records"][0]
        self.assertEqual(rec["verdict"], "COLD")
        self.assertEqual(rec["path"], "/v1/messages")
        self.assertEqual(rec["time"], "14:13:20")
        self.assertEqual(rec["hdr_s"], 0.25)
        self.assertEqual(rec["ttft_s"], 0.75)
        self.assertEqual(rec["total_s"], 1.95)
        self.assertEqual(rec["output"], "Hola mundo")
        self.assertEqual(rec["stop_reason"], "end_turn")
        self.assertEqual(rec["usage"], {"read": 0, "write": 3000, "uncached": 20,
                                        "input_total": 3020, "output": 50, "reasoning": None})
        self.assertEqual(set(rec["resp_headers"]),
                         {"request-id", "anthropic-ratelimit-requests-remaining", "via"})
