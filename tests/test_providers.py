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


class WrittenTtlTest(unittest.TestCase):
    def test_confirmed_write(self):
        events = [{"event": "x", "usage": {"cache_creation": {"ephemeral_1h_input_tokens": 9}}}]
        self.assertEqual(providers.written_ttl(events), 3600)


if __name__ == "__main__":
    unittest.main()
