import unittest

from cachetap import cost
from cachetap.prices import anthropic, copilot, openai


def U(read, write, uncached, output, reasoning=None):
    return {
        "read": read,
        "write": write,
        "uncached": uncached,
        "input_total": read + (write or 0) + uncached,
        "output": output,
        "reasoning": reasoning,
    }


OPUS = anthropic.PRICES["claude-opus-5.5"]  # 4 input, 0.2 read, 5 write, 8 write 1h, 20 output


class ComputeTest(unittest.TestCase):
    def test_parts_add_up_to_the_cost(self):
        c = cost.compute(U(1_000_000, 100_000, 10_000, 1_000), OPUS, "Anthropic")
        self.assertEqual(c["parts"], {"uncached": 0.04, "read": 0.2, "write": 0.5, "output": 0.02})
        self.assertEqual(c["usd"], 0.76)
        self.assertEqual(c["tariff"], "Anthropic")

    def test_saved_is_what_no_cache_would_have_cost_minus_the_cost(self):
        c = cost.compute(U(1_000_000, 0, 0, 0), OPUS, "Anthropic")
        self.assertEqual(c["no_cache_usd"], 4.0)
        self.assertEqual(c["saved_usd"], 3.8)

    def test_a_write_with_nothing_read_costs_more_than_no_cache(self):
        c = cost.compute(U(0, 1_000_000, 0, 0), OPUS, "Anthropic")
        self.assertEqual(c["usd"], 5.0)
        self.assertEqual(c["saved_usd"], -1.0)

    def test_one_hour_writes_pay_their_own_rate(self):
        c = cost.compute(U(0, 1_000_000, 0, 0), OPUS, "Anthropic", write_1h=400_000)
        self.assertEqual(c["parts"]["write"], 0.6 * 5 + 0.4 * 8)
        self.assertEqual(c["write_1h"], 400_000)

    def test_one_hour_writes_never_exceed_what_was_written(self):
        c = cost.compute(U(0, 100, 0, 0), OPUS, "Anthropic", write_1h=5_000)
        self.assertEqual(c["write_1h"], 100)

    def test_unreported_write_costs_nothing(self):
        c = cost.compute(U(0, None, 100_000, 0), openai.PRICES["gpt-5.5"], "OpenAI")
        self.assertEqual(c["parts"]["write"], 0)
        self.assertEqual(c["usd"], 0.5)

    def test_write_without_its_own_rate_pays_as_input(self):
        c = cost.compute(U(0, 100_000, 0, 0), openai.PRICES["gpt-5.5"], "OpenAI")
        self.assertEqual(c["usd"], 0.5)
        self.assertEqual(c["saved_usd"], 0)

    def test_long_context_tier_applies_to_the_whole_request(self):
        luna = openai.PRICES["gpt-6-luna"]
        at_limit = cost.compute(U(0, 0, 272_000, 1_000_000), luna, "OpenAI")
        over = cost.compute(U(0, 0, 272_001, 1_000_000), luna, "OpenAI")
        self.assertNotIn("long_over", at_limit)
        self.assertEqual(at_limit["rates"]["input"], 0.1)
        self.assertEqual(over["long_over"], 272_000)
        self.assertEqual(over["rates"], {
            "input": 0.2, "read": 0.02, "write": 0.25, "write_1h": 0.25, "output": 0.75,
        })
        self.assertEqual(over["parts"]["output"], 0.75)

    def test_price_note_travels_with_the_cost(self):
        c = cost.compute(U(0, None, 500, 10), copilot.PRICES["gpt-4.1"], "Copilot")
        self.assertEqual(c["usd"], 0)
        self.assertIn("utilitario", c["note"])


class LostTest(unittest.TestCase):
    def lost(self, usage, previous_total):
        c = cost.compute(usage, OPUS, "Anthropic")
        return cost.lost(usage, U(0, 0, previous_total, 0), c)

    def test_rewritten_prefix_pays_write_instead_of_read(self):
        # the 1M tokens of the previous request were written again at 5 instead of read at 0.2
        self.assertEqual(self.lost(U(0, 1_000_000, 0, 0), 1_000_000), 4.8)

    def test_uncached_prefix_pays_input_instead_of_read(self):
        self.assertEqual(self.lost(U(0, 0, 1_000_000, 0), 1_000_000), 3.8)

    def test_only_the_previous_prefix_counts(self):
        # 500K were new anyway: only the other 500K could have been read
        self.assertEqual(self.lost(U(0, 1_000_000, 0, 0), 500_000), 2.4)

    def test_partial_read_loses_only_the_shortfall(self):
        self.assertEqual(self.lost(U(400_000, 600_000, 0, 0), 1_000_000), 2.88)

    def test_everything_read_loses_nothing(self):
        self.assertEqual(self.lost(U(1_000_000, 0, 50, 0), 1_000_000), 0)


class PriceRecordTest(unittest.TestCase):
    def rec(self, **changes):
        return {"id": 2, "host": "api.anthropic.com", "model": "claude-opus-5-5", **changes}

    def test_without_usage_nothing_is_set(self):
        rec = self.rec(usage=None)
        cost.price_record(rec, None)
        self.assertNotIn("cost", rec)
        self.assertNotIn("cost_missing", rec)

    def test_direct_call_pays_the_list_price(self):
        rec = self.rec(usage=U(0, 0, 1_000_000, 0), verdict="COLD")
        cost.price_record(rec, None)
        self.assertEqual(rec["cost"]["tariff"], "Anthropic")
        self.assertEqual(rec["cost"]["usd"], 4.0)
        self.assertNotIn("lost_usd", rec["cost"])

    def test_copilot_host_pays_the_copilot_price(self):
        rec = self.rec(host="api.githubcopilot.com", model="gpt-6-luna", usage=U(0, None, 100_000, 0))
        cost.price_record(rec, None)
        self.assertEqual(rec["cost"]["tariff"], "Copilot")
        self.assertEqual(rec["cost"]["usd"], 0.01)

    def test_miss_records_what_was_lost(self):
        rec = self.rec(usage=U(0, 1_000_000, 0, 0), verdict="MISS")
        cost.price_record(rec, {"id": 1, "usage": U(0, 0, 1_000_000, 0)})
        self.assertEqual(rec["cost"]["lost_usd"], 4.8)

    def test_hit_never_loses(self):
        rec = self.rec(usage=U(900_000, 100_000, 0, 0), verdict="HIT")
        cost.price_record(rec, {"id": 1, "usage": U(0, 0, 1_000_000, 0)})
        self.assertNotIn("lost_usd", rec["cost"])

    def test_miss_after_a_request_without_usage_has_no_loss(self):
        rec = self.rec(usage=U(0, 1_000_000, 0, 0), verdict="MISS")
        cost.price_record(rec, {"id": 1, "usage": None})
        self.assertNotIn("lost_usd", rec["cost"])

    def test_model_without_price_is_never_guessed(self):
        rec = self.rec(model="claude-opus-4-6", usage=U(0, 0, 600, 5))
        cost.price_record(rec, None)
        self.assertNotIn("cost", rec)
        self.assertEqual(rec["cost_missing"], "sin precio para claude-opus-4-6 en la tarifa de Anthropic")

    def test_unknown_provider_has_no_tariff(self):
        rec = self.rec(host="api.mistral.ai", model="mistral-large", usage=U(0, None, 600, 5))
        cost.price_record(rec, None)
        self.assertEqual(rec["cost_missing"], "sin tarifa conocida para mistral-large")

    def test_one_hour_write_is_priced(self):
        rec = self.rec(usage=U(0, 1_000_000, 0, 0), verdict="COLD")
        cost.price_record(rec, None, 1_000_000)
        self.assertEqual(rec["cost"]["usd"], 8.0)


if __name__ == "__main__":
    unittest.main()
