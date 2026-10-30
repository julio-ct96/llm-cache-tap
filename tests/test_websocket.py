"""Tests for the transport-free Responses WebSocket decoder."""

import copy
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cachetap import capture, config, record, response_body, store, websocket
from tests.replay import adapter, builders

FIXTURE = Path(__file__).parent / "fixtures" / "copilot_responses_ws.json"


class WebSocketDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def assert_fixed_value_error(self, call, external: str) -> None:
        with self.assertRaises(ValueError) as raised:
            call()
        self.assertNotIn(external, str(raised.exception))

    def test_decodes_minimal_client_request_without_transport_envelope(self) -> None:
        client = self.fixture["client"]
        decoded = websocket.decode_client(
            json.dumps(client, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )

        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertEqual(decoded["model"], self.fixture["expected"]["model"])
        self.assertEqual(decoded["input"], client["input"])
        self.assertEqual(decoded["tools"], client["tools"])
        self.assertEqual(decoded["reasoning"], client["reasoning"])
        self.assertNotIn("type", decoded)
        self.assertNotIn("headers", decoded)

    def test_ignores_unknown_client_message_types(self) -> None:
        self.assertIsNone(websocket.decode_client(b'{"type":"ping"}'))

    def test_rejects_invalid_client_messages_with_fixed_errors(self) -> None:
        malformed = [
            (b"\xff", "secret"),
            (b'{"type":"response.create", "secret":"wire-secret"', "wire-secret"),
            (b"[]", "[]"),
        ]
        for content, external in malformed:
            with self.subTest(content=content):
                self.assert_fixed_value_error(lambda: websocket.decode_client(content), external)

        invalid_requests = [
            {"type": "response.create", "model": 7},
            {"type": "response.create", "input": {"role": "user"}},
            {"type": "response.create", "tools": ["not-an-object"]},
            {"type": "response.create", "previous_response_id": 9},
        ]
        for request in invalid_requests:
            payload = json.dumps(request).encode("utf-8")
            with self.subTest(request=request):
                self.assert_fixed_value_error(
                    lambda: websocket.decode_client(payload), json.dumps(request)
                )

    def test_client_size_boundary_uses_utf8_bytes(self) -> None:
        client = dict(self.fixture["client"])
        client["instructions"] = "café"
        content = json.dumps(client, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.assertGreater(len(content), len(content.decode("utf-8")))

        with patch.object(config, "MAX_REQUEST_BYTES", len(content)):
            self.assertIsNotNone(websocket.decode_client(content))
        with patch.object(config, "MAX_REQUEST_BYTES", len(content) - 1):
            self.assert_fixed_value_error(lambda: websocket.decode_client(content), "café")

    def test_projects_only_allowlisted_fields_from_fixture_events(self) -> None:
        projections: list[record.JsonObject] = []
        for wire_event in self.fixture["server"]:
            decoded = websocket.decode_server(
                json.dumps(wire_event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            projected = websocket.project_event(decoded)
            self.assertIsNotNone(projected)
            assert projected is not None
            projections.append(projected)
            self.assertNotIn("headers", projected)
            self.assertNotIn("copilot_usage", projected)
            self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", repr(projected))

        self.assertEqual(
            projections[0],
            {
                "type": "response.created",
                "response": {"id": "resp_ws_1", "model": "gpt-6-luna"},
            },
        )
        self.assertEqual(projections[1], {"type": "response.output_text.delta", "delta": "Hola"})
        self.assertEqual(projections[2], {"type": "response.output_text.delta", "delta": " mundo"})
        self.assertEqual(
            projections[3],
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_ws_1",
                    "model": "gpt-6-luna",
                    "usage": self.fixture["server"][3]["response"]["usage"],
                },
            },
        )

        original_usage = self.fixture["server"][3]["response"]["usage"]
        projected_usage = projections[3]["response"]["usage"]
        self.assertIsNot(projected_usage, original_usage)
        self.assertIsNot(
            projected_usage["input_tokens_details"], original_usage["input_tokens_details"]
        )

    def test_usage_and_output_text_match_fixture_after_sse_conversion(self) -> None:
        projections = [
            websocket.project_event(websocket.decode_server(json.dumps(event).encode("utf-8")))
            for event in self.fixture["server"]
        ]
        body = "".join(builders.sse(event) for event in projections if event is not None)
        usage = response_body.usage_events(body)

        self.assertEqual(usage[0]["usage"], self.fixture["server"][3]["response"]["usage"])
        self.assertEqual(response_body.output_text(body)[0], self.fixture["expected"]["output"])

    def test_discards_reasoning_tool_and_unknown_events(self) -> None:
        events = [
            {"type": "response.reasoning_summary_text.delta", "delta": "hidden"},
            {"type": "response.function_call_arguments.delta", "delta": "hidden"},
            {"type": "response.future_event", "headers": {"secret": "hidden"}},
        ]
        for event in events:
            with self.subTest(event=event):
                self.assertIsNone(websocket.project_event(event))

    def test_rejects_invalid_server_shapes_without_exposing_values(self) -> None:
        invalid_wire_messages = [
            {"type": 4},
        ]
        for event in invalid_wire_messages:
            content = json.dumps(event).encode("utf-8")
            with self.subTest(event=event):
                self.assert_fixed_value_error(
                    lambda: websocket.decode_server(content), json.dumps(event)
                )

        invalid_events = [
            {"type": "response.output_text.delta", "delta": 5},
            {"type": "response.completed", "response": "private"},
            {"type": "response.completed", "response": {"usage": []}},
        ]
        for event in invalid_events:
            with self.subTest(event=event):
                self.assert_fixed_value_error(lambda: websocket.project_event(event), str(event))

        self.assert_fixed_value_error(lambda: websocket.decode_server(b"\xff"), "\xff")
        self.assert_fixed_value_error(lambda: websocket.decode_server(b"not-json"), "not-json")
        self.assert_fixed_value_error(lambda: websocket.decode_server(b"[]"), "[]")


class WebSocketSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_log = config.LOG
        adapter.reset(Path(self.tempdir.name) / "requests.jsonl")
        self.sessions: list[websocket.Session] = []

    def tearDown(self) -> None:
        for session in self.sessions:
            session.close()
        adapter.reset(self.original_log)
        self.tempdir.cleanup()

    @staticmethod
    def encode(message: record.JsonObject) -> bytes:
        return json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def session(self) -> websocket.Session:
        session = websocket.Session(
            self.fixture["host"], self.fixture["path"], logging.getLogger(__name__)
        )
        self.sessions.append(session)
        return session

    def client_message(
        self,
        session: websocket.Session,
        at: float,
        *,
        previous_response_id: str | None = None,
        user_text: str | None = None,
    ) -> bytes:
        client = copy.deepcopy(self.fixture["client"])
        if previous_response_id is not None:
            client["previous_response_id"] = previous_response_id
        if user_text is not None:
            client["input"][1]["content"][0]["text"] = user_text
        content = self.encode(client)
        session.client(content, at)
        return content

    def send_fixture_server(
        self,
        session: websocket.Session,
        started_at: float,
        *,
        response_id: str = "resp_ws_1",
    ) -> None:
        delta_index = 0
        for original in self.fixture["server"]:
            event = copy.deepcopy(original)
            if isinstance(event.get("response"), dict) and "id" in event["response"]:
                event["response"]["id"] = response_id
            if "response_id" in event:
                event["response_id"] = response_id

            if event["type"] == "response.output_text.delta":
                at = started_at + (0.5 if delta_index == 0 else 0.8)
                delta_index += 1
            elif event["type"] == "response.completed":
                at = started_at + 2.0
            else:
                at = started_at + 0.1
            session.server(self.encode(event), at)

    def records(self) -> list[record.Record]:
        with store.LOCK:
            return copy.deepcopy(list(store.RECORDS.values()))

    def record(self, rid: int) -> record.Record:
        with store.LOCK:
            return copy.deepcopy(store.RECORDS[rid])

    def body(self, rid: int) -> str:
        with store.LOCK:
            return store.BODIES[rid]

    def log_lines(self) -> list[str]:
        if not config.LOG.exists():
            return []
        return config.LOG.read_text(encoding="utf-8").splitlines()

    def assert_no_active_reservations(self) -> None:
        with store.LOCK:
            self.assertEqual(store.ACTIVE_CAPTURES, set())

    def test_fixture_session_records_cost_text_timing_and_transport(self) -> None:
        session = self.session()
        original_request = self.client_message(session, 100.0)
        self.send_fixture_server(session, 100.0)

        rows = self.records()
        self.assertEqual(len(rows), 1)
        rec = rows[0]
        expected = self.fixture["expected"]
        self.assertEqual(rec["transport"], "websocket")
        self.assertEqual(rec["status"], 101)
        self.assertEqual(rec["resp_headers"], {})
        self.assertNotIn("hdr_s", rec)
        self.assertEqual(rec["req_bytes"], len(original_request))
        self.assertEqual(rec["ts"], 100.0)
        self.assertEqual(rec["ttft_s"], 0.5)
        self.assertEqual(rec["total_s"], 2.0)
        self.assertEqual(rec["model"], expected["model"])
        self.assertEqual(rec["usage"], expected["usage"])
        self.assertEqual(rec["output"], expected["output"])
        self.assertEqual(rec["verdict"], expected["verdict"])
        self.assertEqual(rec["ttl_s"], expected["ttl_s"])
        self.assertEqual(rec["cost"]["tariff"], expected["tariff"])
        self.assertEqual(rec["cost"]["usd"], expected["usd"])
        self.assertEqual(rec["cost"]["no_cache_usd"], expected["no_cache_usd"])
        self.assertEqual(rec["cost"]["saved_usd"], expected["saved_usd"])

        body = self.body(rec["id"])
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", body)
        saved_body = json.loads(body)
        self.assertNotIn("headers", saved_body)
        self.assertNotIn("type", saved_body)
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", json.dumps(rec))
        self.assertEqual(len(self.log_lines()), 1)
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", self.log_lines()[0])
        with store.LOCK:
            total = copy.deepcopy(store.CONV_TOTALS[rec["conv"]])
        self.assertEqual(total["priced"], 1)
        self.assert_no_active_reservations()

    def test_two_sequential_responses_keep_ids_usage_text_and_origins_separate(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        self.send_fixture_server(session, 100.0)

        self.client_message(session, 200.0, user_text="segunda solicitud")
        second_usage: record.JsonObject = {
            "input_tokens": 10,
            "input_tokens_details": {
                "cached_tokens": 4,
                "cache_write_tokens": 2,
                "cache_write_tokens_details": {"ttl_30m_tokens": 2},
            },
            "output_tokens": 7,
            "output_tokens_details": {"reasoning_tokens": 1},
            "total_tokens": 17,
        }
        self.send_response(session, "resp_ws_2", "respuesta dos", second_usage, 200.0)

        rows = self.records()
        self.assertEqual(len(rows), 2)
        first, second = rows
        self.assertEqual(first["ts"], 100.0)
        self.assertEqual(first["output"], "Hola mundo")
        self.assertEqual(first["usage"], self.fixture["expected"]["usage"])
        self.assertEqual(second["ts"], 200.0)
        self.assertEqual(second["ttft_s"], 0.5)
        self.assertEqual(second["total_s"], 2.0)
        self.assertNotIn("hdr_s", second)
        self.assertEqual(second["output"], "respuesta dos")
        self.assertEqual(
            second["usage"],
            {
                "read": 4,
                "write": 2,
                "uncached": 4,
                "input_total": 10,
                "output": 7,
                "reasoning": 1,
            },
        )
        self.assertEqual(len(self.log_lines()), 2)
        with store.LOCK:
            priced = sum(total["priced"] for total in store.CONV_TOTALS.values())
        self.assertEqual(priced, 2)
        self.assert_no_active_reservations()

    def test_duplicate_and_old_terminal_are_ignored_and_close_is_idempotent(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        self.send_response_created(session, "resp_ws_1", 100.1)
        completed = self.fixture["server"][3]
        session.server(self.encode(completed), 102.0)
        session.server(self.encode(completed), 103.0)

        self.client_message(session, 200.0, user_text="segunda solicitud")
        session.server(self.encode(completed), 201.0)
        rows = self.records()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["state"], "streaming")
        self.assertNotIn("usage", rows[1])

        session.close(at=202.0)
        session.close(at=203.0)
        rows_after_close = self.records()
        self.assertEqual(len(rows_after_close), 2)
        self.assertEqual(rows_after_close[1]["state"], "error")
        self.assertEqual(rows_after_close[1]["verdict"], "ERR")
        self.assertNotIn("usage", rows_after_close[1])
        self.assertNotIn("cost", rows_after_close[1])
        self.assertEqual(
            rows_after_close[1]["notes"],
            ["conexión WebSocket cerrada antes de completar la respuesta"],
        )
        self.assertEqual(len(self.log_lines()), 1)
        with store.LOCK:
            priced = sum(total["priced"] for total in store.CONV_TOTALS.values())
        self.assertEqual(priced, 1)
        self.assert_no_active_reservations()

    def test_different_id_cannot_complete_an_identified_active_response(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        self.send_response_created(session, "resp_ws_1", 100.1)
        wrong = copy.deepcopy(self.fixture["server"][3])
        wrong["response"]["id"] = "resp_other"
        session.server(self.encode(wrong), 101.0)

        pending = self.records()[0]
        self.assertEqual(pending["state"], "streaming")
        self.assertNotIn("usage", pending)
        with store.LOCK:
            self.assertIn(pending["id"], store.ACTIVE_CAPTURES)

        correct = copy.deepcopy(self.fixture["server"][3])
        session.server(self.encode(correct), 102.0)
        finished = self.record(pending["id"])
        self.assertEqual(finished["state"], "done")
        self.assertEqual(finished["usage"], self.fixture["expected"]["usage"])
        self.assertEqual(len(self.log_lines()), 1)
        self.assert_no_active_reservations()

    def test_previous_response_id_keeps_partial_context_unlinked(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        self.send_fixture_server(session, 100.0)

        self.client_message(session, 200.0, previous_response_id="resp_previous")
        self.send_fixture_server(session, 200.0, response_id="resp_ws_2")
        partial = self.records()[1]
        self.assertTrue(partial["context_partial"])
        self.assertIsNone(partial["prev_id"])
        self.assertEqual(partial["_msgs"], [])
        self.assertEqual(partial["verdict"], "N/A")
        self.assertEqual(
            partial["notes"],
            ["contexto incremental WebSocket: no se dispone del prefijo completo"],
        )
        self.assertEqual(partial["cost"]["usd"], self.fixture["expected"]["usd"])
        self.assertNotIn("lost_usd", partial["cost"])
        self.assertEqual(len(self.log_lines()), 2)
        self.assert_no_active_reservations()

    def test_reasoning_is_not_projected_and_empty_delta_keeps_original_byte_count(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        created = self.encode(
            {"type": "response.created", "response": {"id": "resp_ws_1", "model": "gpt-6-luna"}}
        )
        session.server(created, 100.1)
        empty_delta = self.encode(
            {"type": "response.output_text.delta", "response_id": "resp_ws_1", "delta": ""}
        )
        session.server(empty_delta, 100.2)
        assert session._active is not None
        active = session._active
        self.assertEqual(active.server_bytes, len(created) + len(empty_delta))

        first_delta = self.encode(
            {"type": "response.output_text.delta", "response_id": "resp_ws_1", "delta": "Hola"}
        )
        reasoning = self.encode(
            {
                "type": "response.reasoning_summary_text.delta",
                "delta": "PRIVATE_REASONING_SENTINEL",
            }
        )
        second_delta = self.encode(
            {
                "type": "response.output_text.delta",
                "response_id": "resp_ws_1",
                "delta": " mundo",
            }
        )
        session.server(first_delta, 100.5)
        session.server(reasoning, 100.6)
        session.server(second_delta, 100.8)
        completed = copy.deepcopy(self.fixture["server"][3])
        session.server(self.encode(completed), 102.0)

        rec = self.records()[0]
        self.assertEqual(
            active.server_bytes,
            sum(
                map(
                    len,
                    (
                        created,
                        empty_delta,
                        first_delta,
                        reasoning,
                        second_delta,
                        self.encode(completed),
                    ),
                )
            ),
        )
        self.assertEqual(rec["ttft_s"], 0.5)
        self.assertEqual(rec["output"], "Hola mundo")
        self.assertNotIn("PRIVATE_REASONING_SENTINEL", json.dumps(rec))
        self.assertNotIn("PRIVATE_REASONING_SENTINEL", self.log_lines()[0])
        self.assertNotIn("PRIVATE_REASONING_SENTINEL", json.dumps(rec["raw_usage"]))

    def test_failed_incomplete_and_error_events_fail_without_usage_cost_or_log(self) -> None:
        failures = (
            ("response.failed", "respuesta WebSocket fallida"),
            ("response.incomplete", "respuesta WebSocket incompleta"),
            ("error", "error del protocolo WebSocket"),
        )
        for event_type, note in failures:
            with self.subTest(event_type=event_type):
                adapter.reset(Path(self.tempdir.name) / f"{event_type}.jsonl")
                session = self.session()
                self.client_message(session, 100.0)
                session.server(
                    self.encode(
                        {
                            "type": event_type,
                            "response": {
                                "id": "resp_ws_1",
                                "error": {"message": "PRIVATE_SERVER_ERROR"},
                            },
                        }
                    ),
                    100.5,
                )

                rec = self.records()[0]
                self.assertEqual(rec["state"], "error")
                self.assertEqual(rec["verdict"], "ERR")
                self.assertEqual(rec["notes"], [note])
                self.assertNotIn("usage", rec)
                self.assertNotIn("cost", rec)
                self.assertNotIn("PRIVATE_SERVER_ERROR", json.dumps(rec))
                with store.LOCK:
                    self.assertEqual(store.CONV_TOTALS, {})
                    self.assertEqual(store.ACTIVE_CAPTURES, set())
                self.assertEqual(self.log_lines(), [])
                self.assertTrue(session._disabled)

    def test_first_error_without_response_id_fails_and_releases_slot(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        assert session._active is not None
        active = session._active
        session.server(
            self.encode({"type": "error", "error": {"message": "PRIVATE_ERROR_TEXT"}}),
            100.5,
        )

        rec = self.record(active.rid)
        self.assertEqual(rec["state"], "error")
        self.assertEqual(rec["verdict"], "ERR")
        self.assertEqual(rec["notes"], ["error del protocolo WebSocket"])
        self.assertNotIn("usage", rec)
        self.assertNotIn("cost", rec)
        self.assertNotIn("PRIVATE_ERROR_TEXT", json.dumps(rec))
        self.assertTrue(session._disabled)
        self.assertIsNone(session._active)
        self.assertTrue(active.state["closed"])
        self.assertFalse(active.state["committed"])
        self.assertEqual(active.state["chunks"], [])
        self.assertFalse(active.state["reserved"])
        with store.LOCK:
            self.assertEqual(store.ACTIVE_CAPTURES, set())
            self.assertEqual(store.CONV_TOTALS, {})
        self.assertEqual(self.log_lines(), [])

    def test_invalid_server_and_binary_messages_fail_active_capture_privately(self) -> None:
        messages = (b"\xff", b'{"type":"response.completed","secret":"WIRE_SECRET"')
        for index, content in enumerate(messages):
            with self.subTest(content=content):
                adapter.reset(Path(self.tempdir.name) / f"invalid-{index}.jsonl")
                session = self.session()
                self.client_message(session, 100.0)
                session.server(content, 100.5)
                rec = self.records()[0]
                self.assertEqual(rec["state"], "error")
                self.assertEqual(rec["verdict"], "ERR")
                self.assertEqual(rec["notes"], ["evento WebSocket no inspeccionable"])
                self.assertNotIn("WIRE_SECRET", json.dumps(rec))
                self.assertNotIn("usage", rec)
                self.assertEqual(self.log_lines(), [])
                self.assert_no_active_reservations()
                self.assertTrue(session._disabled)

        adapter.reset(Path(self.tempdir.name) / "binary.jsonl")
        session = self.session()
        self.client_message(session, 100.0)
        session.uninspectable(100.5)
        rec = self.records()[0]
        self.assertEqual(rec["state"], "error")
        self.assertEqual(rec["notes"], ["evento WebSocket no inspeccionable"])
        self.assertNotIn("usage", rec)
        self.assertEqual(self.log_lines(), [])
        self.assert_no_active_reservations()

    def test_overlapping_create_fails_only_first_and_disables_connection(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        second = copy.deepcopy(self.fixture["client"])
        second["input"][1]["content"][0]["text"] = "second request"
        session.client(self.encode(second), 101.0)

        rows = self.records()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], "error")
        self.assertEqual(rows[0]["verdict"], "ERR")
        self.assertEqual(rows[0]["notes"], ["captura WebSocket interrumpida: peticiones solapadas"])
        self.assertNotIn("usage", rows[0])
        self.assertNotIn("cost", rows[0])
        self.assertTrue(session._disabled)
        self.assertIsNone(session._active)
        self.assertEqual(session._last_response_id, None)
        self.assert_no_active_reservations()
        with store.LOCK:
            self.assertEqual(store.CONV_TOTALS, {})
        self.assertEqual(self.log_lines(), [])

        session.client(self.encode(self.fixture["client"]), 102.0)
        session.server(b'{"type":"response.completed","secret":"DISABLED_SECRET"}', 103.0)
        session.uninspectable(104.0)
        session.close(105.0)
        self.assertEqual(len(self.records()), 1)
        self.assertNotIn("DISABLED_SECRET", json.dumps(self.records()))
        self.assertEqual(self.log_lines(), [])

    def test_invalid_or_oversized_create_warns_without_a_record_and_disables(self) -> None:
        cases = (
            (b'{"type":"response.create","secret":"CLIENT_SECRET"', 100),
            (self.encode(self.fixture["client"]), 1),
        )
        for index, (content, limit) in enumerate(cases):
            with self.subTest(index=index):
                adapter.reset(Path(self.tempdir.name) / f"invalid-client-{index}.jsonl")
                session = self.session()
                with patch.object(config, "MAX_REQUEST_BYTES", limit):
                    with self.assertLogs(__name__, level="WARNING") as logs:
                        session.client(content, 100.0)
                self.assertEqual(
                    logs.output, [f"WARNING:{__name__}:Petición WebSocket no inspeccionable"]
                )
                self.assertEqual(self.records(), [])
                self.assertTrue(session._disabled)
                self.assertIsNone(session._active)
                self.assertNotIn("CLIENT_SECRET", logs.output[0])
                self.assertEqual(self.log_lines(), [])

        adapter.reset(Path(self.tempdir.name) / "surrogate-client.jsonl")
        session = self.session()
        invalid_unicode = b'{"type":"response.create","instructions":"\\ud800"}'
        with self.assertLogs(__name__, level="WARNING") as logs:
            session.client(invalid_unicode, 100.0)
        self.assertEqual(logs.output, [f"WARNING:{__name__}:Petición WebSocket no inspeccionable"])
        self.assertEqual(self.records(), [])
        self.assertTrue(session._disabled)
        self.assertEqual(self.log_lines(), [])

    def test_disabled_session_does_not_decode_or_retain_new_events(self) -> None:
        session = self.session()
        with patch.object(config, "MAX_REQUEST_BYTES", 1):
            with self.assertLogs(__name__, level="WARNING"):
                session.client(b'{"type":"response.create"}', 100.0)
        with store.LOCK:
            next_id = store.STATE["next_id"]

        with patch.object(websocket, "decode_client", side_effect=AssertionError("decoded")):
            with patch.object(websocket, "decode_server", side_effect=AssertionError("decoded")):
                session.client(self.encode(self.fixture["client"]), 101.0)
                session.server(b'{"type":"response.completed"}', 102.0)
                session.uninspectable(103.0)
                session.close(104.0)

        with store.LOCK:
            self.assertEqual(store.STATE["next_id"], next_id)
            self.assertEqual(store.ACTIVE_CAPTURES, set())
            self.assertEqual(store.CONV_TOTALS, {})
        self.assertEqual(self.records(), [])
        self.assertEqual(self.log_lines(), [])

    def test_response_wire_limit_accepts_exact_size_and_skips_decode_over_limit(self) -> None:
        exact_event = self.encode({"type": "response.future", "padding": "wire-only"})
        session = self.session()
        self.client_message(session, 100.0)
        with patch.object(config, "MAX_RESPONSE_BYTES", len(exact_event)):
            session.server(exact_event, 100.5)
            self.assertIsNotNone(session._active)
            assert session._active is not None
            self.assertEqual(session._active.server_bytes, len(exact_event))
            self.assertIsNone(session._active.state["limited"])

            with patch.object(websocket, "decode_server", side_effect=AssertionError("decoded")):
                session.server(b"x", 101.0)

        rec = self.records()[0]
        self.assertEqual(rec["capture_limited"], "response_size")
        self.assertEqual(rec["verdict"], "N/A")
        self.assertIsNone(rec["usage"])
        self.assertEqual(rec["raw_usage"], [])
        self.assertEqual(rec["output"], "")
        self.assertTrue(session._disabled)
        self.assertIsNone(session._active)
        self.assert_no_active_reservations()

    def test_response_wire_limit_counts_utf8_bytes_not_characters(self) -> None:
        content = self.encode({"type": "response.future", "note": "ñ"})
        character_count = len(content.decode("utf-8"))
        self.assertGreater(len(content), character_count)
        session = self.session()
        self.client_message(session, 100.0)
        with patch.object(config, "MAX_RESPONSE_BYTES", character_count):
            with patch.object(websocket, "decode_server", side_effect=AssertionError("decoded")):
                session.server(content, 100.5)

        rec = self.records()[0]
        self.assertEqual(rec["capture_limited"], "response_size")
        self.assertEqual(rec["verdict"], "N/A")
        self.assertIsNone(rec["usage"])
        self.assertTrue(session._disabled)
        self.assert_no_active_reservations()

    def test_sse_buffer_limit_is_independent_of_original_wire_bytes(self) -> None:
        events: list[record.JsonObject] = [
            {"type": "response.created", "response": {"id": "resp_ws_1", "model": "gpt-6-luna"}},
            {"type": "response.output_text.delta", "response_id": "resp_ws_1", "delta": "hola"},
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_ws_1",
                    "model": "gpt-6-luna",
                    "usage": {"input_tokens": 2, "output_tokens": 1},
                },
            },
        ]
        wire_messages = [self.encode(event) for event in events]
        wire_limit = sum(map(len, wire_messages))
        session = self.session()
        self.client_message(session, 100.0)
        with patch.object(config, "MAX_RESPONSE_BYTES", wire_limit):
            for index, message in enumerate(wire_messages):
                session.server(message, 100.1 + index)

        rec = self.records()[0]
        self.assertEqual(rec["capture_limited"], "response_size")
        self.assertEqual(rec["verdict"], "N/A")
        self.assertIsNone(rec["usage"])
        self.assertEqual(rec["raw_usage"], [])
        self.assertEqual(rec["output"], "")
        self.assertTrue(session._disabled)
        self.assertIsNone(session._active)
        self.assert_no_active_reservations()

    def test_surrogate_delta_and_deep_usage_are_uninspectable_not_internal_errors(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        self.send_response_created(session, "resp_ws_1", 100.1)
        surrogate_delta = json.dumps(
            {
                "type": "response.output_text.delta",
                "response_id": "resp_ws_1",
                "delta": "\ud800",
            },
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        session.server(surrogate_delta, 100.5)

        rec = self.records()[0]
        self.assertEqual(rec["state"], "error")
        self.assertEqual(rec["notes"], ["evento WebSocket no inspeccionable"])
        self.assertNotIn("usage", rec)
        self.assertNotIn("\ud800", json.dumps(rec))
        self.assertTrue(session._disabled)
        self.assert_no_active_reservations()

        adapter.reset(Path(self.tempdir.name) / "deep-usage.jsonl")
        session = self.session()
        self.client_message(session, 100.0)
        self.send_response_created(session, "resp_ws_1", 100.1)
        usage: record.JsonObject = {"leaf": "PRIVATE_DEEP_USAGE"}
        for _ in range(1500):
            usage = {"nested": usage}
        event: record.JsonObject = {
            "type": "response.completed",
            "response": {"id": "resp_ws_1", "usage": usage},
        }
        with self.assertRaises(ValueError) as raised:
            websocket.project_event(event)
        self.assertNotIn("PRIVATE_DEEP_USAGE", str(raised.exception))
        with patch.object(websocket, "decode_server", return_value=event):
            session.server(b"{}", 101.0)

        rec = self.records()[0]
        self.assertEqual(rec["state"], "error")
        self.assertEqual(rec["notes"], ["evento WebSocket no inspeccionable"])
        self.assertNotIn("usage", rec)
        self.assertNotIn("PRIVATE_DEEP_USAGE", json.dumps(rec))
        self.assertTrue(session._disabled)
        self.assert_no_active_reservations()
        self.assertEqual(self.log_lines(), [])

    def test_http_occupied_slot_finalizes_websocket_without_response_buffer(self) -> None:
        session = self.session()
        with patch.object(config, "MAX_ACTIVE_CAPTURES", 1):
            with store.LOCK:
                self.assertTrue(store.begin_capture(9000))
            self.client_message(session, 100.0)

            rec = self.records()[0]
            self.assertEqual(rec["capture_limited"], "active_captures")
            self.assertEqual(rec["verdict"], "N/A")
            self.assertIsNone(rec["usage"])
            self.assertTrue(session._disabled)
            self.assertIsNone(session._active)
            with store.LOCK:
                self.assertEqual(store.ACTIVE_CAPTURES, {9000})

            with patch.object(websocket, "decode_server", side_effect=AssertionError("decoded")):
                session.server(b'{"type":"response.created"}', 101.0)

            with store.LOCK:
                store.end_capture(9000)
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(len(self.log_lines()), 1)

    def test_clear_or_eviction_is_not_resurrected_by_server_or_close(self) -> None:
        for mode in ("clear", "eviction"):
            with self.subTest(mode=mode):
                adapter.reset(Path(self.tempdir.name) / f"{mode}.jsonl")
                session = self.session()
                self.client_message(session, 100.0)
                assert session._active is not None
                active = session._active
                with store.LOCK:
                    if mode == "clear":
                        store.clear()
                    else:
                        rid = active.rid
                        store.RECORDS.pop(rid)
                        body = store.BODIES.pop(rid)
                        store.STATE["body_bytes"] -= len(body.encode("utf-8"))
                    next_id = store.STATE["next_id"]

                if mode == "clear":
                    session.client(self.encode(self.fixture["client"]), 100.5)
                else:
                    session.server(self.encode(self.fixture["server"][0]), 100.5)
                session.client(self.encode(self.fixture["client"]), 100.6)
                session.server(self.encode(self.fixture["server"][0]), 100.7)
                session.close(101.0)
                self.assertEqual(self.records(), [])
                self.assertTrue(session._disabled)
                self.assertIsNone(session._active)
                self.assertTrue(active.state["closed"])
                self.assertEqual(active.state["chunks"], [])
                self.assertEqual(active.server_bytes, 0)
                self.assertEqual(self.log_lines(), [])
                with store.LOCK:
                    self.assertEqual(store.ACTIVE_CAPTURES, set())
                    self.assertEqual(store.CONV_TOTALS, {})
                    self.assertEqual(store.STATE["next_id"], next_id)

    def test_unexpected_projection_feed_and_precommit_finish_errors_cleanup_then_propagate(
        self,
    ) -> None:
        cases = ("projection", "feed", "precommit-verdict", "precommit-count")
        for operation in cases:
            with self.subTest(operation=operation):
                adapter.reset(Path(self.tempdir.name) / f"runtime-{operation}.jsonl")
                session = self.session()
                self.client_message(session, 100.0)
                self.send_response_created(session, "resp_ws_1", 100.1)
                assert session._active is not None
                active = session._active
                original = RuntimeError(f"synthetic {operation} failure")
                if operation == "projection":
                    target = patch.object(websocket, "project_event", side_effect=original)
                    message = self.encode({"type": "response.output_text.delta", "delta": "hola"})
                elif operation == "feed":
                    target = patch.object(capture, "feed", side_effect=original)
                    message = self.encode(
                        {
                            "type": "response.output_text.delta",
                            "response_id": "resp_ws_1",
                            "delta": "hola",
                        }
                    )
                elif operation == "precommit-verdict":
                    target = patch.object(capture.verdict, "judge", side_effect=original)
                    message = self.encode(
                        {
                            "type": "response.completed",
                            "response": {"id": "resp_ws_1", "usage": {"output_tokens": 1}},
                        }
                    )
                else:
                    count_cost = store.count_cost

                    def count_then_raise(item: record.Record) -> None:
                        count_cost(item)
                        raise original

                    target = patch.object(store, "count_cost", side_effect=count_then_raise)
                    message = self.encode(
                        {
                            "type": "response.completed",
                            "response": {"id": "resp_ws_1", "usage": {"output_tokens": 1}},
                        }
                    )

                with target:
                    with self.assertRaises(RuntimeError) as raised:
                        session.server(message, 101.0)

                self.assertIs(raised.exception, original)
                rec = self.records()[0]
                self.assertEqual(rec["state"], "error")
                self.assertEqual(rec["verdict"], "ERR")
                self.assertEqual(rec["notes"], ["error interno al inspeccionar WebSocket"])
                self.assertNotIn("usage", rec)
                self.assertNotIn("cost", rec)
                self.assertTrue(session._disabled)
                self.assertIsNone(session._active)
                self.assertTrue(active.state["closed"])
                self.assertFalse(active.state["committed"])
                self.assertEqual(active.state["chunks"], [])
                self.assertEqual(active.server_bytes, 0)
                self.assertEqual(self.log_lines(), [])
                with store.LOCK:
                    self.assertEqual(store.ACTIVE_CAPTURES, set())
                    self.assertEqual(store.CONV_TOTALS, {})

    def test_runtime_error_from_real_finish_log_preserves_committed_cost(self) -> None:
        session = self.session()
        self.client_message(session, 100.0)
        self.send_response_created(session, "resp_ws_1", 100.1)
        delta = copy.deepcopy(self.fixture["server"][1])
        session.server(self.encode(delta), 100.5)
        assert session._active is not None
        active = session._active
        completed = copy.deepcopy(self.fixture["server"][3])
        original = RuntimeError("synthetic append_log failure")
        append_log = store.append_log

        def append_then_raise(item: record.Record) -> None:
            append_log(item)
            raise original

        with patch.object(store, "append_log", side_effect=append_then_raise):
            with self.assertRaises(RuntimeError) as raised:
                session.server(self.encode(completed), 102.0)

        self.assertIs(raised.exception, original)
        rec = self.record(active.rid)
        expected = self.fixture["expected"]
        self.assertEqual(rec["state"], "done")
        self.assertEqual(rec["verdict"], expected["verdict"])
        self.assertEqual(rec["usage"], expected["usage"])
        self.assertEqual(rec["cost"]["usd"], expected["usd"])
        self.assertTrue(active.state["closed"])
        self.assertTrue(active.state["committed"])
        self.assertEqual(active.state["chunks"], [])
        self.assertFalse(active.state["reserved"])
        self.assertEqual(active.server_bytes, 0)
        self.assertTrue(session._disabled)
        self.assertIsNone(session._active)
        log_lines = self.log_lines()
        self.assertEqual(len(log_lines), 1)
        self.assertEqual(json.loads(log_lines[0])["state"], "done")
        with store.LOCK:
            total = store.CONV_TOTALS[rec["conv"]]
            self.assertEqual(total["priced"], 1)
            self.assertEqual(total["usd"], expected["usd"])
            self.assertEqual(store.ACTIVE_CAPTURES, set())

        session.close(103.0)
        session.server(self.encode(completed), 104.0)
        self.assertEqual(self.record(active.rid), rec)
        self.assertEqual(len(self.log_lines()), 1)
        with store.LOCK:
            self.assertEqual(store.CONV_TOTALS[rec["conv"]]["priced"], 1)

    def send_response_created(
        self, session: websocket.Session, response_id: str, at: float
    ) -> None:
        event: record.JsonObject = {
            "type": "response.created",
            "response": {"id": response_id, "model": self.fixture["expected"]["model"]},
        }
        session.server(self.encode(event), at)

    def send_response(
        self,
        session: websocket.Session,
        response_id: str,
        output: str,
        usage: record.JsonObject,
        started_at: float,
    ) -> None:
        self.send_response_created(session, response_id, started_at + 0.1)
        delta: record.JsonObject = {
            "type": "response.output_text.delta",
            "response_id": response_id,
            "delta": output,
        }
        session.server(self.encode(delta), started_at + 0.5)
        completed: record.JsonObject = {
            "type": "response.completed",
            "response": {
                "id": response_id,
                "model": self.fixture["expected"]["model"],
                "usage": usage,
            },
        }
        session.server(self.encode(completed), started_at + 2.0)


if __name__ == "__main__":
    unittest.main()
