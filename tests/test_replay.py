import json
import os
import unittest
from pathlib import Path

from tests.replay import scenario

GOLDEN_PATH = Path(__file__).parent / "replay" / "golden.json"


def _first_difference(expected, actual):
    """Describe only the first difference between two scenario results, or None."""
    for section in ("events", "records", "body_ids", "log_lines"):
        exp_list = expected.get(section)
        act_list = actual.get(section)
        if len(exp_list) != len(act_list):
            return f"{section}: expected {len(exp_list)} items, got {len(act_list)}"
        for pos, (exp, act) in enumerate(zip(exp_list, act_list)):
            if exp == act:
                continue
            rec_id = exp.get("id") if isinstance(exp, dict) else None
            if isinstance(exp, dict) and isinstance(act, dict):
                for key in sorted(set(exp) | set(act)):
                    if exp.get(key) != act.get(key):
                        return (
                            f"{section}[{pos}] id={rec_id} key={key!r}: "
                            f"expected {exp.get(key)!r}, got {act.get(key)!r}"
                        )
            return f"{section}[{pos}] id={rec_id}: expected {exp!r}, got {act!r}"
    return None


def _by_id(records, rec_id):
    return next(r for r in records if r["id"] == rec_id)


class ReplayTest(unittest.TestCase):
    def test_expected_verdicts(self):
        steps = [s for s in scenario.all_steps() if s.expect is not None]
        result = scenario.run(scenario.all_steps())
        records = result["records"]
        self.assertEqual(len(records), len(steps))
        for step, rec in zip(steps, records):
            self.assertEqual(rec["verdict"], step.expect, f"step {step.key}")

    def test_golden(self):
        result = json.loads(json.dumps(scenario.run(scenario.all_steps())))
        if os.environ.get("TAP_UPDATE_GOLDEN") == "1":
            GOLDEN_PATH.write_text(
                json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True),
                encoding="utf-8",
            )
            return
        expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        diff = _first_difference(expected, result)
        if diff is not None:
            self.fail(f"golden differs, first difference: {diff}")

    def test_known_values(self):
        result = scenario.run(scenario.all_steps())
        records = result["records"]
        self.assertEqual(len(records), 44)
        self.assertEqual(len(result["events"]), 131)
        self.assertEqual(len(result["log_lines"]), 43)
        self.assertEqual(result["body_ids"], list(range(1, 45)))
        self.assertEqual(
            _by_id(records, 5)["notes"],
            ["pasaron 400 s desde el inicio de #4 (TTL 300 s, por defecto de Claude)"],
        )
        self.assertEqual(_by_id(records, 6)["diverge_at"], "system")
        self.assertEqual(_by_id(records, 6)["diff"]["segment"], "system")
        self.assertEqual(_by_id(records, 6)["diff"]["offset"], 40)
        self.assertEqual(_by_id(records, 7)["diverge_at"], "tools (eliminado)")
        self.assertEqual(
            _by_id(records, 8)["notes"],
            [
                "cambió el modelo (claude-opus-5-5 → claude-sonnet-5-5)",
                "cambió el esfuerzo (high → low)",
                "cambiaron thinking/tool_choice",
            ],
        )
        self.assertEqual(_by_id(records, 13)["ttl_source"], "confirmado por usage: escritura a 60 min")
        self.assertEqual(_by_id(records, 15)["ttl_source"], "confirmado por usage: escritura a 5 min")
        self.assertEqual(
            _by_id(records, 29)["notes"],
            ["pasaron 2078 s desde el final de #28 (TTL 1800 s, declarado en prompt_cache_options)"],
        )
        self.assertEqual(_by_id(records, 32)["diverge_at"], "msg0:system")
        self.assertEqual(
            _by_id(records, 40)["notes"],
            ["pasaron 398 s desde el final de #39 (TTL 300 s, supuesto: proveedor sin TTL conocido)"],
        )
        self.assertIsNone(_by_id(records, 41)["model"])
        self.assertEqual(_by_id(records, 44)["output"], "{no es json")
        self.assertEqual([r["id"] for r in records if r.get("server_side")], [4, 33])
