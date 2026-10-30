"""Synthetic contract checks for the current offline Copilot usage reader."""

import unittest

import scripts.check_copilot as runner

MODEL = "gpt-6-luna"
NANO_AIU = 57_968_100
RECORD_USAGE = {"read": 9004, "write": 4286, "output": 36, "input_total": 13293}


def model_row(*, request_count=1):
    return {
        "requests": {"count": request_count, "cost": 1},
        "usage": {
            "inputTokens": 13293,
            "outputTokens": 36,
            "cacheReadTokens": 9004,
            "cacheWriteTokens": 4286,
            "reasoningTokens": 21,
        },
        "tokenDetails": {
            "input": {"tokenCount": 3},
            "cache_read": {"tokenCount": 9004},
            "cache_write": {"tokenCount": 4286},
            "output": {"tokenCount": 36},
        },
    }


def cli_usage(*, mirrors=True, total_nano_aiu=NANO_AIU):
    row = model_row()
    result = {"modelMetrics": {MODEL: row}}
    if mirrors:
        # Repeated views of the model metrics are not additional requests.
        result["agentMetrics"] = {"agent": {MODEL: row}}
        result["providerModelMetrics"] = {"provider": {MODEL: row}}
    if total_nano_aiu is not None:
        result["totalNanoAiu"] = total_nano_aiu
    return result


def completed_record():
    return {
        "model": MODEL,
        "usage": RECORD_USAGE,
        "verdict": "PARTIAL",
    }


class CopilotUsageContractTests(unittest.TestCase):
    def test_valid_synthetic_usage_is_accepted_and_counters_are_preserved(self):
        decoded = runner.decode_cli_usage(cli_usage(mirrors=False))

        self.assertEqual(decoded["modelMetrics"][MODEL]["usage"], model_row()["usage"])
        self.assertEqual(
            decoded["modelMetrics"][MODEL]["tokenDetails"], model_row()["tokenDetails"]
        )
        summary = runner.compare_usage(completed_record(), decoded)
        self.assertEqual(
            {key: summary[key] for key in RECORD_USAGE},
            RECORD_USAGE,
        )

    def test_missing_reasoning_tokens_is_accepted_without_a_synthetic_zero(self):
        usage = cli_usage(mirrors=False)
        del usage["modelMetrics"][MODEL]["usage"]["reasoningTokens"]

        decoded = runner.decode_cli_usage(usage)
        decoded_usage = decoded["modelMetrics"][MODEL]["usage"]
        self.assertNotIn("reasoningTokens", decoded_usage)
        self.assertEqual(
            decoded_usage,
            {key: value for key, value in model_row()["usage"].items() if key != "reasoningTokens"},
        )
        self.assertEqual(
            runner.compare_usage(completed_record(), decoded)["write"],
            RECORD_USAGE["write"],
        )

    def test_present_invalid_reasoning_tokens_remain_rejected(self):
        for value, actual in (
            (None, "null"),
            (True, "boolean"),
            (-1, "negative_number"),
            ("not-a-count", "string"),
        ):
            with self.subTest(actual=actual):
                usage = cli_usage(mirrors=False)
                usage["modelMetrics"][MODEL]["usage"]["reasoningTokens"] = value

                with self.assertRaises(runner.SchemaError) as raised:
                    runner.decode_cli_usage(usage)
                self.assertEqual(
                    runner.format_schema_diagnostic(raised.exception),
                    {
                        "path": "modelMetrics[*].usage.reasoningTokens",
                        "expected": "non_negative_integer",
                        "actual": actual,
                    },
                )

    def test_missing_cache_write_token_detail_is_rejected(self):
        usage = cli_usage(mirrors=False)
        del usage["modelMetrics"][MODEL]["tokenDetails"]["cache_write"]

        with self.assertRaises(runner.SchemaError) as raised:
            runner.decode_cli_usage(usage)
        self.assertEqual(
            runner.format_schema_diagnostic(raised.exception),
            {
                "path": "modelMetrics[*].tokenDetails.cache_write",
                "expected": "object",
                "actual": "missing",
            },
        )

    def test_missing_cache_write_detail_is_accepted_only_with_explicit_zero(self):
        usage = cli_usage(mirrors=False)
        usage["modelMetrics"][MODEL]["usage"]["cacheWriteTokens"] = 0
        del usage["modelMetrics"][MODEL]["tokenDetails"]["cache_write"]

        decoded = runner.decode_cli_usage(usage)
        metrics = decoded["modelMetrics"][MODEL]
        self.assertNotIn("cache_write", metrics["tokenDetails"])
        self.assertEqual(metrics["usage"]["cacheWriteTokens"], 0)

        zero_record = completed_record()
        zero_record["usage"] = {**RECORD_USAGE, "write": 0}
        self.assertEqual(runner.compare_usage(zero_record, decoded)["write"], 0)

        nonzero_record = completed_record()
        with self.assertRaisesRegex(runner.RunnerError, "CLI usage counters differ"):
            runner.compare_usage(nonzero_record, decoded)

        missing_write_record = completed_record()
        missing_write_record["usage"] = dict(RECORD_USAGE)
        del missing_write_record["usage"]["write"]
        with self.assertRaisesRegex(runner.RunnerError, "CLI usage counters differ"):
            runner.compare_usage(missing_write_record, decoded)

        boolean_write_record = completed_record()
        boolean_write_record["usage"] = {**RECORD_USAGE, "write": False}
        with self.assertRaisesRegex(runner.RunnerError, "CLI usage counters differ"):
            runner.compare_usage(boolean_write_record, decoded)

    def test_missing_cache_write_detail_requires_valid_explicit_usage_zero(self):
        cases = (
            ("positive", 1, "modelMetrics[*].tokenDetails.cache_write", "object", "missing"),
            (
                "missing",
                None,
                "modelMetrics[*].usage.cacheWriteTokens",
                "non_negative_integer",
                "missing",
            ),
            (
                "null",
                None,
                "modelMetrics[*].usage.cacheWriteTokens",
                "non_negative_integer",
                "null",
            ),
            (
                "boolean",
                True,
                "modelMetrics[*].usage.cacheWriteTokens",
                "non_negative_integer",
                "boolean",
            ),
        )
        for case, value, path, expected, actual in cases:
            with self.subTest(case=case):
                usage = cli_usage(mirrors=False)
                row = usage["modelMetrics"][MODEL]
                del row["tokenDetails"]["cache_write"]
                if case == "missing":
                    del row["usage"]["cacheWriteTokens"]
                else:
                    row["usage"]["cacheWriteTokens"] = value

                with self.assertRaises(runner.SchemaError) as raised:
                    runner.decode_cli_usage(usage)
                self.assertEqual(
                    runner.format_schema_diagnostic(raised.exception),
                    {"path": path, "expected": expected, "actual": actual},
                )

    def test_present_invalid_cache_write_detail_is_rejected_even_with_zero_usage(self):
        cases = (
            (None, "modelMetrics[*].tokenDetails.cache_write", "object", "null"),
            (
                {"tokenCount": True},
                "modelMetrics[*].tokenDetails.cache_write.tokenCount",
                "non_negative_integer",
                "boolean",
            ),
            (
                {"tokenCount": -1},
                "modelMetrics[*].tokenDetails.cache_write.tokenCount",
                "non_negative_integer",
                "negative_number",
            ),
        )
        for value, path, expected, actual in cases:
            with self.subTest(actual=actual):
                usage = cli_usage(mirrors=False)
                row = usage["modelMetrics"][MODEL]
                row["usage"]["cacheWriteTokens"] = 0
                row["tokenDetails"]["cache_write"] = value

                with self.assertRaises(runner.SchemaError) as raised:
                    runner.decode_cli_usage(usage)
                self.assertEqual(
                    runner.format_schema_diagnostic(raised.exception),
                    {"path": path, "expected": expected, "actual": actual},
                )

    def test_other_token_detail_fields_remain_required(self):
        for field in ("input", "cache_read", "output"):
            with self.subTest(field=field):
                usage = cli_usage(mirrors=False)
                del usage["modelMetrics"][MODEL]["tokenDetails"][field]

                with self.assertRaises(runner.SchemaError) as raised:
                    runner.decode_cli_usage(usage)
                self.assertEqual(
                    runner.format_schema_diagnostic(raised.exception),
                    {
                        "path": f"modelMetrics[*].tokenDetails.{field}",
                        "expected": "object",
                        "actual": "missing",
                    },
                )

    def test_present_write_counter_or_detail_must_still_match_record(self):
        for field in ("cacheWriteTokens", "tokenCount"):
            with self.subTest(field=field):
                usage = cli_usage(mirrors=False)
                row = usage["modelMetrics"][MODEL]
                if field == "cacheWriteTokens":
                    row["usage"][field] = RECORD_USAGE["write"] + 1
                else:
                    row["tokenDetails"]["cache_write"][field] = RECORD_USAGE["write"] + 1

                decoded = runner.decode_cli_usage(usage)
                with self.assertRaisesRegex(runner.RunnerError, "CLI usage counters differ"):
                    runner.compare_usage(completed_record(), decoded)

    def test_usage_schema_distinguishes_null_from_missing_and_boolean(self):
        null_usage = cli_usage(mirrors=False)
        null_usage["modelMetrics"][MODEL]["usage"]["reasoningTokens"] = None
        with self.assertRaises(runner.SchemaError) as null_raised:
            runner.decode_cli_usage(null_usage)
        self.assertEqual(runner.format_schema_diagnostic(null_raised.exception)["actual"], "null")

        boolean_usage = cli_usage(mirrors=False)
        boolean_usage["modelMetrics"][MODEL]["tokenDetails"]["input"]["tokenCount"] = True
        with self.assertRaises(runner.SchemaError) as boolean_raised:
            runner.decode_cli_usage(boolean_usage)
        self.assertEqual(
            runner.format_schema_diagnostic(boolean_raised.exception)["actual"], "boolean"
        )

    def test_missing_token_details_object_is_rejected(self):
        usage = cli_usage(mirrors=False)
        del usage["modelMetrics"][MODEL]["tokenDetails"]

        with self.assertRaises(runner.SchemaError) as raised:
            runner.decode_cli_usage(usage)
        self.assertEqual(
            runner.format_schema_diagnostic(raised.exception),
            {"path": "modelMetrics[*].tokenDetails", "expected": "object", "actual": "missing"},
        )

    def test_mirror_sections_do_not_add_model_requests_to_the_count(self):
        decoded = runner.decode_cli_usage(cli_usage(mirrors=True))

        self.assertEqual(set(decoded["modelMetrics"]), {MODEL})
        self.assertEqual(runner.compare_usage(completed_record(), decoded)["requests"], 1)


if __name__ == "__main__":
    unittest.main()
