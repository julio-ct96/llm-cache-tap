import json
import tempfile
import unittest
from datetime import UTC, datetime
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
        request = flows.FakeRequest(method, self.case["host"], path, "{}", 1790000000.0)
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

    def test_native_gemini_routes_require_the_developer_api_host(self):
        for host, method in (("example.org", "POST"), ("generativelanguage.googleapis.com", "GET")):
            req = flows.FakeRequest(
                method, host, "/v1beta/models/gemini-4-argon:generateContent", "{}", 1790000000.0
            )
            self.assertFalse(adapter.hooks()._is_llm(flows.FakeFlow(req)))

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

    def test_gpt_62_ignores_instructions_but_compares_developer_message(self):
        host, path = "api.githubcopilot.com", "/v1/responses"
        user = {"role": "user", "content": "cached question"}

        def step(t, instructions, developer, cached):
            body = {
                "model": "gpt-6.2-sol",
                "input": [
                    {"role": "developer", "content": developer},
                    user,
                ],
            }
            if instructions:
                body["instructions"] = instructions
            data = {
                "usage": {"input_tokens": 8000, "input_tokens_details": {"cached_tokens": cached}}
            }
            return scenario.Step("gpt-6.2", t, host, path, body, 200, [json.dumps(data)], None)

        first, partial, moved, changed = scenario.run(
            [
                step(0, "old uncached text", "stable", 0),
                step(4, "new uncached text", "stable", 5000),
                step(8, None, "stable", 7900),
                step(12, None, "changed", 0),
            ]
        )["records"]
        self.assertTrue(first["uncached_instructions"])
        self.assertEqual([seg["name"] for seg in first["segs"]], ["msg0:developer", "msg1:user"])
        self.assertEqual(
            (partial["verdict"], partial["prefix_intact"], partial["server_side"]),
            ("PARTIAL", True, False),
        )
        self.assertNotIn("lost_usd", partial["cost"])
        self.assertIn("no se estima el coste perdido", " ".join(partial["notes"]))
        self.assertNotIn("uncached_instructions", moved)
        self.assertEqual(moved["verdict"], "HIT")
        self.assertEqual(changed["diverge_at"], "msg0:developer")
        self.assertIn("stable", changed["diff"]["before"])

    def test_gpt_62_prices_mixed_retention_writes_from_usage(self):
        payload = {
            "usage": {
                "input_tokens": 12000,
                "output_tokens": 100,
                "input_tokens_details": {
                    "cached_tokens": 4000,
                    "cache_write_tokens": 7000,
                    "cache_write_tokens_details": {"ttl_30m_tokens": 3000, "ttl_12h_tokens": 4000},
                },
            }
        }
        req = {"model": "gpt-6.2-sol", "input": "question", "prompt_cache_options": {"ttl": "12h"}}
        step = scenario.Step(
            "gpt-6.2", 0, "api.openai.com", "/responses", req, 200, [json.dumps(payload)], None
        )
        (row,) = scenario.run([step])["records"]
        self.assertEqual(row["ttl_s"], 43200)
        self.assertEqual(row["cost"]["write_12h"], 4000)
        self.assertAlmostEqual(row["cost"]["usd"], 0.0309)

    def test_google_native_json_and_sse_use_the_route_model_and_usage(self):
        host = "generativelanguage.googleapis.com"
        req = {
            "systemInstruction": {"parts": [{"text": "system"}]},
            "contents": [{"role": "user", "parts": [{"text": "question"}]}],
        }
        data = {
            "usageMetadata": {
                "promptTokenCount": 6000,
                "cachedContentTokenCount": 5000,
                "candidatesTokenCount": 10,
                "thoughtsTokenCount": 90,
            },
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"text": "not output", "thought": True},
                            {"text": "respuesta"},
                        ]
                    },
                }
            ],
        }
        json_path = "/v1beta/models/gemini-4-carbon:generateContent"
        stream_path = "/v1beta/models/gemini-4-carbon:streamGenerateContent"
        steps = [
            scenario.Step(
                "google",
                0,
                host,
                json_path + "?key=SYNTHETIC_KEY",
                req,
                200,
                [json.dumps(data)],
                None,
            ),
            scenario.Step(
                "google", 4, host, stream_path + "?alt=sse", req, 200, [builders.sse(data)], None
            ),
        ]
        result = scenario.run(steps, base_ts=datetime(2026, 12, 1, tzinfo=UTC).timestamp())
        for row, path in zip(result["records"], (json_path, stream_path)):
            self.assertEqual(
                (row["path"], row["model"], row["n_msgs"]), (path, "gemini-4-carbon", 1)
            )
            self.assertEqual(
                row["usage"],
                {
                    "input_total": 6000,
                    "uncached": 1000,
                    "read": 5000,
                    "write": None,
                    "output": 100,
                    "reasoning": 90,
                },
            )
            self.assertEqual((row["output"], row["stop_reason"]), ("respuesta", "STOP"))
            self.assertEqual((row["cost"]["tariff"], row["cost"]["usd"]), ("Google", 0.007))
        self.assertNotIn("SYNTHETIC_KEY", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
