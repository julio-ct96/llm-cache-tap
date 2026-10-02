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
