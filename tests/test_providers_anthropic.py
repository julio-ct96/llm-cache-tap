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


if __name__ == "__main__":
    unittest.main()
