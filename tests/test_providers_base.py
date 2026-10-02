import unittest

from cachetap.providers import base


class VersionTest(unittest.TestCase):
    def test_gpt_with_minor(self):
        self.assertEqual(base.version("gpt-5.6-luna", "gpt"), (5, 6))

    def test_gpt_date_suffix_is_not_a_minor(self):
        self.assertEqual(base.version("gpt-5-2025-08-07", "gpt"), (5, 0))

    def test_gpt_letter_suffix(self):
        self.assertEqual(base.version("gpt-4o", "gpt"), (4, 0))

    def test_gpt_dotted_minor(self):
        self.assertEqual(base.version("gpt-4.1", "gpt"), (4, 1))

    def test_claude_opus_4_7(self):
        self.assertEqual(base.version("claude-opus-4-7", "claude-opus"), (4, 7))

    def test_claude_opus_5_5(self):
        self.assertEqual(base.version("claude-opus-5-5", "claude-opus"), (5, 5))

    def test_other_family_is_none(self):
        self.assertIsNone(base.version("mistral-large", "gpt"))

    def test_no_model_is_none(self):
        self.assertIsNone(base.version(None, "gpt"))


if __name__ == "__main__":
    unittest.main()
