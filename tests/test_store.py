import json
import threading
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
        with store.LOCK:
            self.assertEqual(store.next_id(), 1)
            self.assertEqual(store.next_id(), 2)

    def test_conversations(self):
        with store.LOCK:
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
        with store.LOCK:
            store.add(rec, "a")
        self.assertIs(store.RECORDS[1], rec)
        self.assertEqual(store.BODIES[1], "a")

    def test_eviction(self):
        with mock.patch.object(config, "MAX", 2):
            with store.LOCK:
                for rid in (1, 2, 3):
                    store.add({"id": rid}, "b")
        self.assertEqual(list(store.RECORDS), [2, 3])
        self.assertEqual(list(store.BODIES), [2, 3])

    def test_byte_budget_counts_utf8_and_evicts_fifo(self):
        with mock.patch.object(config, "MAX_BODY_BYTES", 4):
            with store.LOCK:
                self.assertEqual(store.add({"id": 1}, "ñ"), [])
                self.assertEqual(store.add({"id": 2}, "ab"), [])
                self.assertEqual(store.add({"id": 3}, "c"), [1])
        self.assertEqual(list(store.RECORDS), [2, 3])
        self.assertEqual(list(store.BODIES), [2, 3])
        self.assertEqual(store.STATE["body_bytes"], 3)

    def test_replacing_id_adjusts_body_byte_count(self):
        with store.LOCK:
            store.add({"id": 1}, "ñ")
            store.add({"id": 2}, "ab")
            self.assertEqual(store.add({"id": 1}, "a"), [])
        self.assertEqual(store.STATE["body_bytes"], 3)
        self.assertEqual(list(store.RECORDS), [1, 2])
        self.assertEqual(store.BODIES[1], "a")

    def test_body_larger_than_budget_is_not_retained_and_publishes_eviction(self):
        with mock.patch.object(config, "MAX_BODY_BYTES", 2):
            with store.LOCK:
                q = store.subscribe()
                evicted = store.add({"id": 1}, "abc")
                store.push({"id": 1}, evicted)
        self.assertEqual(evicted, [1])
        self.assertEqual(store.RECORDS, {})
        self.assertEqual(store.BODIES, {})
        self.assertEqual(store.STATE["body_bytes"], 0)
        self.assertEqual(q.get_nowait(), {"type": "evict", "ids": [1]})

    def test_publish(self):
        q = adapter.subscribe()
        with store.LOCK:
            store.publish({"type": "x"})
        self.assertEqual(q.get_nowait(), {"type": "x"})

    def test_push(self):
        q = adapter.subscribe()
        with store.LOCK:
            store.push({"id": 1, "segs": [], "_msgs": []})
        self.assertEqual(q.get_nowait(), {"type": "record", "rec": {"id": 1}})

    def test_push_does_not_modify_record(self):
        rec = {"id": 1, "segs": [{"text": "light"}], "_msgs": [{"content": "public"}]}
        original = deepcopy(rec)
        with store.LOCK:
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
        q = adapter.subscribe()
        with store.LOCK:
            store.add({"id": 1}, "a")
            store.clear()
        self.assertEqual(len(store.RECORDS), 0)
        self.assertEqual(len(store.BODIES), 0)
        self.assertEqual(store.STATE["body_bytes"], 0)
        self.assertEqual(q.get_nowait(), {"type": "clear"})

    def test_slow_client_is_disconnected_without_blocking_fast_client(self):
        with mock.patch.object(config, "MAX_CLIENT_EVENTS", 2):
            with store.LOCK:
                slow = store.subscribe()
                fast = store.subscribe()
                for event_id in range(3):
                    store.publish({"type": "event", "id": event_id})
                    self.assertEqual(fast.get_nowait(), {"type": "event", "id": event_id})
            self.assertEqual(slow.get_nowait(), {"type": "disconnect"})
            with store.LOCK:
                self.assertNotIn(slow, store.CLIENTS)
                self.assertIn(fast, store.CLIENTS)
                store.unsubscribe(fast)

    def test_unsubscribe_is_idempotent(self):
        with store.LOCK:
            q = store.subscribe()
            store.unsubscribe(q)
            store.unsubscribe(q)
            self.assertNotIn(q, store.CLIENTS)

    def test_concurrent_publish_and_subscriber_lifecycle(self):
        barrier = threading.Barrier(3)
        errors = []

        def produce():
            try:
                barrier.wait(timeout=2)
                for event_id in range(200):
                    with store.LOCK:
                        store.publish({"type": "event", "id": event_id})
            except BaseException as exc:
                errors.append(exc)

        def manage_subscribers():
            try:
                barrier.wait(timeout=2)
                for _ in range(100):
                    with store.LOCK:
                        q = store.subscribe()
                        store.unsubscribe(q)
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=produce), threading.Thread(target=manage_subscribers)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=3)
        self.assertFalse([thread for thread in threads if thread.is_alive()])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
