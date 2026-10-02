import unittest

from cachetap import response_body
from tests.replay import builders


def usage_of(chunks):
    return response_body.usage_events("".join(chunks))


class UsageEventsTest(unittest.TestCase):
    def test_usage_in_json(self):
        events = usage_of(builders.chat_json(10, 4))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "chat.completion")

    def test_json_without_usage(self):
        self.assertEqual(response_body.usage_events('{"type": "error"}'), [])

    def test_broken_json(self):
        self.assertEqual(response_body.usage_events("{no es json"), [])

    def test_anthropic_sse(self):
        events = usage_of(builders.anthropic_sse(1, 2, 3))
        self.assertEqual([e["event"] for e in events], ["message_start", "message_delta"])

    def test_responses_sse(self):
        events = usage_of(builders.responses_sse(10, 4))
        self.assertEqual([e["event"] for e in events], ["response.completed"])

    def test_broken_line(self):
        self.assertEqual(response_body.usage_events('data: {"usage" roto'), [])

    def test_unusable_sse_events_are_skipped(self):
        body = "".join(
            [
                'data: []\n\n',
                'data: null\n\n',
                'data: 42\n\n',
                'data: {"type":"response.output_text.delta","delta":"válido"}\n\n',
            ]
        )
        self.assertEqual(response_body.output_text(body), ("válido", None))

    def test_deeply_nested_sse_event_does_not_hide_later_delta(self):
        body = f'data: {"[" * 1100}null{ "]" * 1100}\n\n'
        body += 'data: {"type":"response.output_text.delta","delta":"válido"}\n\n'
        self.assertEqual(response_body.output_text(body), ("válido", None))


class OutputTextTest(unittest.TestCase):
    def test_anthropic_text(self):
        body = "".join(builders.anthropic_sse(1, 2, 3))
        self.assertEqual(response_body.output_text(body), ("Hola mundo", "end_turn"))

    def test_responses_text(self):
        body = "".join(builders.responses_sse(10, 4))
        self.assertEqual(response_body.output_text(body), ("Hola mundo", None))

    def test_chat_text(self):
        body = "".join(builders.chat_sse(10, 4))
        self.assertEqual(response_body.output_text(body), ("Hola mundo", "stop"))

    def test_json_body(self):
        body = "".join(builders.chat_json(10, 4))
        self.assertEqual(response_body.output_text(body), ("", None))

    def test_text_is_cut(self):
        body = builders.sse({"type": "content_block_delta", "delta": {"text": "x" * 3000}})
        text, _ = response_body.output_text(body)
        self.assertEqual(len(text), 2000)


if __name__ == "__main__":
    unittest.main()
