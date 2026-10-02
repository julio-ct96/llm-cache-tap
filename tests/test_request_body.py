import json
import unittest
from unittest.mock import patch

from cachetap import request_body


class RequestBodyTest(unittest.TestCase):
    def test_malformed_json_retains_empty_object_behavior(self):
        self.assertEqual(request_body.parse("not json"), {})

    def test_non_object_roots_are_rejected(self):
        for text in ("[]", "null", "42", '"text"'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                request_body.parse(text)

    def test_request_field_shapes_are_validated(self):
        invalid = (
            {"model": 3},
            {"tools": 7},
            {"tools": ["tool"]},
            {"messages": 7},
            {"input": {}},
            {"output_config": {"effort": []}},
            {"reasoning": {"effort": {}}},
            {"reasoning_effort": []},
            {"cache_control": {"ttl": {}}},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                request_body.parse(json.dumps(value))

    def test_optional_fields_accept_null_and_supported_shapes(self):
        req = {
            "model": None,
            "tools": [{"name": "tool"}],
            "messages": [42],
            "input": "hola",
            "output_config": {"effort": "high"},
            "reasoning": {"effort": None},
            "reasoning_effort": None,
        }
        self.assertEqual(request_body.parse(json.dumps(req)), req)

        self.assertEqual(
            request_body.parse(json.dumps({"model": None, "tools": None, "messages": None, "input": None})),
            {"model": None, "tools": None, "messages": None, "input": None},
        )

    def test_container_depth_boundary(self):
        accepted = "{}"
        for _ in range(request_body.MAX_CONTAINER_DEPTH - 1):
            accepted = '{"x":' + accepted + "}"
        self.assertIsInstance(request_body.parse(accepted), dict)

        rejected = "{}"
        for _ in range(request_body.MAX_CONTAINER_DEPTH):
            rejected = '{"x":' + rejected + "}"
        with self.assertRaisesRegex(ValueError, "profundidad JSON superior a 100 contenedores"):
            request_body.parse(rejected)

    def test_decoder_recursion_error_is_rejected(self):
        with patch("cachetap.request_body.json.loads", side_effect=RecursionError):
            with self.assertRaisesRegex(ValueError, "JSON demasiado profundo para inspeccionar"):
                request_body.parse("{}")

    def test_cache_control_ttl_accepts_absent_null_or_string(self):
        for ttl in (None, "5m"):
            with self.subTest(ttl=ttl):
                req = {"cache_control": {"ttl": ttl}}
                self.assertEqual(request_body.parse(json.dumps(req)), req)
        req = {"cache_control": {}}
        self.assertEqual(request_body.parse(json.dumps(req)), req)


if __name__ == "__main__":
    unittest.main()
