import unittest

from cachetap import segments


class StripTest(unittest.TestCase):
    def test_strip(self):
        self.assertEqual(
            segments.strip_cache_control({"a": [{"cache_control": 1, "b": 2}], "cache_control": 3}),
            {"a": [{"b": 2}]},
        )


class DumpTest(unittest.TestCase):
    def test_dump(self):
        self.assertEqual(segments.dump({"b": 1, "a": "ñ"}), '{"a": "ñ", "b": 1}')


class DigestTest(unittest.TestCase):
    def test_digest(self):
        self.assertRegex(segments.digest({"x": 1}), r"^[0-9a-f]{10}$")
        self.assertEqual(segments.digest({"x": 1, "cache_control": {}}), segments.digest({"x": 1}))
        self.assertNotEqual(segments.digest({"x": 1}), segments.digest({"x": 2}))


class PreviewTest(unittest.TestCase):
    def test_text(self):
        self.assertEqual(segments.preview("a   b\n c"), "a b c")
        self.assertEqual(len(segments.preview("x" * 200)), 140)

    def test_blocks(self):
        self.assertEqual(segments.preview({"type": "tool_use", "name": "run"}), "[tool_use run]")
        self.assertEqual(segments.preview({"type": "tool_result", "content": "ok"}), "[tool_result] ok")
        self.assertEqual(segments.preview({"type": "thinking"}), "[thinking]")
        self.assertEqual(segments.preview({"type": "document", "name": "doc.pdf"}), "[document doc.pdf]")
        self.assertEqual(segments.preview(42), "42")

    def test_message(self):
        self.assertEqual(segments.preview({"role": "user", "content": "hola"}), "hola")


class SegObjsTest(unittest.TestCase):
    def test_order(self):
        req = {
            "tools": [{"name": "t"}],
            "system": "s",
            "messages": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
        }
        names = [n for n, _, _ in segments.segment_objects(req)]
        self.assertEqual(names, ["tools", "system", "msg0:user", "msg1:assistant"])

    def test_formats(self):
        names = [n for n, _, _ in segments.segment_objects({"instructions": "x", "input": "hola"})]
        self.assertEqual(names, ["system", "msg0:text"])

    def test_tool_names(self):
        tools = [
            {"name": "named"},
            {"function": {"name": "function-named"}},
            {"type": "computer"},
            {},
            "ignored",
        ]
        self.assertEqual(
            segments.segment_objects({"tools": tools})[0][2],
            "5 tools: named, function-named, computer, ?",
        )


class SegmentsTest(unittest.TestCase):
    def test_cc(self):
        req = {
            "system": [{"type": "text", "text": "s", "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": "hola"}],
        }
        segs = segments.segments(req)
        self.assertTrue(segs[0]["cc"])
        self.assertFalse(segs[1]["cc"])
        for s in segs:
            self.assertEqual(set(s), {"name", "hash", "bytes", "cc", "preview"})


class FirstDiffTest(unittest.TestCase):
    def test_no_body(self):
        self.assertIsNone(segments.first_diff(None, "system", {"system": "a"}))

    def test_broken_body(self):
        self.assertIsNone(segments.first_diff("no json", "system", {"system": "a"}))

    def test_missing_segment(self):
        self.assertIsNone(segments.first_diff('{"system": "a"}', "tools", {"system": "a"}))

    def test_change(self):
        self.assertEqual(
            segments.first_diff('{"system": "abc"}', "system", {"system": "abd"}),
            {"segment": "system", "offset": 3, "before": '"abc"', "after": '"abd"'},
        )


if __name__ == "__main__":
    unittest.main()
