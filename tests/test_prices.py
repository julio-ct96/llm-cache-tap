import unittest

from cachetap import prices
from cachetap.prices import base


class LookupTest(unittest.TestCase):
    def test_copilot_host_uses_the_copilot_table(self):
        tariff, price = prices.lookup("api.githubcopilot.com", "claude-opus-5.5")
        self.assertEqual(tariff, "Copilot")
        self.assertEqual(price["input"], 4)
        self.assertNotIn("write_1h", price)

    def test_host_is_compared_in_lower_case(self):
        self.assertEqual(prices.lookup("API.GitHubCopilot.com", "gpt-6-luna")[0], "Copilot")

    def test_direct_call_uses_the_list_price_of_the_owner(self):
        tariff, price = prices.lookup("api.anthropic.com", "claude-haiku-4-5-20251001")
        self.assertEqual(tariff, "Anthropic")
        self.assertEqual(price["write_1h"], 2)
        self.assertEqual(prices.lookup("api.openai.com", "gpt-6-luna")[0], "OpenAI")

    def test_copilot_does_not_fall_back_to_a_list_price(self):
        self.assertEqual(prices.lookup("api.githubcopilot.com", "gpt-5.2"), ("Copilot", None))

    def test_model_without_price(self):
        self.assertEqual(prices.lookup("api.openai.com", "gpt-5.2"), ("OpenAI", None))

    def test_unknown_provider(self):
        self.assertEqual(prices.lookup("api.mistral.ai", "mistral-large"), (None, None))
        self.assertEqual(prices.lookup(None, None), (None, None))


class ReferenceTest(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(set(prices.reference()), {"prices", "prices_reviewed"})
        self.assertEqual(prices.reference()["prices_reviewed"], "octubre de 2026")

    def test_rows(self):
        rows = prices.reference()["prices"]
        self.assertEqual(len(rows), 60)
        self.assertEqual({row["tariff"] for row in rows}, {"Copilot", "Anthropic", "OpenAI"})
        for row in rows:
            with self.subTest(tariff=row["tariff"], model=row["model"]):
                self.assertEqual(set(row), {"tariff", "model", "price"})
                self.assertLessEqual(row["price"]["read"], row["price"]["input"])

    def test_priced_names_are_canonical(self):
        for row in prices.reference()["prices"]:
            with self.subTest(model=row["model"]):
                self.assertEqual(base.canonical(row["model"]), row["model"])



if __name__ == "__main__":
    unittest.main()
