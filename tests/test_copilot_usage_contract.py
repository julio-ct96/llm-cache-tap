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

    def test_missing_reasoning_tokens_is_rejected(self):
        usage = cli_usage(mirrors=False)
        del usage["modelMetrics"][MODEL]["usage"]["reasoningTokens"]

        with self.assertRaisesRegex(runner.RunnerError, "reasoningTokens"):
            runner.decode_cli_usage(usage)

    def test_missing_cache_write_token_detail_is_rejected(self):
        usage = cli_usage(mirrors=False)
        del usage["modelMetrics"][MODEL]["tokenDetails"]["cache_write"]

        with self.assertRaisesRegex(runner.RunnerError, "cache_write"):
            runner.decode_cli_usage(usage)

    def test_missing_token_details_object_is_rejected(self):
        usage = cli_usage(mirrors=False)
        del usage["modelMetrics"][MODEL]["tokenDetails"]

        with self.assertRaisesRegex(runner.RunnerError, "tokenDetails"):
            runner.decode_cli_usage(usage)

    def test_mirror_sections_do_not_add_model_requests_to_the_count(self):
        decoded = runner.decode_cli_usage(cli_usage(mirrors=True))

        self.assertEqual(set(decoded["modelMetrics"]), {MODEL})
        self.assertEqual(runner.compare_usage(completed_record(), decoded)["requests"], 1)


if __name__ == "__main__":
    unittest.main()
