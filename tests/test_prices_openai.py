import unittest

from cachetap import providers
from cachetap.prices import openai


class PricesTest(unittest.TestCase):
    def test_gpt_5_6_and_later_bill_cache_writes(self):
        self.assertEqual(
            openai.PRICES["gpt-6.1-sol"],
            {
                "input": 2,
                "read": 0.1,
                "output": 10,
                "write": 2.5,
                "over": 272_000,
                "long": {"input": 4, "read": 0.2, "output": 15, "write": 5},
            },
        )
        self.assertEqual(openai.PRICES["gpt-6-luna"]["write"], 0.125)

    def test_earlier_models_do_not_bill_cache_writes(self):
        for model in ("gpt-5.5", "gpt-5.4", "gpt-5-mini", "gpt-4.1"):
            with self.subTest(model=model):
                self.assertNotIn("write", openai.PRICES[model])

    def test_small_models_have_no_long_context_tier(self):
        self.assertEqual(openai.PRICES["gpt-5.4-mini"], {"input": 0.75, "read": 0.075, "output": 4.5})

    def test_every_priced_model_is_owned(self):
        for model in openai.PRICES:
            with self.subTest(model=model):
                self.assertTrue(providers.openai.owns(model))


if __name__ == "__main__":
    unittest.main()
