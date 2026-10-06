import unittest

from cachetap.prices import base


class CanonicalTest(unittest.TestCase):
    def test_dashed_minor_becomes_dotted(self):
        self.assertEqual(base.canonical("claude-opus-5-5"), "claude-opus-5.5")

    def test_date_suffix_is_dropped(self):
        self.assertEqual(base.canonical("claude-haiku-4-5-20251001"), "claude-haiku-4.5")
        self.assertEqual(base.canonical("gpt-5-2025-08-07"), "gpt-5")

    def test_dotted_names_are_kept(self):
        for name in ("gpt-5.6-luna", "gpt-4.1", "gpt-5-mini", "gpt-6.1-sol", "kimi-k2.7-code"):
            with self.subTest(name=name):
                self.assertEqual(base.canonical(name), name)

    def test_case_and_spaces(self):
        self.assertEqual(base.canonical(" Claude-Sonnet-5 "), "claude-sonnet-5")

    def test_empty(self):
        self.assertEqual(base.canonical(""), "")


class LongContextTest(unittest.TestCase):
    def test_doubles_input_and_cache_and_scales_output(self):
        price = base.long_context({"input": 2, "read": 0.2, "write": 2.5, "output": 10}, 272_000)
        self.assertEqual(price["over"], 272_000)
        self.assertEqual(price["long"], {"input": 4, "read": 0.4, "write": 5, "output": 15})
        self.assertEqual(price["input"], 2)

    def test_rates_without_write_stay_without_it(self):
        price = base.long_context({"input": 5, "read": 0.5, "output": 30}, 272_000)
        self.assertNotIn("write", price["long"])


if __name__ == "__main__":
    unittest.main()
