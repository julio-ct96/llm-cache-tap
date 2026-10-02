import unittest

from cachetap.providers import openai

IN_MEMORY_ONLY = "por defecto: este modelo solo admite in_memory"
ORG_DEPENDENT = "supuesto: la retención por defecto depende de la organización"


class OwnsTest(unittest.TestCase):
    def test_gpt_4o(self):
        self.assertIs(openai.owns("gpt-4o"), True)

    def test_gpt_5_6(self):
        self.assertIs(openai.owns("gpt-5.6"), True)

    def test_o_series(self):
        self.assertIs(openai.owns("o3-mini"), True)

    def test_claude(self):
        self.assertIs(openai.owns("claude-opus-5-5"), False)

    def test_mistral(self):
        self.assertIs(openai.owns("mistral-large"), False)

    def test_empty(self):
        self.assertIs(openai.owns(""), False)


class CacheTtlTest(unittest.TestCase):
    def check(self, model, req, ttl_s, ttl_max_s, source):
        expected = {"ttl_s": ttl_s, "ttl_source": source, "ttl_anchor": "end"}
        if ttl_max_s is not None:
            expected["ttl_max_s"] = ttl_max_s
        self.assertEqual(openai.cache_ttl(req, model), expected)

    def test_gpt_5_6_default(self):
        self.check("gpt-5.6", {}, 1800, None, "por defecto de GPT-5.6 y posteriores")

    def test_gpt_5_6_declared(self):
        req = {"prompt_cache_options": {"ttl": "30m"}}
        self.check("gpt-5.6", req, 1800, None, "declarado en prompt_cache_options")

    def test_gpt_5_2(self):
        self.check("gpt-5.2", {}, 300, 86400, ORG_DEPENDENT)

    def test_gpt_5_dated(self):
        self.check("gpt-5-2025-08-07", {}, 300, 86400, ORG_DEPENDENT)

    def test_gpt_4_1_24h(self):
        self.check("gpt-4.1", {"prompt_cache_retention": "24h"}, 1800, 86400, "declarado: retención 24h")

    def test_gpt_4_1_in_memory(self):
        self.check("gpt-4.1", {"prompt_cache_retention": "in_memory"}, 300, 3600, "declarado: retención in_memory")

    def test_gpt_4o(self):
        self.check("gpt-4o", {}, 300, 3600, IN_MEMORY_ONLY)

    def test_o_series(self):
        self.check("o3-mini", {}, 300, 3600, IN_MEMORY_ONLY)


class MinCacheableTest(unittest.TestCase):
    def test_gpt_5_6(self):
        self.assertEqual(openai.min_cacheable("gpt-5.6"), 1024)


class EffortTest(unittest.TestCase):
    def test_reasoning(self):
        self.assertEqual(openai.effort({"reasoning": {"effort": "low"}}), "low")

    def test_reasoning_effort(self):
        self.assertEqual(openai.effort({"reasoning_effort": "medium"}), "medium")

    def test_not_a_dict(self):
        self.assertIsNone(openai.effort({"reasoning": "x"}))


class NormalizeTest(unittest.TestCase):
    def test_responses_shape(self):
        merged = {
            "input_tokens": 4200,
            "input_tokens_details": {"cached_tokens": 3900},
            "output_tokens": 80,
            "output_tokens_details": {"reasoning_tokens": 30},
        }
        self.assertEqual(
            openai.normalize(merged),
            {"read": 3900, "write": None, "uncached": 300, "input_total": 4200, "output": 80, "reasoning": 30},
        )

    def test_chat_completions_shape(self):
        merged = {"prompt_tokens": 1600, "prompt_tokens_details": {"cached_tokens": 1400}, "completion_tokens": 40}
        self.assertEqual(
            openai.normalize(merged),
            {"read": 1400, "write": None, "uncached": 200, "input_total": 1600, "output": 40, "reasoning": None},
        )

    def test_invalid_details_and_cached_tokens_are_ignored(self):
        self.assertEqual(
            openai.normalize(
                {
                    "input_tokens": 12,
                    "input_tokens_details": {"cached_tokens": True},
                    "output_tokens_details": [],
                }
            ),
            {"read": 0, "write": None, "uncached": 12, "input_total": 12, "output": 0, "reasoning": None},
        )

    def test_cached_tokens_are_capped_at_input_total(self):
        self.assertEqual(
            openai.normalize({"input_tokens": 8, "input_tokens_details": {"cached_tokens": 20}}),
            {"read": 8, "write": None, "uncached": 0, "input_total": 8, "output": 0, "reasoning": None},
        )


class DeltasTest(unittest.TestCase):
    def test_responses_text(self):
        self.assertEqual(openai.deltas({"type": "response.output_text.delta", "delta": "a"}), (["a"], None))

    def test_other_event_type(self):
        self.assertEqual(openai.deltas({"type": "otro", "delta": "a"}), ([], None))

    def test_chat_text_and_finish(self):
        ev = {"choices": [{"delta": {"content": "a"}}, {"delta": {}, "finish_reason": "stop"}]}
        self.assertEqual(openai.deltas(ev), (["a"], "stop"))

    def test_malformed_choices_and_reasons_are_ignored(self):
        self.assertEqual(openai.deltas({"choices": {}, "delta": "x"}), ([], None))
        self.assertEqual(
            openai.deltas({"choices": [None, {"delta": [], "finish_reason": 4}, {"delta": {"content": "a"}}]}),
            (["a"], None),
        )

    def test_anthropic_shaped_delta(self):
        self.assertEqual(openai.deltas({"delta": {"text": "a"}}), ([], None))
