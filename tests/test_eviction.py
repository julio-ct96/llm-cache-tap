import unittest

from tests.replay import adapter, builders, scenario


class EvictionTest(unittest.TestCase):
    def test_oldest_requests_and_bodies_are_evicted(self):
        old_max = adapter.set_max(3)
        self.addCleanup(adapter.set_max, old_max)
        steps = [
            scenario.Step(
                key=f"V{k}", t=10 * k, host="api.anthropic.com", path="/v1/messages",
                body=builders.claude_body("claude-opus-5-5", f"V{k}", 1), status=200,
                chunks=builders.anthropic_sse(0, 0, 600), expect="COLD",
            )
            for k in range(1, 6)
        ]
        result = scenario.run(steps)
        self.assertEqual([r["id"] for r in result["records"]], [3, 4, 5])
        self.assertEqual(result["body_ids"], [3, 4, 5])
        self.assertEqual(len(result["log_lines"]), 5)
        self.assertEqual(len(result["events"]), 15)
        record_events = [event for event in result["events"] if event["type"] == "record"]
        self.assertEqual(record_events[9]["evicted_ids"], [1])
        self.assertEqual(record_events[12]["evicted_ids"], [2])


if __name__ == "__main__":
    unittest.main()
