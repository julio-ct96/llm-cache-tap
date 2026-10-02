"""Tests for the unified check runner's orchestration."""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

import scripts.check as check


class CheckRunnerTest(unittest.TestCase):
    def setUp(self):
        self.runner = Mock()

    def test_runs_checks_in_order_with_expected_arguments(self):
        check.run_checks(runner=self.runner)

        calls = self.runner.call_args_list
        self.assertEqual(
            [call.args[0] for call in calls],
            [
                [check.sys.executable, "-m", "ruff", "check", "tap.py", "cachetap"],
                [check.sys.executable, "-m", "ruff", "format", "--check", "tap.py", "cachetap"],
                [check.sys.executable, "-m", "mypy"],
                [
                    check.sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-t",
                    ".",
                    "-q",
                ],
                [
                    "node",
                    "--test",
                    *(
                        str(path.relative_to(check.ROOT))
                        for path in sorted((check.ROOT / "tests/ui/unit").glob("*.test.mjs"))
                    ),
                ],
            ],
        )
        for call in calls:
            self.assertEqual(call.kwargs["cwd"], check.ROOT)
            self.assertIs(call.kwargs["check"], True)

    def test_propagates_subprocess_failure(self):
        failure = subprocess.CalledProcessError(7, ["ruff"])
        self.runner.side_effect = failure

        with self.assertRaises(subprocess.CalledProcessError) as raised:
            check.run_checks(runner=self.runner)

        self.assertIs(raised.exception, failure)
        self.runner.assert_called_once()

    def test_full_adds_ui_check_after_all_other_checks(self):
        check.VENV_PYTHON = Path(__file__).resolve().parents[1] / "venv/bin/python"
        check.run_checks(full=True, runner=self.runner)

        ui_call = self.runner.call_args_list[-1]
        self.assertEqual(ui_call.args[0], ["node", "tests/ui/check.mjs", "--full"])
        self.assertEqual(ui_call.kwargs["cwd"], check.ROOT)
        self.assertIs(ui_call.kwargs["check"], True)
        self.assertIn("localhost", ui_call.kwargs["env"]["NO_PROXY"].split(","))
        self.assertIn("127.0.0.1", ui_call.kwargs["env"]["NO_PROXY"].split(","))
        self.assertIn("::1", ui_call.kwargs["env"]["NO_PROXY"].split(","))


if __name__ == "__main__":
    unittest.main()
