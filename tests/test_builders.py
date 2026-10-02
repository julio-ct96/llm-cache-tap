import json
import unittest

from tests.replay import builders


class BuildersTest(unittest.TestCase):
    def test_turns(self):
        msgs = builders.turns("A", 3)
        self.assertEqual(len(msgs), 5)
        self.assertEqual(msgs[0], {"role": "user", "content": "A pregunta 1"})
        self.assertEqual(msgs[1], {"role": "assistant", "content": "A respuesta 1"})
        self.assertEqual(msgs[-1], {"role": "user", "content": "A pregunta 3"})

    def test_claude_body_keys(self):
        body = builders.claude_body("m", "A", 1)
        self.assertEqual(
            list(body), ["model", "max_tokens", "stream", "tools", "system", "messages"]
        )

    def test_claude_body_options(self):
        body = builders.claude_body(
            "m", "A", 1, tools=False, effort="high", thinking=True, system_ttl="1h"
        )
        self.assertNotIn("tools", body)
        self.assertEqual(body["output_config"], {"effort": "high"})
        self.assertEqual(
            body["system"][0]["cache_control"], {"type": "ephemeral", "ttl": "1h"}
        )
        self.assertIn("thinking", body)

    def test_claude_body_mark_last(self):
        body = builders.claude_body("m", "A", 2, mark_last=True)
        content = body["messages"][-1]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(len(content), 1)
        self.assertIn("cache_control", content[0])

    def test_responses_body_raw_input(self):
        self.assertEqual(
            builders.responses_body("m", "G", 1, raw_input="x"),
            {"model": "m", "stream": True, "input": "x"},
        )

    def test_chat_body(self):
        body = builders.chat_body("m", "H", 1)
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(len(body["messages"]), 2)

    def test_anthropic_sse(self):
        chunks = builders.anthropic_sse(1, 2, 3)
        self.assertEqual(len(chunks), 3)
        self.assertIn("content_block_delta", chunks[1])
        self.assertTrue(chunks[0].startswith("data: {"))

    def test_anthropic_sse_creation(self):
        chunks = builders.anthropic_sse(1, 2, 3, (4, 5))
        self.assertIn('"ephemeral_1h_input_tokens":5', chunks[0])

    def test_chat_sse_compact_delta(self):
        self.assertIn('"delta":{"content"', builders.chat_sse(10, 0)[1])

    def test_chat_sse_done(self):
        self.assertTrue(builders.chat_sse(10, 0)[2].endswith("data: [DONE]\n\n"))

    def test_chat_json(self):
        chunks = builders.chat_json(10, 4)
        self.assertEqual(len(chunks), 1)
        data = json.loads(chunks[0])
        self.assertEqual(data["usage"]["prompt_tokens_details"]["cached_tokens"], 4)


if __name__ == "__main__":
    unittest.main()
