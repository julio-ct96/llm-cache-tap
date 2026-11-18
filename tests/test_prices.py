import unittest
from datetime import date

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

    def test_gemini_4_promotions_switch_without_falling_back_from_copilot(self):
        direct, copilot = "generativelanguage.googleapis.com", "api.githubcopilot.com"
        november, december = date(2026, 11, 30), date(2026, 12, 1)
        for host, tariff in ((direct, "Google"), (copilot, "Copilot")):
            for model in ("gemini-4-argon", "gemini-4-carbon"):
                with self.subTest(host=host, model=model):
                    name, promo = prices.lookup(host, model, at=november)
                    self.assertEqual(name, tariff)
                    self.assertEqual((promo["input"], promo["read"], promo["output"]), (2, 0.1, 10))
                    expected = None if host == copilot and model.endswith("argon") else {
                        "input": 4, "read": 0.2, "output": 20,
                    }
                    self.assertEqual(prices.lookup(host, model, at=december), (tariff, expected))

    def test_gemini_direct_is_not_a_vertex_or_gateway_rate(self):
        model = "gemini-4-hydrogen"
        self.assertEqual(prices.lookup("aiplatform.googleapis.com", model), (None, None))
        self.assertEqual(
            prices.lookup("generativelanguage.googleapis.com", model),
            ("Google", {"input": 1.5, "read": 0.075, "output": 7.5}),
        )

    def test_reference_agrees_with_dated_lookup(self):
        at = date(2027, 1, 1)
        rows = {(row["tariff"], row["model"]): row["price"] for row in prices.reference(at=at)["prices"]}
        self.assertNotIn(("Copilot", "gemini-4-argon"), rows)
        self.assertEqual(rows["Google", "gemini-3.8-flash"], {"input": 1.5, "read": 0.15, "output": 7.5})

    def test_unknown_provider(self):
        self.assertEqual(prices.lookup("api.mistral.ai", "mistral-large"), (None, None))
        self.assertEqual(prices.lookup(None, None), (None, None))


class ReferenceTest(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(set(prices.reference()), {"prices", "prices_reviewed"})
        self.assertEqual(prices.reference()["prices_reviewed"], "noviembre de 2026")

    def test_rows(self):
        rows = prices.reference(at=date(2026, 11, 18))["prices"]
        self.assertEqual(len(rows), 97)
        self.assertEqual({row["tariff"] for row in rows}, {"Copilot", "Anthropic", "OpenAI", "Google"})
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
