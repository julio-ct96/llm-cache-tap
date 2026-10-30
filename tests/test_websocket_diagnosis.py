"""Offline regression matrix for ambiguous Responses WebSocket errors."""

import copy
import json
import logging
import tempfile
import unittest
from pathlib import Path

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
                    self.assertEqual([row["notes"] for row in rows], [[error_note]])
                    self.assertTrue(all("usage" not in row for row in rows))
                    self.assertTrue(all("cost" not in row for row in rows))
                    self.assertEqual(totals, {})
                    self.assertEqual(self.log_lines(), [])
                else:
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
