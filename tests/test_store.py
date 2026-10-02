import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from cachetap import config, store
from tests.replay import adapter


class StoreTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        adapter.reset(Path(tmp.name) / "requests.jsonl")

    def test_ids(self):
        self.assertEqual(store.next_id(), 1)
        self.assertEqual(store.next_id(), 2)

    def test_conversations(self):
        self.assertEqual(store.new_conv(), "c1")
        self.assertEqual(store.new_conv(), "c2")

    def test_active_capture_slots_are_bounded_and_reusable(self):
        with mock.patch.object(config, "MAX_ACTIVE_CAPTURES", 1):
            with store.LOCK:
                self.assertTrue(store.begin_capture(1))
                self.assertFalse(store.begin_capture(2))
                store.end_capture(1)
                self.assertTrue(store.begin_capture(2))
                store.end_capture(2)
        self.assertEqual(store.ACTIVE_CAPTURES, set())

    def test_end_capture_is_idempotent(self):
        with store.LOCK:
            store.end_capture(999)
        self.assertNotIn(999, store.ACTIVE_CAPTURES)

    def test_add(self):
        rec = {"id": 1}
        store.add(rec, "a")
        self.assertIs(store.RECORDS[1], rec)
        self.assertEqual(store.BODIES[1], "a")

    def test_eviction(self):
        with mock.patch.object(config, "MAX", 2):
            for rid in (1, 2, 3):
                store.add({"id": rid}, "b")
        self.assertEqual(list(store.RECORDS), [2, 3])
        self.assertEqual(list(store.BODIES), [2, 3])

    def test_byte_budget_counts_utf8_and_evicts_fifo(self):
        with mock.patch.object(config, "MAX_BODY_BYTES", 4):
            self.assertEqual(store.add({"id": 1}, "ñ"), [])
            self.assertEqual(store.add({"id": 2}, "ab"), [])
            self.assertEqual(store.add({"id": 3}, "c"), [1])
        self.assertEqual(list(store.RECORDS), [2, 3])
        self.assertEqual(list(store.BODIES), [2, 3])
        self.assertEqual(store.STATE["body_bytes"], 3)

    def test_replacing_id_adjusts_body_byte_count(self):
        store.add({"id": 1}, "ñ")
        store.add({"id": 2}, "ab")
        self.assertEqual(store.add({"id": 1}, "a"), [])
        self.assertEqual(store.STATE["body_bytes"], 3)
        self.assertEqual(list(store.RECORDS), [1, 2])
        self.assertEqual(store.BODIES[1], "a")

    def test_body_larger_than_budget_is_not_retained_and_publishes_eviction(self):
        q = adapter.subscribe()
        with mock.patch.object(config, "MAX_BODY_BYTES", 2):
            evicted = store.add({"id": 1}, "abc")
            store.push({"id": 1}, evicted)
        self.assertEqual(evicted, [1])
        self.assertEqual(store.RECORDS, {})
        self.assertEqual(store.BODIES, {})
        self.assertEqual(store.STATE["body_bytes"], 0)
        self.assertEqual(q.get_nowait(), {"type": "evict", "ids": [1]})

    def test_publish(self):
        q = adapter.subscribe()
        store.publish({"type": "x"})
        self.assertEqual(q.get_nowait(), {"type": "x"})

    def test_push(self):
        q = adapter.subscribe()
        store.push({"id": 1, "segs": [], "_msgs": []})
        self.assertEqual(q.get_nowait(), {"type": "record", "rec": {"id": 1}})

    def test_push_does_not_modify_record(self):
        rec = {"id": 1, "segs": [{"text": "light"}], "_msgs": [{"content": "public"}]}
        original = deepcopy(rec)
        store.push(rec)
        self.assertEqual(rec, original)

    def test_append_log(self):
        log_path = Path(config.LOG).parent / "nested" / "requests.jsonl"
        with mock.patch.object(config, "LOG", log_path):
            store.append_log({"id": 1, "segs": [], "model": "ñ"})
        text = log_path.read_text(encoding="utf-8")
        self.assertEqual(json.loads(text), {"id": 1, "model": "ñ"})
        self.assertIn("ñ", text)

    def test_append_log_preserves_existing_lines(self):
        log_path = Path(config.LOG).parent / "requests.jsonl"
        with mock.patch.object(config, "LOG", log_path):
            store.append_log({"id": 1, "segs": []})
            store.append_log({"id": 2, "segs": []})
        lines = log_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["id"] for line in lines], [1, 2])

    def test_clear(self):
        store.add({"id": 1}, "a")
        q = adapter.subscribe()
        store.clear()
        self.assertEqual(len(store.RECORDS), 0)
        self.assertEqual(len(store.BODIES), 0)
        self.assertEqual(store.STATE["body_bytes"], 0)
        self.assertEqual(q.get_nowait(), {"type": "clear"})


if __name__ == "__main__":
    unittest.main()
