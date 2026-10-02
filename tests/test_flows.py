import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cachetap import config, store
from tests.replay import adapter
from tests.replay.flows import FakeFlow, FakeRequest, FakeResponse


class FlowsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        adapter.reset(Path(tmp.name) / "requests.jsonl")

    def _start_response(self, chunks=()):
        flow = FakeFlow(FakeRequest(
            "POST", "api.anthropic.com", "/v1/messages",
            '{"model":"claude-opus-5-5","messages":[{"role":"user","content":"hola"}]}',
            1790000000.0,
        ))
        adapter.hooks().request(flow)
        flow.response = FakeResponse(200, {}, 1790000000.3)
        adapter.hooks().responseheaders(flow)
        returned = [flow.response.stream(chunk) for chunk in chunks]
        return flow, returned

    def test_request_hook_records_pending_flow(self):
        body = {"model": "claude-opus-5-5", "messages": [{"role": "user", "content": "hola"}]}
        flow = FakeFlow(FakeRequest("POST", "api.anthropic.com", "/v1/messages", json.dumps(body), 1790000000.0))
        adapter.hooks().request(flow)
        recs = adapter.records()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["id"], 1)
        self.assertEqual(recs[0]["state"], "pending")
        self.assertEqual(recs[0]["model"], "claude-opus-5-5")
        self.assertEqual(flow.request.headers["accept-encoding"], "identity")
        self.assertEqual(flow.metadata["tap_id"], 1)
        self.assertEqual(adapter.body_ids(), [1])

    def test_ignored_routes_are_not_recorded(self):
        for method, path in (("GET", "/v1/messages"), ("POST", "/v1/models")):
            with self.subTest(method=method, path=path):
                flow = FakeFlow(FakeRequest(method, "api.anthropic.com", path, "{}", 1790000000.0))
                adapter.hooks().request(flow)
                self.assertEqual(adapter.records(), [])
                self.assertNotIn("tap_id", flow.metadata)

    def test_broken_json_is_recorded_without_model(self):
        flow = FakeFlow(FakeRequest("POST", "api.anthropic.com", "/v1/messages", "esto no es JSON", 1790000000.0))
        adapter.hooks().request(flow)
        recs = adapter.records()
        self.assertEqual(len(recs), 1)
        self.assertIsNone(recs[0]["model"])

    def test_uninspectable_request_is_not_recorded_and_warning_has_no_body(self):
        body = '{"messages": 7, "secret": "private body"}'
        flow = FakeFlow(FakeRequest("POST", "api.anthropic.com", "/v1/messages", body, 1790000000.0))
        with self.assertLogs("tap", level="WARNING") as logs:
            adapter.hooks().request(flow)
        self.assertEqual(adapter.records(), [])
        self.assertNotIn("tap_id", flow.metadata)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("messages debe ser una lista o null", logs.output[0])
        self.assertNotIn(body, logs.output[0])

    def test_request_at_byte_limit_is_captured_and_over_limit_is_skipped(self):
        with mock.patch.object(config, "MAX_REQUEST_BYTES", 2):
            accepted = FakeFlow(FakeRequest(
                "POST", "api.anthropic.com", "/v1/messages", "{}", 1790000000.0
            ))
            adapter.hooks().request(accepted)
            self.assertEqual(accepted.metadata["tap_id"], 1)
            self.assertEqual(adapter.records()[0]["req_bytes"], 2)

            oversized = FakeFlow(FakeRequest(
                "POST", "api.anthropic.com", "/v1/messages", "{} ", 1790000001.0
            ))
            raw_content = oversized.request.raw_content
            with mock.patch.object(oversized.request, "get_text", side_effect=AssertionError("read body")):
                with self.assertLogs("tap", level="WARNING") as logs:
                    adapter.hooks().request(oversized)
            self.assertEqual(oversized.request.raw_content, raw_content)
            self.assertNotIn("tap_id", oversized.metadata)
            self.assertEqual(len(adapter.records()), 1)
            self.assertIn("límite de tamaño de petición", logs.output[0])
            self.assertNotIn("{}", logs.output[0])

    def test_input_string_counts_as_one_message(self):
        flow = FakeFlow(FakeRequest(
            "POST", "api.openai.com", "/v1/responses", '{"input":"hola"}', 1790000000.0
        ))
        adapter.hooks().request(flow)
        rec = adapter.records()[0]
        self.assertEqual(rec["n_msgs"], 1)
        self.assertEqual([segment["name"] for segment in rec["segs"]], ["msg0:text"])

    def test_input_list_keeps_scalar_elements(self):
        flow = FakeFlow(FakeRequest(
            "POST", "api.openai.com", "/v1/responses", '{"input":["texto",42]}', 1790000000.0
        ))
        adapter.hooks().request(flow)
        rec = adapter.records()[0]
        self.assertEqual(rec["n_msgs"], 2)
        self.assertEqual([segment["name"] for segment in rec["segs"]], ["msg0:text", "msg1:text"])

    def test_response_size_limit_counts_utf8_bytes_and_preserves_stream_data(self):
        chunk = "ññ".encode("utf-8")
        with mock.patch.object(config, "MAX_RESPONSE_BYTES", len(chunk)):
            flow, returned = self._start_response([chunk])
            adapter.hooks().response(flow)
        self.assertIs(returned[0], chunk)
        rec = adapter.records()[0]
        self.assertNotIn("capture_limited", rec)
        self.assertEqual(rec["state"], "done")
        self.assertEqual(flow.metadata.get("tap_stream"), None)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        adapter.reset(Path(tmp.name) / "requests.jsonl")
        with mock.patch.object(config, "MAX_RESPONSE_BYTES", len(chunk) - 1):
            flow, returned = self._start_response([chunk])
            adapter.hooks().response(flow)
        self.assertIs(returned[0], chunk)
        rec = adapter.records()[0]
        self.assertEqual(rec["capture_limited"], "response_size")
        self.assertIsNone(rec["usage"])
        self.assertEqual(rec["verdict"], "N/A")
        self.assertEqual(rec["notes"], ["captura incompleta: límite de tamaño de respuesta"])
        self.assertEqual(flow.metadata.get("tap_stream"), None)

    def test_response_over_limit_discards_partial_usage_without_parsing(self):
        usage_chunk = b'data: {"type":"message_start","message":{"usage":{"input_tokens":100}}}\n\n'
        overflow_chunk = b"x"
        with mock.patch.object(config, "MAX_RESPONSE_BYTES", len(usage_chunk)):
            flow, returned = self._start_response([usage_chunk, overflow_chunk])
            with mock.patch("tap.response_body.usage_events") as usage_events, mock.patch(
                "tap.response_body.output_text"
            ) as output_text:
                adapter.hooks().response(flow)
        usage_events.assert_not_called()
        output_text.assert_not_called()
        self.assertEqual(returned, [usage_chunk, overflow_chunk])
        rec = adapter.records()[0]
        self.assertEqual(rec["capture_limited"], "response_size")
        self.assertIsNone(rec["usage"])
        self.assertEqual(rec["raw_usage"], [])
        self.assertEqual(rec["output"], "")
        self.assertEqual(rec["verdict"], "N/A")

    def test_active_capture_limit_is_released_on_response_and_error(self):
        with mock.patch.object(config, "MAX_ACTIVE_CAPTURES", 16):
            flows = [self._start_response()[0] for _ in range(17)]
            self.assertEqual(len(store.ACTIVE_CAPTURES), 16)
            adapter.hooks().response(flows[16])
            self.assertEqual(adapter.records()[16]["capture_limited"], "active_captures")

            adapter.hooks().response(flows[0])
            self.assertEqual(len(store.ACTIVE_CAPTURES), 15)
            after_response, _ = self._start_response()
            self.assertEqual(len(store.ACTIVE_CAPTURES), 16)

            adapter.hooks().error(flows[1])
            self.assertEqual(len(store.ACTIVE_CAPTURES), 15)
            after_error, _ = self._start_response()
            self.assertEqual(len(store.ACTIVE_CAPTURES), 16)
            self.assertTrue(after_response.metadata["tap_stream"]["reserved"])
            self.assertTrue(after_error.metadata["tap_stream"]["reserved"])

    def test_capture_slot_is_released_if_record_was_evicted(self):
        flow, _ = self._start_response()
        with store.LOCK:
            store.RECORDS.pop(flow.metadata["tap_id"])
        adapter.hooks().response(flow)
        self.assertEqual(store.ACTIVE_CAPTURES, set())

    def test_done_clears_active_capture_reservations(self):
        flow, _ = self._start_response()
        self.assertIn(flow.metadata["tap_id"], store.ACTIVE_CAPTURES)
        adapter.hooks().done()
        self.assertEqual(store.ACTIVE_CAPTURES, set())

    def test_response_writes_independent_log_copy_outside_lock(self):
        flow, _ = self._start_response()
        observed = {}

        def append_while_unlocked(rec):
            acquired = store.LOCK.acquire(blocking=False)
            observed["acquired"] = acquired
            if acquired:
                store.LOCK.release()
            observed["record"] = rec
            rec["notes"].append("log-only")

        with mock.patch.object(store, "append_log", side_effect=append_while_unlocked):
            adapter.hooks().response(flow)

        self.assertTrue(observed["acquired"])
        self.assertEqual(observed["record"]["state"], "done")
        self.assertNotIn("log-only", store.RECORDS[flow.metadata["tap_id"]]["notes"])
        self.assertIsNot(observed["record"], store.RECORDS[flow.metadata["tap_id"]])

    def test_log_permission_error_keeps_done_event_and_hides_error_text(self):
        flow, _ = self._start_response()
        events = adapter.subscribe()
        with mock.patch.object(store, "append_log", side_effect=PermissionError("private filesystem detail")):
            with self.assertLogs("tap", level="WARNING") as logs:
                adapter.hooks().response(flow)

        rec = store.RECORDS[flow.metadata["tap_id"]]
        self.assertEqual(rec["state"], "done")
        event = events.get_nowait()
        self.assertEqual(event["type"], "record")
        self.assertEqual(event["rec"]["state"], "done")
        self.assertIn(str(flow.metadata["tap_id"]), logs.output[0])
        self.assertIn("PermissionError", logs.output[0])
        self.assertNotIn("private filesystem detail", logs.output[0])
        self.assertNotEqual(rec["state"], "error")

    def test_load_logs_dashboard_url(self):
        with mock.patch("tap.dashboard.start"):
            with self.assertLogs("tap", level="INFO") as logs:
                adapter.hooks().load(None)
        self.assertIn("http://127.0.0.1:8900", logs.output[0])


if __name__ == "__main__":
    unittest.main()
