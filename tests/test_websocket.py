"""Tests for the transport-free Responses WebSocket decoder."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from cachetap import config, record, response_body, websocket
from tests.replay import builders

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


if __name__ == "__main__":
    unittest.main()
