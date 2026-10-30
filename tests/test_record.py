import copy
import unittest

from cachetap import record


class RecordTest(unittest.TestCase):
    def test_segment_required_and_optional_keys(self):
        self.assertEqual(
            record.Segment.__required_keys__,
            {"name", "hash", "bytes", "cc", "preview"},
        )
        self.assertEqual(record.Segment.__optional_keys__, {"same"})

    def test_diff_and_usage_fields_are_required(self):
        self.assertEqual(record.Diff.__required_keys__, {"segment", "offset", "before", "after"})
        self.assertEqual(record.Diff.__optional_keys__, set())
        self.assertEqual(
            record.Usage.__required_keys__,
            {"read", "write", "uncached", "input_total", "output", "reasoning"},
        )
        self.assertEqual(record.Usage.__optional_keys__, set())

    def test_record_requires_only_id(self):
        self.assertEqual(record.Record.__required_keys__, {"id"})
        self.assertEqual(
            record.Record.__optional_keys__, set(record.Record.__annotations__) - {"id"}
        )
        self.assertIn("transport", record.Record.__optional_keys__)
        self.assertIn("context_partial", record.Record.__optional_keys__)

    def test_cache_ttl_and_usage_event_contracts(self):
        self.assertEqual(record.CacheTTL.__required_keys__, {"ttl_s", "ttl_source", "ttl_anchor"})
        self.assertEqual(record.CacheTTL.__optional_keys__, {"ttl_max_s"})
        self.assertEqual(record.UsageEvent.__required_keys__, {"event", "usage"})
        self.assertEqual(record.UsageEvent.__optional_keys__, set())

    def test_websocket_diagnostic_contract(self):
        self.assertEqual(
            record.WebSocketDiagnosticStep.__required_keys__,
            {"direction", "event", "action", "identified", "id_relation"},
        )
        self.assertEqual(
            record.WebSocketDiagnosticStep.__optional_keys__, {"generate", "incremental"}
        )
        self.assertEqual(
            record.WebSocketDiagnostic.__required_keys__,
            {"events", "truncated", "omitted_server_events"},
        )
        self.assertEqual(record.WebSocketDiagnostic.__optional_keys__, set())

    def test_heavy_fields(self):
        self.assertEqual(
            record.HEAVY,
            (
                "segs",
                "raw_usage",
                "output",
                "effort_fields",
                "resp_headers",
                "diff",
                "ws_diagnostic",
            ),
        )

    def test_light_drops_heavy_and_private(self):
        rec = {
            "id": 1,
            "segs": [],
            "_msgs": [],
            "model": "m",
            "ws_diagnostic": {"events": [], "truncated": False, "omitted_server_events": 0},
        }
        self.assertEqual(record.light(rec), {"id": 1, "model": "m"})

    def test_public_drops_private_only(self):
        diagnostic = {"events": [], "truncated": False, "omitted_server_events": 0}
        rec = {"id": 1, "segs": [], "_msgs": [], "ws_diagnostic": diagnostic}
        self.assertEqual(record.public(rec), {"id": 1, "segs": [], "ws_diagnostic": diagnostic})

    def test_do_not_mutate_input(self):
        rec = {
            "id": 1,
            "segs": [],
            "_msgs": [],
            "model": "m",
            "ws_diagnostic": {
                "events": [
                    {
                        "direction": "client",
                        "event": "response.create",
                        "action": "start",
                        "identified": False,
                        "id_relation": "missing",
                    }
                ],
                "truncated": False,
                "omitted_server_events": 0,
            },
        }
        original = copy.deepcopy(rec)
        record.light(rec)
        record.public(rec)
        self.assertEqual(rec, original)


if __name__ == "__main__":
    unittest.main()
