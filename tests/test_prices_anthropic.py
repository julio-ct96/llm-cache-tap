import unittest

from cachetap import providers
from cachetap.prices import anthropic


class PricesTest(unittest.TestCase):
    def test_opus_5_5(self):
        self.assertEqual(
            anthropic.PRICES["claude-opus-5.5"],
            {"input": 4, "read": 0.2, "write": 5, "write_1h": 8, "output": 20},
        )

    def test_fable_5_1_reads_cheaper_than_fable_5(self):
        self.assertEqual(anthropic.PRICES["claude-fable-5.1"]["read"], 0.25)
        self.assertEqual(anthropic.PRICES["claude-fable-5"]["read"], 1)

    def test_haiku_4_5(self):
        self.assertEqual(
            anthropic.PRICES["claude-haiku-4.5"],
            {"input": 1, "read": 0.1, "write": 1.25, "write_1h": 2, "output": 5},
        )

    def test_every_priced_model_is_owned(self):
        for model in anthropic.PRICES:
            with self.subTest(model=model):
                self.assertTrue(providers.anthropic.owns(model))


if __name__ == "__main__":
    unittest.main()
