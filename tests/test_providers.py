import unittest
from unittest import mock

from cachetap import config, providers

UNKNOWN = {"ttl_s": config.TTL_S, "ttl_source": "supuesto: proveedor sin TTL conocido", "ttl_anchor": "end"}


class CacheTtlTest(unittest.TestCase):
    def test_forced_ttl(self):
        with mock.patch.object(config, "TTL_FORCED", 120):
            self.assertEqual(
                providers.cache_ttl({"model": "claude-opus-5-5"}),
                {"ttl_s": 120, "ttl_source": "forzado con TAP_TTL_S", "ttl_anchor": "end"},
            )

    def test_unknown_provider(self):
        with mock.patch.object(config, "TTL_FORCED", None):
            self.assertEqual(providers.cache_ttl({"model": "mistral-large"}), UNKNOWN)

    def test_no_model(self):
        with mock.patch.object(config, "TTL_FORCED", None):
            self.assertEqual(providers.cache_ttl({}), UNKNOWN)

    def test_claude(self):
        with mock.patch.object(config, "TTL_FORCED", None):
            self.assertEqual(providers.cache_ttl({"model": "Claude-Opus-5-5"})["ttl_anchor"], "start")

    def test_gpt(self):
        with mock.patch.object(config, "TTL_FORCED", None):
            self.assertEqual(providers.cache_ttl({"model": "gpt-5.6"})["ttl_s"], 1800)


class MinCacheableTest(unittest.TestCase):
    def test_claude_uppercase(self):
        self.assertEqual(providers.min_cacheable("CLAUDE-OPUS-4-7"), 2048)

    def test_gpt(self):
        self.assertEqual(providers.min_cacheable("gpt-5.6"), 1024)

    def test_unknown(self):
        self.assertEqual(providers.min_cacheable("mistral-large"), 1024)
        self.assertEqual(providers.min_cacheable(None), 1024)


class ReferenceTest(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(set(providers.reference()), {"ttl", "min_cacheable", "reviewed"})

    def test_ttl_rows(self):
        rows = providers.reference()["ttl"]
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["models"], "Claude (todos)")
        self.assertEqual(rows[-1]["models"], "Otros proveedores")
        for row in rows:
            self.assertEqual(set(row), {"models", "ttl", "anchor"})

    def test_min_cacheable_rows(self):
        rows = providers.reference()["min_cacheable"]
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertIsInstance(row["tokens"], int)

    def test_help_does_not_lie(self):
        for row in providers.reference()["min_cacheable"]:
            with self.subTest(example=row["example"]):
                self.assertEqual(providers.min_cacheable(row["example"]), row["tokens"])


class FirstTokenTest(unittest.TestCase):
    def test_marks(self):
        self.assertEqual(len(providers.FIRST_TOKEN), 4)
        self.assertEqual(providers.FIRST_TOKEN[0], b"content_block_delta")


class EffortOfTest(unittest.TestCase):
    def test_both_shapes(self):
        self.assertEqual(providers.effort_of({"output_config": {"effort": "high"}, "reasoning_effort": "low"}), "high")

    def test_absent(self):
        self.assertIsNone(providers.effort_of({}))


class NormalizeTest(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(providers.normalize([]))

    def test_merged_events(self):
        events = [
            {"event": "a", "usage": {"input_tokens": 20, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 10, "output_tokens": 1}},
            {"event": "b", "usage": {"output_tokens": 50, "input_tokens": None}},
        ]
        usage = providers.normalize(events)
        self.assertEqual(usage["output"], 50)
        self.assertEqual(usage["uncached"], 20)
        self.assertEqual(usage["input_total"], 30)

    def test_openai_usage(self):
        usage = providers.normalize([{"event": "a", "usage": {"prompt_tokens": 10}}])
        self.assertIsNone(usage["write"])
        self.assertEqual(usage["input_total"], 10)


class WrittenTtlTest(unittest.TestCase):
    def test_confirmed_write(self):
        events = [{"event": "x", "usage": {"cache_creation": {"ephemeral_1h_input_tokens": 9}}}]
        self.assertEqual(providers.written_ttl(events), 3600)


class DeltasTest(unittest.TestCase):
    def test_both_providers_in_order_and_openai_stop_wins(self):
        ev = {
            "delta": {"text": "a", "stop_reason": "x"},
            "choices": [{"delta": {"content": "b"}, "finish_reason": "y"}],
        }
        self.assertEqual(providers.deltas(ev), (["a", "b"], "y"))


if __name__ == "__main__":
    unittest.main()
