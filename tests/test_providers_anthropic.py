import unittest

from cachetap.providers import anthropic


def M(ttl=None):
    cc = {"type": "ephemeral"}
    if ttl:
        cc["ttl"] = ttl
    return {"type": "text", "text": "x", "cache_control": cc}


def E(u):
    return {"event": "x", "usage": u}


def made(five, hour):
    return E({"cache_creation": {"ephemeral_5m_input_tokens": five, "ephemeral_1h_input_tokens": hour}})


class OwnsTest(unittest.TestCase):
    def test_claude(self):
        self.assertTrue(anthropic.owns("claude-opus-5-5"))

    def test_gpt(self):
        self.assertFalse(anthropic.owns("gpt-5.6"))

    def test_empty(self):
        self.assertFalse(anthropic.owns(""))


class CacheTtlTest(unittest.TestCase):
    MODEL = "claude-opus-5-5"
    DEFAULT = {"ttl_s": 300, "ttl_source": "por defecto de Claude", "ttl_anchor": "start"}

    def test_no_marks(self):
        self.assertEqual(anthropic.cache_ttl({}, self.MODEL), self.DEFAULT)

    def test_mark_without_ttl(self):
        self.assertEqual(anthropic.cache_ttl({"system": [M()]}, self.MODEL), self.DEFAULT)

    def test_one_hour(self):
        self.assertEqual(
            anthropic.cache_ttl({"system": [M("1h")]}, self.MODEL),
            {"ttl_s": 3600, "ttl_source": "declarado en cache_control", "ttl_anchor": "start"},
        )

    def test_shortest_mark_wins(self):
        self.assertEqual(
            anthropic.cache_ttl({"system": [M("1h"), M()]}, self.MODEL),
            {"ttl_s": 300, "ttl_source": "declarado en cache_control", "ttl_anchor": "start"},
        )

    def test_thirty_minutes(self):
        self.assertEqual(anthropic.cache_ttl({"system": [M("30m")]}, self.MODEL)["ttl_s"], 1800)


class MinCacheableTest(unittest.TestCase):
    def test_by_model(self):
        cases = {
            "claude-fable-5-1": 512,
            "claude-mythos-5-1": 512,
            "claude-mythos-preview": 2048,
            "claude-opus-5-5": 512,
            "claude-sonnet-5-5": 512,
            "claude-opus-4-8": 1024,
            "claude-opus-4-7": 2048,
            "claude-opus-4-6": 4096,
            "claude-opus-4-5": 4096,
            "claude-haiku-4-5": 4096,
            "claude-haiku-3-5": 2048,
            "claude-sonnet-4-5": 1024,
            "claude-3-5-haiku-20241022": 1024,
        }
        for model, expected in cases.items():
            with self.subTest(model=model):
                self.assertEqual(anthropic.min_cacheable(model), expected)


class EffortTest(unittest.TestCase):
    def test_declared(self):
        self.assertEqual(anthropic.effort({"output_config": {"effort": "high"}}), "high")

    def test_not_a_dict(self):
        self.assertIsNone(anthropic.effort({"output_config": "x"}))

    def test_absent(self):
        self.assertIsNone(anthropic.effort({}))


class NormalizeTest(unittest.TestCase):
    def test_cache_fields(self):
        merged = {"input_tokens": 20, "cache_creation_input_tokens": 3000, "cache_read_input_tokens": 0, "output_tokens": 50}
        self.assertEqual(
            anthropic.normalize(merged),
            {"read": 0, "write": 3000, "uncached": 20, "input_total": 3020, "output": 50, "reasoning": None},
        )

    def test_invalid_token_counters_are_ignored(self):
        self.assertEqual(
            anthropic.normalize(
                {
                    "input_tokens": "20",
                    "cache_creation_input_tokens": True,
                    "cache_read_input_tokens": -1,
                    "output_tokens": "5",
                }
            ),
            {"read": 0, "write": 0, "uncached": 0, "input_total": 0, "output": 0, "reasoning": None},
        )

    def test_other_shape(self):
        self.assertIsNone(anthropic.normalize({"prompt_tokens": 5}))


class WrittenTtlTest(unittest.TestCase):
    def test_one_hour(self):
        self.assertEqual(anthropic.written_ttl([made(0, 5000)]), 3600)

    def test_five_minutes(self):
        self.assertEqual(anthropic.written_ttl([made(50, 0)]), 300)

    def test_nothing_written(self):
        self.assertIsNone(anthropic.written_ttl([made(0, 0)]))

    def test_no_breakdown(self):
        self.assertIsNone(anthropic.written_ttl([E({"output_tokens": 5})]))

    def test_no_events(self):
        self.assertIsNone(anthropic.written_ttl([]))


class DeltasTest(unittest.TestCase):
    def test_text(self):
        self.assertEqual(anthropic.deltas({"delta": {"text": "a"}}), (["a"], None))

    def test_stop_reason(self):
        self.assertEqual(anthropic.deltas({"delta": {"stop_reason": "end_turn"}}), ([], "end_turn"))

    def test_non_string_stop_reason_is_ignored(self):
        self.assertEqual(anthropic.deltas({"delta": {"stop_reason": 12}}), ([], None))

    def test_delta_not_a_dict(self):
        self.assertEqual(anthropic.deltas({"delta": "a"}), ([], None))

    def test_no_delta(self):
        self.assertEqual(anthropic.deltas({}), ([], None))


if __name__ == "__main__":
    unittest.main()
