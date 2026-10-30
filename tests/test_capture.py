import json
import logging
import tempfile
import unittest
from pathlib import Path

from cachetap import capture, config, store
from tests.replay import adapter

FIXTURE = Path(__file__).parent / "fixtures" / "copilot_responses_ws.json"
BODY_KEYS = {
    "model",
    "input",
    "instructions",
    "tools",
    "reasoning",
    "reasoning_effort",
    "tool_choice",
    "parallel_tool_calls",
    "max_output_tokens",
    "prompt_cache_options",
    "prompt_cache_retention",
    "previous_response_id",
    "stream",
    "text",
    "store",
    "include",
}
STARTED_AT = 100.0


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_log = config.LOG
        adapter.reset(Path(self.tempdir.name) / "requests.jsonl")

    def tearDown(self):
        adapter.reset(self.original_log)
        self.tempdir.cleanup()

    def request(self):
        return {key: value for key, value in self.case["client"].items() if key in BODY_KEYS}

    def begin(self, *, transport="websocket", context_partial=False):
        req = self.request()
        text = json.dumps(req, separators=(",", ":"))
        args = (
            req,
            text,
            self.case["host"],
            self.case["path"],
            len(text.encode("utf-8")),
            STARTED_AT,
        )
        options = {}
        if transport is not None:
            options["transport"] = transport
        if context_partial:
            options["context_partial"] = True
        return capture.begin(*args, **options)

    def record(self, rid):
        with store.LOCK:
            return dict(store.RECORDS[rid])

    def sse_data(self, event):
        # Keep only inference event data; fixture-only headers and metering envelopes stay out.
        data = {key: event[key] for key in ("type", "response", "delta") if key in event}
        return f"data: {json.dumps(data, separators=(',', ':'))}\n\n".encode("utf-8")

    def feed_fixture_events(self, rid, state):
        delta_at = (STARTED_AT + 0.5, STARTED_AT + 0.8)
        delta_index = 0
        for event in self.case["server"]:
            if event["type"] == "response.output_text.delta":
                at = delta_at[delta_index]
                delta_index += 1
            elif event["type"] == "response.completed":
                at = STARTED_AT + 1.5
            else:
                at = STARTED_AT + 0.1
            data = self.sse_data(event)
            self.assertIs(capture.feed(rid, state, data, at=at), data)

    def start(self, rid):
        return capture.start(rid, 101, {}, STARTED_AT, None)

    def finish(self, rid, state):
        capture.finish(
            rid,
            state,
            101,
            STARTED_AT,
            logging.getLogger(__name__),
            ended_at=STARTED_AT + 2.0,
        )

    def test_http_defaults_leave_transport_metadata_absent(self):
        rid = self.begin(transport=None)
        rec = self.record(rid)
        self.assertNotIn("transport", rec)
        self.assertNotIn("context_partial", rec)

    def test_websocket_transport_uses_fixture_request_and_model(self):
        rid = self.begin()
        rec = self.record(rid)
        self.assertEqual(rec["transport"], "websocket")
        self.assertNotIn("context_partial", rec)
        self.assertEqual(rec["host"], self.case["host"])
        self.assertEqual(rec["model"], self.case["expected"]["model"])
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", json.dumps(rec))
        with store.LOCK:
            self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", store.BODIES[rid])

    def test_partial_context_is_not_linked_to_or_from(self):
        partial_id = self.begin(context_partial=True)
        partial = self.record(partial_id)
        self.assertIsNone(partial["prev_id"])
        self.assertEqual(partial["_msgs"], [])
        self.assertTrue(partial["context_partial"])

        next_id = self.begin(transport=None)
        next_record = self.record(next_id)
        self.assertIsNone(next_record["prev_id"])
        self.assertNotEqual(next_record["conv"], partial["conv"])

    def test_fixture_usage_cost_timestamps_and_finish_are_idempotent(self):
        rid = self.begin()
        state = self.start(rid)
        self.feed_fixture_events(rid, state)
        self.finish(rid, state)

        expected = self.case["expected"]
        rec = self.record(rid)
        self.assertEqual(rec["model"], expected["model"])
        self.assertEqual(rec["usage"], expected["usage"])
        self.assertEqual(rec["output"], expected["output"])
        self.assertEqual(rec["verdict"], expected["verdict"])
        self.assertEqual(rec["ttl_s"], expected["ttl_s"])
        self.assertEqual(rec["cost"]["tariff"], expected["tariff"])
        self.assertEqual(rec["cost"]["usd"], expected["usd"])
        self.assertEqual(rec["cost"]["no_cache_usd"], expected["no_cache_usd"])
        self.assertEqual(rec["cost"]["saved_usd"], expected["saved_usd"])
        self.assertEqual(rec["ttft_s"], 0.5)
        self.assertEqual(rec["total_s"], 2.0)
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", json.dumps(rec))

        with store.LOCK:
            total = dict(store.CONV_TOTALS[rec["conv"]])
        self.assertEqual(total["priced"], 1)
        self.assertEqual(total["usd"], expected["usd"])
        self.assertEqual(len(config.LOG.read_text(encoding="utf-8").splitlines()), 1)

        capture.finish(
            rid,
            state,
            101,
            STARTED_AT,
            logging.getLogger(__name__),
            ended_at=STARTED_AT + 3.0,
        )
        capture.fail(rid, state, "late failure", ended_at=STARTED_AT + 4.0)
        self.assertEqual(self.record(rid), rec)
        with store.LOCK:
            self.assertEqual(store.CONV_TOTALS[rec["conv"]]["priced"], 1)
        self.assertEqual(len(config.LOG.read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(state["chunks"], [])
        self.assertFalse(state["reserved"])

    def test_partial_context_keeps_fixture_cost_without_lost_cost(self):
        rid = self.begin(context_partial=True)
        state = self.start(rid)
        self.feed_fixture_events(rid, state)
        self.finish(rid, state)

        rec = self.record(rid)
        self.assertIsNone(rec["prev_id"])
        self.assertEqual(rec["verdict"], "N/A")
        self.assertEqual(
            rec["notes"],
            ["contexto incremental WebSocket: no se dispone del prefijo completo"],
        )
        self.assertEqual(rec["cost"]["usd"], self.case["expected"]["usd"])
        self.assertNotIn("lost_usd", rec["cost"])

    def test_duplicate_fail_with_retained_record_publishes_once(self):
        rid = self.begin()
        state = self.start(rid)
        capture.feed(rid, state, b"partial response")
        client = adapter.subscribe()
        while not client.empty():
            client.get_nowait()

        capture.fail(rid, state, "respuesta WebSocket fallida", ended_at=STARTED_AT + 1.0)
        first_event = client.get_nowait()
        self.assertEqual(first_event["type"], "record")
        after_first = self.record(rid)
        capture.fail(rid, state, "duplicate failure", ended_at=STARTED_AT + 2.0)

        self.assertTrue(client.empty())
        self.assertEqual(self.record(rid), after_first)
        self.assertEqual(after_first["state"], "error")
        self.assertEqual(after_first["ts_end"], STARTED_AT + 1.0)
        self.assertEqual(state["chunks"], [])
        self.assertFalse(state["reserved"])
        with store.LOCK:
            self.assertEqual(store.CONV_TOTALS, {})
        self.assertFalse(config.LOG.exists())

    def test_finish_after_eviction_releases_resources_without_resurrection(self):
        rid = self.begin()
        state = self.start(rid)
        capture.feed(rid, state, b"partial response")
        client = adapter.subscribe()
        while not client.empty():
            client.get_nowait()

        with store.LOCK:
            store.RECORDS.pop(rid)
            body = store.BODIES.pop(rid, None)
            if body is not None:
                store.STATE["body_bytes"] -= len(body.encode("utf-8"))

        self.finish(rid, state)
        self.finish(rid, state)
        capture.fail(rid, state, "late failure", ended_at=STARTED_AT + 3.0)

        with store.LOCK:
            self.assertNotIn(rid, store.RECORDS)
            self.assertEqual(store.CONV_TOTALS, {})
        self.assertTrue(client.empty())
        self.assertEqual(state["chunks"], [])
        self.assertFalse(state["reserved"])
        self.assertFalse(config.LOG.exists())


if __name__ == "__main__":
    unittest.main()
