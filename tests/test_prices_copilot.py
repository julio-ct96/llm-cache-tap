import unittest

from cachetap.prices import anthropic, copilot, openai


class ServesTest(unittest.TestCase):
    def test_copilot_hosts(self):
        self.assertTrue(copilot.serves("api.githubcopilot.com"))
        self.assertTrue(copilot.serves("api.business.githubcopilot.com"))

    def test_other_hosts(self):
        self.assertFalse(copilot.serves("api.anthropic.com"))
        self.assertFalse(copilot.serves("notgithubcopilot.com"))
        self.assertFalse(copilot.serves(""))


class PricesTest(unittest.TestCase):
    def test_claude_rows_have_a_single_write_rate(self):
        for model in anthropic.PRICES:
            with self.subTest(model=model):
                price = copilot.PRICES[model]
                self.assertNotIn("write_1h", price)
                self.assertEqual(price["write"], anthropic.PRICES[model]["write"])
                self.assertEqual(price["input"], anthropic.PRICES[model]["input"])

    def test_gpt_rows_are_the_list_price(self):
        self.assertEqual(copilot.PRICES["gpt-6.1-sol"], openai.PRICES["gpt-6.1-sol"])

    def test_gpt_5_6_luna_long_context_starts_earlier(self):
        self.assertEqual(copilot.PRICES["gpt-5.6-luna"]["over"], 200_000)
        self.assertEqual(openai.PRICES["gpt-5.6-luna"]["over"], 272_000)
        self.assertEqual(copilot.PRICES["gpt-5.6-luna"]["long"], openai.PRICES["gpt-5.6-luna"]["long"])

    def test_utility_models_are_free_and_say_why(self):
        for model in ("gpt-4.1", "gpt-4o", "gpt-4o-mini"):
            with self.subTest(model=model):
                price = copilot.PRICES[model]
                self.assertEqual((price["input"], price["read"], price["output"]), (0, 0, 0))
                self.assertIn("utilitario", price["note"])

    def test_grok_long_context_doubles_everything(self):
        self.assertEqual(
            copilot.PRICES["grok-4.7"],
            {
                "input": 2,
                "read": 0.5,
                "output": 6,
                "over": 200_000,
                "long": {"input": 4, "read": 1, "output": 12},
            },
        )

    def test_other_vendors(self):
        self.assertEqual(copilot.PRICES["gemini-3.8-flash"], {"input": 0.75, "read": 0.075, "output": 3.75})
        self.assertEqual(copilot.PRICES["kimi-k3"], {"input": 3, "read": 0.3, "output": 15})
        self.assertEqual(copilot.PRICES["mai-code-1.1-flash"], {"input": 0.2, "read": 0.02, "output": 1.2})


if __name__ == "__main__":
    unittest.main()
