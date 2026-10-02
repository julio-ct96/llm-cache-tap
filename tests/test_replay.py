import unittest

from tests.replay import scenario


class ReplayTest(unittest.TestCase):
    def test_expected_verdicts(self):
        steps = [s for s in scenario.all_steps() if s.expect is not None]
        result = scenario.run(scenario.all_steps())
        records = result["records"]
        self.assertEqual(len(records), len(steps))
        for step, rec in zip(steps, records):
            self.assertEqual(rec["verdict"], step.expect, f"step {step.key}")
