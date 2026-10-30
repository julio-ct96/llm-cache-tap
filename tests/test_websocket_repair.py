"""Offline regression coverage for synthetic Responses WebSocket sequences."""

import copy
import json
import logging
import tempfile
import unittest
from pathlib import Path
from typing import Any

from cachetap import config, store, websocket
from tests.replay import adapter

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "copilot_ws_repair.json"


class WebSocketRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

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

    def records(self) -> list[dict[str, Any]]:
        with store.LOCK:
            return copy.deepcopy(list(store.RECORDS.values()))

    def log_lines(self) -> list[str]:
        if not config.LOG.exists():
            return []
        return config.LOG.read_text(encoding="utf-8").splitlines()

    def event(self, event_type: str, response_id: str) -> dict[str, Any]:
        message = copy.deepcopy(self.fixture["events"][event_type])
        message["response"]["id"] = response_id
        return message

    def run_case(self, case: dict[str, Any]) -> tuple[websocket.Session, list[dict[str, Any]]]:
        adapter.reset(Path(self.tempdir.name) / f"{case['name']}.jsonl")
        session = self.new_session()
        unchanged_messages: list[tuple[dict[str, Any], dict[str, Any]]] = []

        for index, step in enumerate(case["steps"], start=1):
            at = float(index)
            if step == "create":
                message = copy.deepcopy(self.fixture["client"])
                unchanged_messages.append((message, copy.deepcopy(message)))
                session.client(self.encode(message), at)
                continue
            if step == "close":
                session.close(at=at)
                continue

            if step.startswith("created_"):
                event_type = "created"
                response_id = step.removeprefix("created_").upper()
            elif step.startswith("in_progress_"):
                event_type = "in_progress"
                response_id = step.removeprefix("in_progress_").upper()
            elif step.startswith("completed_"):
                event_type = "completed"
                response_id = step.removeprefix("completed_").upper()
            else:
                self.fail(f"unknown synthetic step: {step}")
            message = self.event(event_type, response_id)
            unchanged_messages.append((message, copy.deepcopy(message)))
            session.server(self.encode(message), at)

        for message, original in unchanged_messages:
            self.assertEqual(message, original)
        return session, self.records()

    def test_six_synthetic_sequences_match_the_ambiguity_matrix(self) -> None:
        diagnostics: dict[str, object] = {}

        for case in self.fixture["cases"]:
            with self.subTest(case=case["name"]):
                session, rows = self.run_case(case)
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row["state"], case["state"])
                self.assertEqual(row.get("verdict"), case["verdict"])
                with store.LOCK:
                    totals = copy.deepcopy(store.CONV_TOTALS)
                    reserved = set(store.ACTIVE_CAPTURES)

                self.assertEqual(reserved, set())
                self.assertIsNone(session._active)

                if case["state"] == "error":
                    diagnostic = row["ws_diagnostic"]
                    diagnostics[case["name"]] = diagnostic
                    self.assertEqual(
                        [event["action"] for event in diagnostic["events"]],
                        case["actions"],
                    )
                    self.assertNotIn("usage", row)
                    self.assertNotIn("cost", row)
                    self.assertEqual(totals, {})
                    self.assertEqual(self.log_lines(), [])
                    if case["name"] == "overlap":
                        self.assertTrue(session._disabled)
                else:
                    self.assertIsNone(case["actions"])
                    self.assertNotIn("ws_diagnostic", row)
                    self.assertEqual(row["usage"], self.fixture["expected"]["usage"])
                    self.assertEqual(row["cost"]["usd"], self.fixture["expected"]["usd"])
                    self.assertEqual(len(totals), 1)
                    total = totals[row["conv"]]
                    self.assertEqual(
                        total,
                        {
                            "priced": 1,
                            "unpriced": 0,
                            "usd": self.fixture["expected"]["usd"],
                            "no_cache_usd": row["cost"]["no_cache_usd"],
                            "saved_usd": row["cost"]["saved_usd"],
                            "lost_usd": row["cost"].get("lost_usd", 0.0),
                        },
                    )
                    self.assertEqual(len(self.log_lines()), 1)

        self.assertEqual(diagnostics["other_same"], diagnostics["other_different"])


if __name__ == "__main__":
    unittest.main()
