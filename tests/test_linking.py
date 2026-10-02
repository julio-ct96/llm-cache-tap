import json
import unittest
from copy import deepcopy

from cachetap import linking, segments

U1 = {"role": "user", "content": "first question"}
A1 = {"role": "assistant", "content": "first answer"}
U2 = {"role": "user", "content": "second question"}
P1 = {"tools": [{"name": "t"}], "system": "s", "messages": [U1]}
P2 = {"tools": [{"name": "t"}], "system": "s", "messages": [U1, A1, U2]}


def make(req, **fields):
    rec = {"segs": segments.segments(req), "ts": 0, "effort": None, "model": "m", "_params": ""}
    rec.update(fields)
    return rec


def previous(req, **fields):
    rec = make(req, **fields)
    linking.prepare_fingerprints(rec)
    return rec


class CommonTest(unittest.TestCase):
    def test_common_prefix_length(self):
        self.assertEqual(linking.common_prefix_length([1, 2, 3], [1, 2, 4]), 2)
        self.assertEqual(linking.common_prefix_length([], [1]), 0)


class FindPreviousTest(unittest.TestCase):
    def test_no_previous(self):
        rec = make(P1)
        linking.prepare_fingerprints(rec)
        self.assertEqual(linking.find_previous(rec, []), (None, 0))
        self.assertEqual(sorted(rec["_static"]), ["system", "tools"])
        self.assertEqual(len(rec["_msgs"]), 1)

    def test_find_previous_does_not_mutate_prepared_inputs(self):
        rec = previous(P2)
        records = [previous(P1, id=1, conv="c1")]
        before = deepcopy((rec, records))
        linking.find_previous(rec, records)
        self.assertEqual((rec, records), before)

    def test_other_conversation(self):
        other = {"tools": [{"name": "t"}], "system": "s", "messages": [{"role": "user", "content": "unrelated"}]}
        prev = previous(other, id=1, conv="c1")
        rec = make(P1)
        linking.prepare_fingerprints(rec)
        self.assertEqual(linking.find_previous(rec, [prev]), (None, 0))

    def test_tie_picks_latest(self):
        a1 = previous(P1, id=1, conv="c1")
        a2 = previous(P1, id=2, conv="c2")
        rec = make(P2)
        linking.prepare_fingerprints(rec)
        selected_previous, matched_message_count = linking.find_previous(rec, [a1, a2])
        self.assertEqual(selected_previous["id"], 2)
        self.assertEqual(matched_message_count, 1)


class LinkTest(unittest.TestCase):
    def run_link(self, prev, req, prev_body=None, **fields):
        rec = make(req, **fields)
        linking.prepare_fingerprints(rec)
        previous, matched_message_count = linking.find_previous(rec, [prev])
        linking.link(rec, req, previous, matched_message_count, prev_body)
        return rec

    def test_intact_prefix(self):
        prev = previous(P1, id=1, conv="c1")
        rec = self.run_link(prev, P2, json.dumps(P1))
        self.assertEqual(rec["conv"], "c1")
        self.assertEqual(rec["prev_id"], 1)
        self.assertTrue(rec["prefix_intact"])
        self.assertIsNone(rec["diverge_at"])
        self.assertNotIn("diff", rec)
        self.assertEqual([s["same"] for s in rec["segs"]], [True, True, True, False, False])

    def test_changed_system(self):
        prev = previous(P1, id=1, conv="c1")
        rec = self.run_link(prev, dict(P2, system="otro"), json.dumps(P1))
        self.assertFalse(rec["prefix_intact"])
        self.assertEqual(rec["diverge_at"], "system")
        self.assertEqual(rec["diff"]["segment"], "system")

    def test_removed_tools(self):
        prev = previous(P1, id=1, conv="c1")
        req = {k: v for k, v in P2.items() if k != "tools"}
        rec = self.run_link(prev, req, json.dumps(P1))
        self.assertEqual(rec["diverge_at"], "tools (eliminado)")
        self.assertIn("diff", rec)
        self.assertIsNone(rec["diff"])

    def test_age_from_start(self):
        prev = previous(P1, id=1, conv="c1", ts=100, ts_end=110, ttl_anchor="start")
        rec = self.run_link(prev, P2, ts=160)
        self.assertEqual(rec["gap_s"], 50.0)
        self.assertEqual(rec["age_s"], 60.0)

    def test_age_from_end(self):
        prev = previous(P1, id=1, conv="c1", ts=100, ts_end=110, ttl_anchor="end")
        rec = self.run_link(prev, P2, ts=160)
        self.assertEqual(rec["gap_s"], 50.0)
        self.assertEqual(rec["age_s"], 50.0)

    def test_changes(self):
        prev = previous(P1, id=1, conv="c1", effort=None, model="m")
        rec = self.run_link(prev, P2, effort="high", model="n", _params="x")
        self.assertTrue(rec["effort_changed"])
        self.assertTrue(rec["model_changed"])
        self.assertTrue(rec["params_changed"])
        self.assertIsNone(rec["prev_effort"])
        self.assertEqual(rec["prev_model"], "m")


if __name__ == "__main__":
    unittest.main()
