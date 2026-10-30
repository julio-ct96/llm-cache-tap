"""Synthetic tests for the mitmproxy WebSocket hooks."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import mitmproxy.http
import mitmproxy.websocket
from mitmproxy.test import tflow

import tap
from cachetap import config, store

_HOST = "githubcopilot.com"
_MODEL = "gpt-4.1"
_REQUEST_SENTINEL = "WEBSOCKET_TRANSPORT_SENTINEL"


def _flow(
    *,
    method: str = "GET",
    host: str = _HOST,
    path: str = "/responses",
    status: int = 101,
    with_websocket: bool = True,
) -> mitmproxy.http.HTTPFlow:
    request = mitmproxy.http.Request.make(
        method,
        f"https://{host}{path}",
        headers={"authorization": _REQUEST_SENTINEL},
    )
    request.timestamp_start = 100.0
    request.timestamp_end = 100.1
    response = mitmproxy.http.Response.make(status)
    response.timestamp_start = 100.1
    ws = mitmproxy.websocket.WebSocketData() if with_websocket else False
    return tflow.tflow(req=request, resp=response, ws=ws, live=False)


def _message(
    flow: mitmproxy.http.HTTPFlow,
    *,
    from_client: bool,
    payload: dict[str, object] | bytes,
    timestamp: float,
    opcode: int = 1,
    dropped: bool = False,
    injected: bool = False,
) -> mitmproxy.websocket.WebSocketMessage:
    content = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    message = mitmproxy.websocket.WebSocketMessage(
        opcode,
        from_client,
        content,
        timestamp=timestamp,
        dropped=dropped,
        injected=injected,
    )
    assert flow.websocket is not None
    flow.websocket.messages.append(message)
    history_before = tuple(flow.websocket.messages)
    states_before = tuple(item.get_state() for item in history_before)
    tap.websocket_message(flow)
    history_after = tuple(flow.websocket.messages)
    states_after = tuple(item.get_state() for item in history_after)
    assert len(history_after) == len(history_before)
    assert all(before is after for before, after in zip(history_before, history_after, strict=True))
    assert states_after == states_before
    return message


def _send_exchange(
    flow: mitmproxy.http.HTTPFlow,
    response_id: str,
    *,
    at: float,
) -> None:
    _message(
        flow,
        from_client=True,
        payload={
            "type": "response.create",
            "model": _MODEL,
            "input": f"hello {response_id}",
            "stream": True,
            "headers": {"authorization": _REQUEST_SENTINEL},
        },
        timestamp=at,
    )
    _message(
        flow,
        from_client=False,
        payload={"type": "response.created", "response": {"id": response_id, "model": _MODEL}},
        timestamp=at + 0.1,
    )
    _message(
        flow,
        from_client=False,
        payload={
            "type": "response.completed",
            "response": {
                "id": response_id,
                "model": _MODEL,
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 3,
                    "input_tokens_details": {"cached_tokens": 0},
                },
            },
        },
        timestamp=at + 0.2,
    )


def _load_fixture() -> dict[str, Any]:
    path = Path(__file__).parent / "fixtures" / "copilot_responses_ws.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _play_fixture_case(case: dict[str, Any], host: str) -> tuple[mitmproxy.http.HTTPFlow, int]:
    with store.LOCK:
        before = set(store.RECORDS)
    flow = _flow(host=host, path=case["path"])
    tap.websocket_start(flow)
    try:
        _message(flow, from_client=True, payload=case["client"], timestamp=101.0)
        for index, event in enumerate(case["server"]):
            _message(
                flow,
                from_client=False,
                payload=event,
                timestamp=101.1 + index / 10,
            )
    finally:
        tap.websocket_end(flow)
    with store.LOCK:
        created = [rid for rid in store.RECORDS if rid not in before]
    if len(created) != 1:
        raise AssertionError(f"fixture created {len(created)} records, expected one")
    return flow, created[0]


def play_fixture() -> tuple[mitmproxy.http.HTTPFlow, int]:
    """Play the contract fixture; caller owns store/log setup and reset."""
    case = _load_fixture()
    return _play_fixture_case(case, case["host"])


class WebSocketHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log_patch = patch.object(config, "LOG", Path(self.temp.name) / "requests.jsonl")
        self.log_patch.start()
        self.addCleanup(self.log_patch.stop)
        self._reset_state()

    def tearDown(self) -> None:
        self._reset_state()

    @staticmethod
    def _reset_state() -> None:
        for session in tuple(tap.SOCKETS.values()):
            session.close()
        tap.SOCKETS.clear()
        with store.LOCK:
            store.clear()

    def _record_ids(self) -> set[int]:
        with store.LOCK:
            return set(store.RECORDS)

    def test_auto_and_handshake_create_no_row_but_fixture_create_does(self) -> None:
        auto = _flow(method="POST", path="/auto", status=200)
        tap.request(auto)
        tap.responseheaders(auto)
        tap.response(auto)
        self.assertEqual(self._record_ids(), set())

        handshake = _flow(path="/responses?mode=stream")
        tap.request(handshake)
        tap.websocket_start(handshake)
        self.assertIn(handshake.id, tap.SOCKETS)
        self.assertEqual(self._record_ids(), set())
        tap.websocket_end(handshake)
        self.assertEqual(self._record_ids(), set())

        flow, rid = play_fixture()
        self.assertNotIn(flow.id, tap.SOCKETS)
        self.assertEqual(self._record_ids(), {rid})
        with store.LOCK:
            record = store.RECORDS[rid]
            body = store.BODIES[rid]
        case = _load_fixture()
        expected = case["expected"]
        self.assertEqual(record["host"], case["host"])
        self.assertEqual(record["path"], case["path"])
        self.assertEqual(record["model"], expected["model"])
        self.assertEqual(record["usage"], expected["usage"])
        self.assertEqual(record["output"], expected["output"])
        self.assertEqual(record["verdict"], expected["verdict"])
        self.assertEqual(record["ttl_s"], expected["ttl_s"])
        self.assertEqual(record["cost"]["tariff"], expected["tariff"])
        self.assertEqual(record["cost"]["usd"], expected["usd"])
        self.assertEqual(record["cost"]["no_cache_usd"], expected["no_cache_usd"])
        self.assertEqual(record["cost"]["saved_usd"], expected["saved_usd"])
        self.assertEqual(record["transport"], "websocket")
        self.assertIsInstance(body, str)
        self.assertNotIn("headers", json.loads(body))
        self.assertNotIn("SYNTHETIC_SECRET_DO_NOT_STORE", body)

    def test_dns_trailing_dot_is_canonicalized_for_copilot_prices(self) -> None:
        case = _load_fixture()
        flow, rid = _play_fixture_case(case, f"{case['host']}.")
        self.assertNotIn(flow.id, tap.SOCKETS)
        with store.LOCK:
            record = store.RECORDS[rid]
        self.assertEqual(record["host"], case["host"])
        self.assertEqual(record["cost"]["tariff"], "Copilot")
        self.assertEqual(record["cost"]["usd"], case["expected"]["usd"])

    def test_accepted_hosts_and_routes_are_normalized(self) -> None:
        cases = (
            (_HOST, "/responses?x=1", "/responses"),
            (_HOST, "/responses/", "/responses/"),
            ("api.githubcopilot.com", "/v1/responses?x=1", "/v1/responses"),
            ("api.githubcopilot.com", "/v1/responses/", "/v1/responses/"),
        )
        for host, path, normalized in cases:
            with self.subTest(host=host, path=path):
                flow = _flow(host=host, path=path)
                tap.websocket_start(flow)
                self.assertIn(flow.id, tap.SOCKETS)
                self.assertEqual(tap.SOCKETS[flow.id].path, normalized)
                tap.websocket_end(flow)

    def test_rejects_untrusted_host_route_status_method_and_missing_websocket(self) -> None:
        cases = (
            _flow(host="evilgithubcopilot.com"),
            _flow(host="githubcopilot.com.evil.example"),
            _flow(host="example.com"),
            _flow(path="/auto"),
            _flow(status=200),
            _flow(method="POST"),
            _flow(with_websocket=False),
        )
        for flow in cases:
            with self.subTest(url=flow.request.url, status=flow.response.status_code):
                tap.websocket_start(flow)
                self.assertNotIn(flow.id, tap.SOCKETS)
        self.assertEqual(self._record_ids(), set())

    def test_two_creates_on_one_connection_create_two_rows(self) -> None:
        flow = _flow()
        tap.websocket_start(flow)
        _send_exchange(flow, "resp-one", at=110.0)
        _send_exchange(flow, "resp-two", at=111.0)
        with store.LOCK:
            records_before_duplicate = copy.deepcopy(store.RECORDS)
            totals_before_duplicate = copy.deepcopy(store.CONV_TOTALS)
        _message(
            flow,
            from_client=False,
            payload={
                "type": "response.completed",
                "response": {
                    "id": "resp-two",
                    "model": _MODEL,
                    "usage": {"input_tokens": 12, "output_tokens": 3},
                },
            },
            timestamp=112.0,
        )
        with store.LOCK:
            self.assertEqual(store.RECORDS, records_before_duplicate)
            self.assertEqual(store.CONV_TOTALS, totals_before_duplicate)
        tap.websocket_end(flow)

        ids = self._record_ids()
        self.assertEqual(len(ids), 2)
        self.assertNotIn(flow.id, tap.SOCKETS)
        with store.LOCK:
            self.assertEqual({store.RECORDS[rid]["transport"] for rid in ids}, {"websocket"})
            self.assertFalse(store.ACTIVE_CAPTURES)

    def test_messages_are_unchanged_and_transport_headers_are_not_retained(self) -> None:
        flow = _flow()
        tap.websocket_start(flow)
        _message(
            flow,
            from_client=True,
            payload={
                "type": "response.create",
                "model": _MODEL,
                "input": "fixture input",
                "headers": {"authorization": _REQUEST_SENTINEL},
            },
            timestamp=120.0,
        )
        _message(
            flow,
            from_client=False,
            payload={"type": "response.created", "response": {"id": "resp-safe", "model": _MODEL}},
            timestamp=120.1,
        )
        _message(
            flow,
            from_client=False,
            payload={
                "type": "response.completed",
                "response": {"id": "resp-safe", "model": _MODEL},
            },
            timestamp=120.2,
        )
        tap.websocket_end(flow)

        rid = next(iter(self._record_ids()))
        with store.LOCK:
            body = store.BODIES[rid]
        self.assertIsInstance(body, str)
        self.assertNotIn("headers", json.loads(body))
        self.assertNotIn(_REQUEST_SENTINEL, body)

    def test_dropped_and_injected_messages_are_ignored_and_binary_active_fails(self) -> None:
        flow = _flow()
        tap.websocket_start(flow)
        for timestamp, dropped, injected in ((130.0, True, False), (130.1, False, True)):
            msg = _message(
                flow,
                from_client=True,
                payload={"type": "response.create", "model": _MODEL, "input": "ignored"},
                timestamp=timestamp,
                dropped=dropped,
                injected=injected,
            )
            self.assertEqual((msg.dropped, msg.injected), (dropped, injected))
        self.assertEqual(self._record_ids(), set())

        _message(
            flow,
            from_client=True,
            payload={"type": "response.create", "model": _MODEL, "input": "active"},
            timestamp=130.2,
        )
        binary = _message(
            flow,
            from_client=False,
            payload=b"\xff\xfe not utf-8",
            timestamp=130.3,
            opcode=2,
        )
        self.assertEqual(binary.content, b"\xff\xfe not utf-8")
        tap.websocket_end(flow)
        self.assertEqual(len(self._record_ids()), 1)
        with store.LOCK:
            self.assertFalse(store.ACTIVE_CAPTURES)

    def test_connections_are_independent_and_error_end_close_once(self) -> None:
        first = _flow()
        second = _flow(host="api.githubcopilot.com")
        tap.websocket_start(first)
        tap.websocket_start(second)
        _message(
            first,
            from_client=True,
            payload={"type": "response.create", "model": _MODEL, "input": "first"},
            timestamp=140.0,
        )
        _message(
            second,
            from_client=True,
            payload={"type": "response.create", "model": _MODEL, "input": "second"},
            timestamp=140.1,
        )
        first_rid, second_rid = sorted(self._record_ids())

        tap.error(first)
        tap.websocket_end(first)
        self.assertNotIn(first.id, tap.SOCKETS)
        self.assertIn(second.id, tap.SOCKETS)
        with store.LOCK:
            self.assertEqual(store.ACTIVE_CAPTURES, {second_rid})

        _message(
            second,
            from_client=False,
            payload={
                "type": "response.created",
                "response": {"id": "resp-second", "model": _MODEL},
            },
            timestamp=140.2,
        )
        _message(
            second,
            from_client=False,
            payload={
                "type": "response.completed",
                "response": {"id": "resp-second", "model": _MODEL},
            },
            timestamp=140.3,
        )
        tap.websocket_end(second)
        self.assertEqual(tap.SOCKETS, {})
        with store.LOCK:
            self.assertFalse(store.ACTIVE_CAPTURES)
            self.assertEqual(set(store.RECORDS), {first_rid, second_rid})

    def test_done_closes_websockets_before_stopping_dashboard_and_clears_http_slots(self) -> None:
        ws_flow = _flow()
        tap.websocket_start(ws_flow)
        _message(
            ws_flow,
            from_client=True,
            payload={"type": "response.create", "model": _MODEL, "input": "unfinished"},
            timestamp=150.0,
        )

        http_flow = _flow(method="POST", path="/responses", status=200)
        http_flow.request.content = json.dumps({"model": _MODEL, "input": "http"}).encode()
        tap.request(http_flow)
        tap.responseheaders(http_flow)
        self.assertIn("tap_id", http_flow.metadata)
        with store.LOCK:
            self.assertEqual(len(store.ACTIVE_CAPTURES), 2)
            websocket_rid = next(
                rid for rid in store.RECORDS if rid != http_flow.metadata["tap_id"]
            )
        http_rid = http_flow.metadata["tap_id"]

        def verify_websocket_closed_before_dashboard_stop() -> None:
            with store.LOCK:
                self.assertEqual(store.ACTIVE_CAPTURES, {http_rid})
                self.assertEqual(store.RECORDS[websocket_rid]["state"], "error")

        with patch.object(
            tap.dashboard,
            "stop",
            side_effect=verify_websocket_closed_before_dashboard_stop,
        ) as stop:
            tap.done()
        stop.assert_called_once_with()
        self.assertEqual(tap.SOCKETS, {})
        with store.LOCK:
            self.assertFalse(store.ACTIVE_CAPTURES)

    def test_http_post_capture_path_remains_enabled(self) -> None:
        flow = _flow(method="POST", path="/v1/responses", status=200)
        flow.request.content = json.dumps({"model": _MODEL, "input": "legacy HTTP"}).encode()
        tap.request(flow)
        self.assertIn("tap_id", flow.metadata)
        self.assertEqual(flow.request.headers.get("accept-encoding"), "identity")
        self.assertEqual(len(self._record_ids()), 1)


if __name__ == "__main__":
    unittest.main()
