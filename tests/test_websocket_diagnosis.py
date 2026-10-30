"""Offline regression matrix for ambiguous Responses WebSocket errors."""

import copy
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cachetap import config, store, websocket
from tests.replay import adapter

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REQUEST_FIXTURE = FIXTURE_DIR / "copilot_responses_ws.json"
DIAGNOSIS_FIXTURE = FIXTURE_DIR / "copilot_ws_diagnosis.json"
OVERLAP_NOTE = "captura WebSocket interrumpida: peticiones solapadas"
CLOSE_NOTE = "conexión WebSocket cerrada antes de completar la respuesta"


class WebSocketDiagnosisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
        cls.diagnosis = json.loads(DIAGNOSIS_FIXTURE.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_log = config.LOG
        self.sessions: list[websocket.Session] = []
        adapter.reset(Path(self.tempdir.name) / "requests.jsonl")

    def tearDown(self) -> None:
        for session in self.sessions:
            session.close()
        adapter.reset(self.original_log)
        self.tempdir.cleanup()

    @staticmethod
    def encode(message: object) -> bytes:
        return json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def new_session(self) -> websocket.Session:
        session = websocket.Session(
            self.fixture["host"], self.fixture["path"], logging.getLogger(__name__)
        )
        self.sessions.append(session)
        return session

    def send_server_event(
        self, session: websocket.Session, original: dict[str, object], at: float
    ) -> None:
        session.server(self.encode(copy.deepcopy(original)), at)

    def records(self) -> list[dict[str, object]]:
        with store.LOCK:
            return copy.deepcopy(list(store.RECORDS.values()))

    def log_lines(self) -> list[str]:
        if not config.LOG.exists():
            return []
        return config.LOG.read_text(encoding="utf-8").splitlines()

    def run_case(self, case: dict[str, object]) -> tuple[websocket.Session, float]:
        session = self.new_session()
        last_at = 0.0
        for index, step in enumerate(case["steps"], start=1):
            at = float(index)
            last_at = at
            if step in {"create", "create_generate_false"}:
                client = copy.deepcopy(self.fixture["client"])
                if step == "create_generate_false":
                    client["generate"] = False
                session.client(self.encode(client), at)
            elif step == "created":
                self.send_server_event(session, self.fixture["server"][0], at)
            elif step in {"completed", "wrong_completed"}:
                completed = copy.deepcopy(self.fixture["server"][3])
                if step == "wrong_completed":
                    completed["response"]["id"] = "resp_artificial_other"
                session.server(self.encode(completed), at)
            elif step == "close":
                session.close(at=at)
            else:
                self.fail(f"unknown synthetic step: {step}")
        return session, last_at

    def test_decode_client_drops_generate_false_from_normalized_body(self) -> None:
        client = copy.deepcopy(self.fixture["client"])
        client["generate"] = False

        decoded = websocket.decode_client(self.encode(client))

        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertNotIn("generate", decoded)

    def test_seven_synthetic_sequences_match_the_ambiguity_matrix(self) -> None:
        observed_notes: dict[str, str | None] = {}
        start = {
            "direction": "client",
            "event": "response.create",
            "action": "start",
            "identified": False,
            "id_relation": "missing",
            "generate": "absent",
            "incremental": False,
        }
        expected_steps = {
            "create_before_created": [
                start,
                {
                    "direction": "client",
                    "event": "response.create",
                    "action": "overlap",
                    "identified": False,
                    "id_relation": "missing",
                    "generate": "absent",
                    "incremental": False,
                },
            ],
            "created_then_create": [
                start,
                {
                    "direction": "server",
                    "event": "response.created",
                    "action": "observe",
                    "identified": False,
                    "id_relation": "unbound",
                },
                {
                    "direction": "client",
                    "event": "response.create",
                    "action": "overlap",
                    "identified": True,
                    "id_relation": "missing",
                    "generate": "absent",
                    "incremental": False,
                },
            ],
            "completed_without_created": [
                start,
                {
                    "direction": "server",
                    "event": "response.completed",
                    "action": "ignore_no_id",
                    "identified": False,
                    "id_relation": "unbound",
                },
                {
                    "direction": "client",
                    "event": "response.create",
                    "action": "overlap",
                    "identified": False,
                    "id_relation": "missing",
                    "generate": "absent",
                    "incremental": False,
                },
            ],
            "mismatched_completed": [
                start,
                {
                    "direction": "server",
                    "event": "response.created",
                    "action": "observe",
                    "identified": False,
                    "id_relation": "unbound",
                },
                {
                    "direction": "server",
                    "event": "response.completed",
                    "action": "ignore_other_id",
                    "identified": True,
                    "id_relation": "other",
                },
                {
                    "direction": "client",
                    "event": "response.create",
                    "action": "overlap",
                    "identified": True,
                    "id_relation": "missing",
                    "generate": "absent",
                    "incremental": False,
                },
            ],
            "generate_false_then_create": [
                {**start, "generate": "false"},
                {
                    "direction": "client",
                    "event": "response.create",
                    "action": "overlap",
                    "identified": False,
                    "id_relation": "missing",
                    "generate": "absent",
                    "incremental": False,
                },
            ],
            "close_before_completed": [
                start,
                {
                    "direction": "server",
                    "event": "response.created",
                    "action": "observe",
                    "identified": False,
                    "id_relation": "unbound",
                },
                {
                    "direction": "local",
                    "event": "close",
                    "action": "fail",
                    "identified": True,
                    "id_relation": "missing",
                },
            ],
        }

        for case in self.diagnosis["cases"]:
            with self.subTest(case=case["name"]):
                adapter.reset(Path(self.tempdir.name) / f"{case['name']}.jsonl")
                session, last_at = self.run_case(case)
                rows = self.records()

                self.assertEqual([row["state"] for row in rows], case["states"])
                self.assertEqual([row.get("verdict") for row in rows], case["verdicts"])
                with store.LOCK:
                    reserved = len(store.ACTIVE_CAPTURES)
                    totals = copy.deepcopy(store.CONV_TOTALS)
                self.assertEqual(reserved, case["reserved"])
                self.assertEqual(session._disabled, case["disabled"])

                error_note = case["error_note"]
                observed_notes[case["name"]] = error_note
                if error_note is not None:
                    self.assertEqual(
                        rows[0]["ws_diagnostic"],
                        {
                            "events": expected_steps[case["name"]],
                            "truncated": False,
                            "omitted_server_events": 0,
                        },
                    )
                    self.assertEqual([row["notes"] for row in rows], [[error_note]])
                    self.assertTrue(all("usage" not in row for row in rows))
                    self.assertTrue(all("cost" not in row for row in rows))
                    self.assertEqual(totals, {})
                    self.assertEqual(self.log_lines(), [])
                else:
                    self.assertNotIn("ws_diagnostic", rows[0])
                    notes = [note for row in rows for note in row.get("notes", [])]
                    self.assertNotIn(OVERLAP_NOTE, notes)
                    self.assertNotIn(CLOSE_NOTE, notes)

                session.close(at=last_at + 1.0)
                with store.LOCK:
                    self.assertEqual(store.ACTIVE_CAPTURES, set())

        overlap_cases = [
            case for case in self.diagnosis["cases"] if case["error_note"] == OVERLAP_NOTE
        ]
        self.assertEqual(len(overlap_cases), 5)
        self.assertEqual({observed_notes[case["name"]] for case in overlap_cases}, {OVERLAP_NOTE})
        self.assertNotEqual(observed_notes["close_before_completed"], OVERLAP_NOTE)

    def test_generate_is_classified_exactly_and_incremental_id_is_not_retained(self) -> None:
        cases = (
            ("absent", None, False, "absent"),
            ("true", True, True, "true"),
            ("false", False, True, "false"),
            ("invalid-zero", 0, True, "invalid"),
            ("invalid-one", 1, True, "invalid"),
            ("invalid-null", None, True, "invalid"),
            ("invalid-text", "GENERATE_SECRET", True, "invalid"),
            ("invalid-object", {"marker": "GENERATE_SECRET"}, True, "invalid"),
        )
        normalized_fixture = websocket.decode_client(self.encode(self.fixture["client"]))
        for index, (name, value, present, expected) in enumerate(cases):
            with self.subTest(case=name):
                adapter.reset(Path(self.tempdir.name) / f"generate-{index}.jsonl")
                session = self.new_session()
                create = copy.deepcopy(self.fixture["client"])
                if present:
                    create["generate"] = value
                encoded = self.encode(create)
                decoded = websocket.decode_client(encoded)
                self.assertEqual(decoded, normalized_fixture)
                self.assertIsNotNone(decoded)
                assert decoded is not None
                self.assertNotIn("generate", decoded)

                session.client(encoded, 1.0)
                assert session._active is not None
                self.assertEqual(session._active.diagnostic_events[0]["generate"], expected)
                session.client(encoded, 2.0)

                diagnostic = self.records()[0]["ws_diagnostic"]
                self.assertEqual(diagnostic["events"][0]["generate"], expected)
                self.assertEqual(diagnostic["events"][-1]["generate"], expected)
                self.assertNotIn("GENERATE_SECRET", json.dumps(diagnostic))

        adapter.reset(Path(self.tempdir.name) / "incremental.jsonl")
        session = self.new_session()
        incremental = copy.deepcopy(self.fixture["client"])
        incremental["previous_response_id"] = "PREVIOUS_ID_SECRET"
        session.client(self.encode(incremental), 1.0)
        session.client(self.encode(incremental), 2.0)
        diagnostic = self.records()[0]["ws_diagnostic"]
        self.assertTrue(diagnostic["events"][0]["incremental"])
        self.assertTrue(diagnostic["events"][-1]["incremental"])
        self.assertNotIn("PREVIOUS_ID_SECRET", json.dumps(diagnostic))

    def test_only_control_metadata_and_id_relations_are_retained(self) -> None:
        session = self.new_session()
        client = copy.deepcopy(self.fixture["client"])
        client["headers"] = {"authorization": "HEADER_SECRET"}
        client["input"][0]["content"][0]["text"] = "INPUT_SECRET"
        session.client(self.encode(client), 1.0)
        active_id = "ACTIVE_ID_SECRET"
        self.send_server_event(
            session,
            {"type": "response.created", "response": {"id": active_id}},
            2.0,
        )
        self.send_server_event(
            session,
            {"type": "response.in_progress", "response": {"id": active_id}},
            3.0,
        )
        self.send_server_event(
            session,
            {
                "type": "response.output_text.delta",
                "response_id": active_id,
                "delta": "DELTA_SECRET",
            },
            4.0,
        )
        self.send_server_event(
            session,
            {
                "type": "response.reasoning_summary_text.delta",
                "response_id": active_id,
                "delta": "REASONING_SECRET",
            },
            5.0,
        )
        self.send_server_event(
            session,
            {"type": "UNKNOWN_TYPE_SECRET", "data": "UNKNOWN_DATA_SECRET"},
            6.0,
        )
        self.send_server_event(
            session,
            {
                "type": "error",
                "response_id": active_id,
                "error": {"message": "ERROR_SECRET"},
            },
            7.0,
        )

        diagnostic = self.records()[0]["ws_diagnostic"]
        self.assertEqual(
            diagnostic,
            {
                "events": [
                    {
                        "direction": "client",
                        "event": "response.create",
                        "action": "start",
                        "identified": False,
                        "id_relation": "missing",
                        "generate": "absent",
                        "incremental": False,
                    },
                    {
                        "direction": "server",
                        "event": "response.created",
                        "action": "observe",
                        "identified": False,
                        "id_relation": "unbound",
                    },
                    {
                        "direction": "server",
                        "event": "response.in_progress",
                        "action": "observe",
                        "identified": True,
                        "id_relation": "active",
                    },
                    {
                        "direction": "server",
                        "event": "error",
                        "action": "fail",
                        "identified": True,
                        "id_relation": "active",
                    },
                ],
                "truncated": False,
                "omitted_server_events": 3,
            },
        )
        serialized = json.dumps(diagnostic)
        for sentinel in (
            "HEADER_SECRET",
            "INPUT_SECRET",
            active_id,
            "DELTA_SECRET",
            "REASONING_SECRET",
            "UNKNOWN_TYPE_SECRET",
            "UNKNOWN_DATA_SECRET",
            "ERROR_SECRET",
        ):
            self.assertNotIn(sentinel, serialized)

    def test_missing_and_previous_ids_are_only_relations(self) -> None:
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        self.send_server_event(
            session, {"type": "response.created", "response": {"model": "gpt-6-luna"}}, 2.0
        )
        session.client(self.encode(self.fixture["client"]), 3.0)
        diagnostic = self.records()[0]["ws_diagnostic"]
        self.assertEqual(diagnostic["events"][1]["action"], "ignore_no_id")
        self.assertEqual(diagnostic["events"][1]["id_relation"], "missing")

        adapter.reset(Path(self.tempdir.name) / "previous.jsonl")
        session = self.new_session()
        # A previous terminal is observed only after a successful response on this connection.
        session.client(self.encode(self.fixture["client"]), 1.0)
        self.send_server_event(
            session,
            {"type": "response.created", "response": {"id": "LAST_ID_SECRET"}},
            2.0,
        )
        self.send_server_event(
            session,
            {
                "type": "response.completed",
                "response": {"id": "LAST_ID_SECRET", "usage": {}},
            },
            3.0,
        )
        session.client(self.encode(self.fixture["client"]), 4.0)
        self.send_server_event(
            session,
            {
                "type": "response.completed",
                "response": {"id": "LAST_ID_SECRET", "usage": {}},
            },
            5.0,
        )
        session.client(self.encode(self.fixture["client"]), 6.0)
        diagnostic = self.records()[1]["ws_diagnostic"]
        self.assertEqual(diagnostic["events"][1]["action"], "ignore_previous")
        self.assertEqual(diagnostic["events"][1]["id_relation"], "last")
        self.assertNotIn("LAST_ID_SECRET", json.dumps(diagnostic))

    def test_invalid_messages_and_unexpected_projection_are_sanitized(self) -> None:
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        with self.assertLogs(__name__, level="WARNING"):
            session.client(b'{"type":"response.create","secret":"CLIENT_SECRET"', 2.0)
        rec = self.records()[0]
        self.assertEqual(
            rec["ws_diagnostic"]["events"][-1],
            {
                "direction": "client",
                "event": "invalid",
                "action": "fail",
                "identified": False,
                "id_relation": "missing",
            },
        )
        self.assertNotIn("CLIENT_SECRET", json.dumps(rec["ws_diagnostic"]))

        adapter.reset(Path(self.tempdir.name) / "invalid-server.jsonl")
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        session.server(b'{"type":"response.completed","secret":"SERVER_SECRET"', 2.0)
        invalid = self.records()[0]["ws_diagnostic"]
        self.assertEqual(invalid["events"][-1]["event"], "invalid")
        self.assertEqual(invalid["events"][-1]["action"], "fail")
        self.assertNotIn("SERVER_SECRET", json.dumps(invalid))

        adapter.reset(Path(self.tempdir.name) / "unexpected.jsonl")
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        original = RuntimeError("PROJECTION_SECRET")
        with patch.object(websocket, "project_event", side_effect=original):
            with self.assertRaises(RuntimeError) as raised:
                session.server(self.encode({"type": "response.created"}), 2.0)
        self.assertIs(raised.exception, original)
        failed = self.records()[0]
        self.assertEqual(failed["state"], "error")
        self.assertEqual(
            failed["ws_diagnostic"]["events"],
            [
                {
                    "direction": "client",
                    "event": "response.create",
                    "action": "start",
                    "identified": False,
                    "id_relation": "missing",
                    "generate": "absent",
                    "incremental": False,
                }
            ],
        )
        self.assertNotIn("PROJECTION_SECRET", json.dumps(failed["ws_diagnostic"]))

    def test_committed_log_error_does_not_publish_diagnostic(self) -> None:
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        self.send_server_event(
            session,
            {"type": "response.created", "response": {"id": "COMMITTED_ID_SECRET"}},
            2.0,
        )
        original = RuntimeError("LOG_SECRET")
        with patch.object(store, "append_log", side_effect=original):
            with self.assertRaises(RuntimeError) as raised:
                self.send_server_event(
                    session,
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "COMMITTED_ID_SECRET",
                            "usage": {"input_tokens": 1, "output_tokens": 1},
                        },
                    },
                    3.0,
                )
        self.assertIs(raised.exception, original)
        rec = self.records()[0]
        self.assertEqual(rec["state"], "done")
        self.assertNotIn("ws_diagnostic", rec)
        self.assertNotIn("LOG_SECRET", json.dumps(rec))

    def test_text_deltas_only_increment_omitted_count_across_ignored_branches(self) -> None:
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        assert session._active is not None
        active = session._active

        self.send_server_event(
            session,
            {
                "type": "response.output_text.delta",
                "response_id": "UNBOUND_DELTA_ID_SECRET",
                "delta": "UNBOUND_DELTA_TEXT_SECRET",
            },
            2.0,
        )
        self.assertEqual(list(active.state["chunks"]), [])
        self.assertEqual(active.omitted_server_events, 1)

        active_id = "ACTIVE_DELTA_ID_SECRET"
        self.send_server_event(
            session,
            {"type": "response.created", "response": {"id": active_id}},
            3.0,
        )
        chunks_after_created = list(active.state["chunks"])
        self.send_server_event(
            session,
            {
                "type": "response.output_text.delta",
                "response_id": "OTHER_DELTA_ID_SECRET",
                "delta": "OTHER_DELTA_TEXT_SECRET",
            },
            4.0,
        )
        self.assertEqual(list(active.state["chunks"]), chunks_after_created)
        self.assertEqual(active.omitted_server_events, 2)

        self.send_server_event(
            session,
            {"type": "response.output_text.delta", "delta": "MISSING_ID_DELTA_TEXT_SECRET"},
            5.0,
        )
        self.assertIn(b"MISSING_ID_DELTA_TEXT_SECRET", b"".join(active.state["chunks"]))
        self.assertEqual(active.omitted_server_events, 3)

        self.send_server_event(
            session,
            {
                "type": "error",
                "response_id": active_id,
                "error": {"message": "FAIL_AFTER_DELTAS_SECRET"},
            },
            6.0,
        )
        diagnostic = self.records()[0]["ws_diagnostic"]
        self.assertEqual(
            [step["event"] for step in diagnostic["events"]],
            ["response.create", "response.created", "error"],
        )
        self.assertEqual(
            [step["action"] for step in diagnostic["events"]], ["start", "observe", "fail"]
        )
        self.assertEqual(diagnostic["omitted_server_events"], 3)
        allowed_events = {
            "response.create",
            "response.created",
            "response.in_progress",
            "response.completed",
            "response.failed",
            "response.incomplete",
            "error",
            "invalid",
            "close",
            "uninspectable",
        }
        self.assertTrue(all(step["event"] in allowed_events for step in diagnostic["events"]))
        serialized = json.dumps(diagnostic)
        for sentinel in (
            "UNBOUND_DELTA_ID_SECRET",
            "UNBOUND_DELTA_TEXT_SECRET",
            active_id,
            "OTHER_DELTA_ID_SECRET",
            "OTHER_DELTA_TEXT_SECRET",
            "MISSING_ID_DELTA_TEXT_SECRET",
            "FAIL_AFTER_DELTAS_SECRET",
        ):
            self.assertNotIn(sentinel, serialized)

    def test_success_releases_diagnostic_state_without_changing_result(self) -> None:
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        assert session._active is not None
        active = session._active
        server_messages = [self.encode(event) for event in self.fixture["server"]]
        for index, content in enumerate(server_messages, start=1):
            session.server(content, 1.0 + index)

        rec = self.records()[0]
        self.assertEqual(rec["state"], "done")
        self.assertEqual(rec["verdict"], self.fixture["expected"]["verdict"])
        self.assertEqual(rec["cost"]["usd"], self.fixture["expected"]["usd"])
        self.assertNotIn("ws_diagnostic", rec)
        self.assertEqual(
            session._last_response_id,
            self.fixture["server"][3]["response"]["id"],
        )
        self.assertIsNone(session._active)
        self.assertEqual(list(active.diagnostic_events), [])
        self.assertFalse(active.diagnostic_truncated)
        self.assertEqual(active.omitted_server_events, 0)
        self.assertEqual(active.server_bytes, sum(map(len, server_messages)))

    def test_diagnostic_ring_truncates_and_omitted_count_saturates(self) -> None:
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        assert session._active is not None
        active = session._active
        response_id = "RING_ID_SECRET"
        for index in range(31):
            self.send_server_event(
                session,
                {"type": "response.created", "response": {"id": response_id}},
                2.0 + index,
            )
        session.close(at=40.0)
        diagnostic = self.records()[0]["ws_diagnostic"]
        self.assertEqual(len(diagnostic["events"]), 32)
        self.assertTrue(diagnostic["truncated"])
        self.assertEqual(diagnostic["events"][0]["event"], "response.created")
        self.assertEqual(diagnostic["events"][-1]["event"], "close")
        self.assertNotIn(response_id, json.dumps(diagnostic))
        self.assertEqual(list(active.diagnostic_events), [])
        self.assertFalse(active.diagnostic_truncated)
        self.assertEqual(active.omitted_server_events, 0)
        stored_before = self.records()[0]
        session.server(self.encode({"type": "late_event_secret"}), 41.0)
        session.client(self.encode(self.fixture["client"]), 42.0)
        self.assertEqual(self.records()[0], stored_before)

        adapter.reset(Path(self.tempdir.name) / "saturated.jsonl")
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        for index in range(300):
            self.send_server_event(
                session,
                {"type": f"unknown_type_{index}", "private": "UNKNOWN_SECRET"},
                2.0 + index,
            )
        session.close(at=400.0)
        saturated = self.records()[0]["ws_diagnostic"]
        self.assertEqual(saturated["omitted_server_events"], 255)
        self.assertEqual(
            [step["event"] for step in saturated["events"]], ["response.create", "close"]
        )
        self.assertNotIn("UNKNOWN_SECRET", json.dumps(saturated))

    def test_clear_eviction_and_response_limit_release_local_diagnostic(self) -> None:
        for mode in ("clear", "eviction"):
            with self.subTest(mode=mode):
                adapter.reset(Path(self.tempdir.name) / f"release-{mode}.jsonl")
                session = self.new_session()
                session.client(self.encode(self.fixture["client"]), 1.0)
                assert session._active is not None
                active = session._active
                self.send_server_event(
                    session,
                    {"type": "response.created", "response": {"id": "CLEANUP_ID_SECRET"}},
                    2.0,
                )
                with store.LOCK:
                    if mode == "clear":
                        store.clear()
                    else:
                        store.RECORDS.pop(active.rid)
                        body = store.BODIES.pop(active.rid)
                        store.STATE["body_bytes"] -= len(body.encode("utf-8"))
                session.client(self.encode(self.fixture["client"]), 3.0)
                self.assertEqual(self.records(), [])
                self.assertEqual(list(active.diagnostic_events), [])
                self.assertFalse(active.diagnostic_truncated)
                self.assertEqual(active.omitted_server_events, 0)

        adapter.reset(Path(self.tempdir.name) / "limited.jsonl")
        session = self.new_session()
        session.client(self.encode(self.fixture["client"]), 1.0)
        assert session._active is not None
        active = session._active
        with patch.object(config, "MAX_RESPONSE_BYTES", 0):
            session.server(b'{"type":"response.created"}', 2.0)
        limited = self.records()[0]
        self.assertEqual(limited["capture_limited"], "response_size")
        self.assertNotIn("ws_diagnostic", limited)
        self.assertEqual(list(active.diagnostic_events), [])
        self.assertFalse(active.diagnostic_truncated)
        self.assertEqual(active.omitted_server_events, 0)
