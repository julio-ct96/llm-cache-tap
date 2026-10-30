import json
import tempfile
import unittest
from pathlib import Path

from cachetap import providers, response_body
from tests.replay import adapter, builders, flows, scenario


class CaptureRegressionTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        adapter.reset(Path(tmp.name) / "requests.jsonl")
        self.case = json.loads(
            (Path(__file__).parent / "fixtures" / "copilot_responses_ws.json").read_text(
                encoding="utf-8"
            )
        )

    def _flow(self, method, path):
        request = flows.FakeRequest(
            method, self.case["host"], path, "{}", 1790000000.0
        )
        return flows.FakeFlow(request)

    def _fixture_result(self):
        client = {
            key: value
            for key, value in self.case["client"].items()
            if key not in {"type", "headers"}
        }
        step = scenario.Step(
            "copilot-responses",
            0,
            self.case["host"],
            self.case["path"],
            client,
            200,
            [builders.sse(*self.case["server"])],
            None,
        )
        return scenario.run([step])

    def test_known_http_routes(self):
        hooks = adapter.hooks()
        paths = ("/v1/messages?beta=true", "/responses?api-version=1", "/v1/chat/completions/")
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(hooks._is_llm(self._flow("POST", path)))

    def test_router_is_not_inference(self):
        hooks = adapter.hooks()
        for method, path in (("POST", "/auto"), ("GET", "/responses")):
            with self.subTest(method=method, path=path):
                flow = self._flow(method, path)
                self.assertFalse(hooks._is_llm(flow))
                hooks.request(flow)
                self.assertEqual(adapter.records(), [])
                self.assertNotIn("tap_id", flow.metadata)

    def test_response_payload_already_normalizes(self):
        body = builders.sse(*self.case["server"])
        events = response_body.usage_events(body)
        self.assertEqual(providers.normalize(events), self.case["expected"]["usage"])
        output, _ = response_body.output_text(body)
        self.assertEqual(output, "Hola mundo")

    def test_same_payload_over_http_has_known_result(self):
        result = self._fixture_result()
        self.assertEqual(len(result["records"]), 1)
        row = result["records"][0]
        expected = self.case["expected"]

        self.assertEqual(row["model"], expected["model"])
        self.assertEqual(row["usage"], expected["usage"])
        self.assertEqual(row["output"], expected["output"])
        self.assertEqual(row["verdict"], expected["verdict"])
        self.assertEqual(row["ttl_s"], expected["ttl_s"])
        self.assertEqual(row["cost"]["tariff"], expected["tariff"])
        for amount in ("usd", "no_cache_usd", "saved_usd"):
            with self.subTest(amount=amount):
                self.assertEqual(row["cost"][amount], expected[amount])

    def test_secrets_are_not_usage_or_log_fields(self):
        result = self._fixture_result()
        row = result["records"][0]
        sentinel = "SYNTHETIC_SECRET_DO_NOT_STORE"

        self.assertNotIn(sentinel, json.dumps(row["usage"], ensure_ascii=False))
        self.assertNotIn(sentinel, json.dumps(result["events"], ensure_ascii=False))
        self.assertNotIn(sentinel, json.dumps(result["log_lines"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
