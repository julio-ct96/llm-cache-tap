"""Offline tests of the Copilot billing comparison; no proxy, CLI or network."""

import contextlib
import io
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

import scripts.check_copilot_prices as check

NOW = datetime(2026, 11, 18, tzinfo=UTC)


def billing(default, long=None, promo=None):
    token_prices = {"batch_size": 1_000_000, "default": default}
    if long is not None:
        token_prices["long_context"] = long
    entry = {"token_prices": token_prices}
    if promo is not None:
        entry["promo"] = promo
    return entry


MAI_CODE_2 = billing(
    {"input_price": 100, "cache_read_price": 5, "cache_write_price": 0, "output_price": 500},
    promo={"discount_percent": 50, "ends_at": "2027-05-18T00:00:00Z"},
)
HAIKU_5_5 = billing(
    {"input_price": 10, "cache_read_price": 1, "cache_write_price": 12.5,
     "cache_write_1h_price": 20, "output_price": 50, "max_prompt_tokens": 100000},
    long={"input_price": 50, "cache_read_price": 5, "cache_write_price": 62.5,
          "cache_write_1h_price": 100, "output_price": 250},
)  # fmt: skip


class BilledRatesTest(unittest.TestCase):
    def test_credits_become_dollars_and_a_running_promotion_applies(self):
        self.assertEqual(
            check.billed_rates(MAI_CODE_2, NOW),
            {"rates": {"input": 0.5, "read": 0.025, "output": 2.5}},
        )

    def test_promotion_ends_at_its_instant(self):
        ended = datetime(2027, 5, 18, tzinfo=UTC)
        self.assertEqual(
            check.billed_rates(MAI_CODE_2, ended),
            {"rates": {"input": 1, "read": 0.05, "output": 5}},
        )

    def test_long_tier_is_kept_only_when_it_costs_more(self):
        same = billing({"input_price": 200, "cache_read_price": 10, "output_price": 1000,
                        "max_prompt_tokens": 200000},
                       long={"input_price": 200, "cache_read_price": 10, "output_price": 1000})  # fmt: skip
        self.assertNotIn("long", check.billed_rates(same, NOW))
        tiered = check.billed_rates(HAIKU_5_5, NOW)
        self.assertEqual(tiered["over"], 100000)
        self.assertEqual(tiered["long"]["write_1h"], 1)

    def test_entries_without_prices_are_skipped(self):
        for entry in (None, {}, {"token_prices": {}}, {"token_prices": {"default": "x"}}):
            with self.subTest(entry=entry):
                self.assertIsNone(check.billed_rates(entry, NOW))


class CompareTest(unittest.TestCase):
    def test_table_matches_published_billing(self):
        differences, unpriced = check.compare(
            {"mai-code-2": MAI_CODE_2, "claude-haiku-5.5": HAIKU_5_5}, NOW
        )
        self.assertEqual((differences, unpriced), ([], []))

    def test_a_different_price_is_reported(self):
        luna = billing({"input_price": 11, "cache_read_price": 1, "cache_write_price": 12.5,
                        "output_price": 50})  # fmt: skip
        differences, _ = check.compare({"gpt-6-luna": luna}, NOW)
        self.assertEqual(len(differences), 1)
        self.assertTrue(differences[0].startswith("gpt-6-luna: facturado"))

    def test_models_without_a_price_are_listed_apart(self):
        free = billing({"input_price": 0, "cache_read_price": 0, "output_price": 0})
        differences, unpriced = check.compare({"text-embedding-3-small": free}, NOW)
        self.assertEqual(differences, [])
        self.assertEqual(len(unpriced), 1)
        self.assertTrue(unpriced[0].startswith("text-embedding-3-small: facturado"))

    def test_unknown_price_fields_are_reported(self):
        entry = billing({"input_price": 10, "cache_read_price": 1, "cache_write_price": 12.5,
                         "cache_write_12h_price": 25, "output_price": 50})  # fmt: skip
        differences, _ = check.compare({"gpt-6-luna": entry}, NOW)
        self.assertIn("gpt-6-luna: campos de precio sin comparar: cache_write_12h_price", differences)


class MainTest(unittest.TestCase):
    def test_without_run_makes_no_request(self):
        output = io.StringIO()
        with patch.object(check, "read_billing") as read, contextlib.redirect_stdout(output):
            self.assertEqual(check.main([]), 0)
        read.assert_not_called()
        self.assertEqual(output.getvalue().strip(), check.READY)

    def test_differences_fail_the_run(self):
        luna = billing({"input_price": 11, "cache_read_price": 1, "output_price": 50})
        with patch.object(check, "read_billing", return_value={"gpt-6-luna": luna}):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(["--run"]), 1)


if __name__ == "__main__":
    unittest.main()
