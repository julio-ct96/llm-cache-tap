import copy
import unittest

from cachetap import record


class RecordTest(unittest.TestCase):
    def test_heavy_fields(self):
        self.assertEqual(
            record.HEAVY,
            ("segs", "raw_usage", "output", "effort_fields", "resp_headers", "diff"),
        )

    def test_light_drops_heavy_and_private(self):
        rec = {"id": 1, "segs": [], "_msgs": [], "model": "m"}
        self.assertEqual(record.light(rec), {"id": 1, "model": "m"})

    def test_public_drops_private_only(self):
        rec = {"id": 1, "segs": [], "_msgs": []}
        self.assertEqual(record.public(rec), {"id": 1, "segs": []})

    def test_do_not_mutate_input(self):
        rec = {"id": 1, "segs": [], "_msgs": [], "model": "m"}
        original = copy.deepcopy(rec)
        record.light(rec)
        record.public(rec)
        self.assertEqual(rec, original)


if __name__ == "__main__":
    unittest.main()
