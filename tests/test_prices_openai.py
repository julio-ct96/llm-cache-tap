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

    def test_gpt_6_1_terra_has_the_published_rates(self):
        self.assertEqual(
            openai.PRICES["gpt-6.1-terra"],
            {
                "input": 1,
                "read": 0.05,
                "output": 5,
                "write": 1.25,
                "over": 272_000,
                "long": {"input": 2, "read": 0.1, "output": 7.5, "write": 2.5},
            },
        )

    def test_gpt_6_2_standard_and_long_context_rates(self):
        for model, short, long in (
            ("gpt-6.2-sol", (2, 0.1, 2.5, 5, 10), (4, 0.2, 5, 10, 15)),
            ("gpt-6.2-astra", (8, 0.4, 10, 20, 40), (16, 0.8, 20, 40, 60)),
        ):
            with self.subTest(model=model):
                keys = ("input", "read", "write", "write_12h", "output")
                price = openai.PRICES[model]
                self.assertEqual(price["over"], 272_000)
                self.assertEqual(tuple(price[key] for key in keys), short)
                self.assertEqual(tuple(price["long"][key] for key in keys), long)

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
