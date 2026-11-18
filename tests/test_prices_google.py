import unittest

from cachetap.prices import google


class PricesTest(unittest.TestCase):
    def test_added_models(self):
        self.assertEqual(
            google.PRICES["gemini-3.1-pro-preview"],
            {
                "input": 2,
                "read": 0.2,
                "output": 12,
                "over": 200_000,
                "long": {"input": 4, "read": 0.4, "output": 18},
            },
        )
        self.assertEqual(
            google.PRICES["gemini-2.5-pro"],
            {
                "input": 1.25,
                "read": 0.125,
                "output": 10,
                "over": 200_000,
                "long": {"input": 2.5, "read": 0.25, "output": 15},
            },
        )
        self.assertEqual(
            google.PRICES["gemini-3-flash-preview"],
            {"input": 0.5, "read": 0.05, "output": 3},
        )
        self.assertEqual(
            google.PRICES["gemini-2.5-flash-lite"],
            {"input": 0.1, "read": 0.01, "output": 0.4},
        )


if __name__ == "__main__":
    unittest.main()
