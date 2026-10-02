import unittest

from cachetap import verdict

BASE_REC = {
    "model": "claude-opus-5-5",
    "effort": None,
    "prev_effort": None,
    "effort_changed": False,
    "model_changed": False,
    "params_changed": False,
    "prefix_intact": True,
    "diverge_at": None,
    "gap_s": 58.0,
    "age_s": 60.0,
    "prev_id": 3,
}
BASE_PREV = {
    "id": 3,
    "state": "done",
    "status": 200,
    "ttl_s": 300,
    "ttl_anchor": "start",
    "ttl_source": "por defecto de Claude",
    "usage": {"input_total": 3000},
}


def U(read, total):
    return {"read": read, "write": 0, "uncached": total - read, "input_total": total, "output": 1, "reasoning": None}


class JudgeTest(unittest.TestCase):
    def run_judge(self, rec_changes, prev_changes=None, prev=True):
        rec = {**BASE_REC, **rec_changes}
        previous = {**BASE_PREV, **(prev_changes or {})} if prev else None
        verdict.judge(rec, previous)
        return rec

    def check(self, rec, expected_verdict, notes, server_side):
        self.assertEqual(rec["verdict"], expected_verdict)
        self.assertEqual(rec["notes"], notes)
        if server_side is not None:
            self.assertIs(rec["server_side"], server_side)

    def test_without_usage(self):
        rec = self.run_judge({}, prev=False)
        self.check(rec, "N/A", ["la respuesta no trae usage"], None)

    def test_below_minimum(self):
        rec = self.run_judge({"usage": U(0, 600), "model": "claude-opus-4-7"}, prev=False)
        self.check(rec, "N/A", ["menos de 2048 tokens de entrada: por debajo del mínimo cacheable de este modelo"], False)

    def test_cold_first_request(self):
        rec = self.run_judge({"usage": U(0, 3020), "prev_id": None}, prev=False)
        self.check(rec, "COLD", ["primera petición de esta conversación"], False)

    def test_hit_first_request_from_other_conversation(self):
        rec = self.run_judge({"usage": U(2000, 2100), "prev_id": None}, prev=False)
        self.check(
            rec,
            "HIT",
            ["primera petición de esta conversación", "parte del prefijo ya estaba en caché de otra conversación"],
            False,
        )

    def test_clean_hit(self):
        rec = self.run_judge({"usage": U(3000, 3200)})
        self.check(rec, "HIT", [], False)

    def test_hit_despite_effort_change(self):
        rec = self.run_judge({"usage": U(3000, 3200), "effort_changed": True, "effort": "high"})
        self.check(rec, "HIT", ["hit pese al cambio de esfuerzo (None → high)"], False)

    def test_hit_with_modified_prefix(self):
        rec = self.run_judge({"usage": U(3000, 3200), "prefix_intact": False, "diverge_at": "system"})
        self.check(
            rec,
            "HIT",
            ["el cliente modificó el prefijo en system; el hit viene de una variante ya cacheada"],
            False,
        )

    def test_partial_without_client_cause(self):
        rec = self.run_judge({"usage": U(1000, 3200)})
        self.check(rec, "PARTIAL", ["sin causa en el cliente: mismo prefijo, mismo esfuerzo, 58.0 s desde #3"], True)

    def test_miss_ttl_expired_from_start(self):
        rec = self.run_judge({"usage": U(0, 3200), "age_s": 400.0})
        self.check(rec, "MISS", ["pasaron 400 s desde el inicio de #3 (TTL 300 s, por defecto de Claude)"], False)

    def test_miss_ttl_expired_from_end(self):
        rec = self.run_judge({"usage": U(0, 3200), "age_s": 400.0}, {"ttl_anchor": "end"})
        self.check(rec, "MISS", ["pasaron 400 s desde el final de #3 (TTL 300 s, por defecto de Claude)"], False)

    def test_miss_previous_failed(self):
        rec = self.run_judge({"usage": U(0, 3200)}, {"status": 529})
        self.check(rec, "MISS", ["la petición anterior (#3) no terminó bien"], False)

    def test_miss_modified_prefix(self):
        rec = self.run_judge({"usage": U(0, 3200), "prefix_intact": False, "diverge_at": "system"})
        self.check(rec, "MISS", ["el cliente modificó el prefijo en system"], False)

    def test_miss_model_and_params_changed(self):
        rec = self.run_judge(
            {
                "usage": U(0, 3200),
                "model_changed": True,
                "prev_model": "a",
                "model": "claude-sonnet-5-5",
                "params_changed": True,
            }
        )
        self.check(rec, "MISS", ["cambió el modelo (a → claude-sonnet-5-5)", "cambiaron thinking/tool_choice"], False)

    def test_hit_when_previous_has_no_usage(self):
        prev = {k: v for k, v in BASE_PREV.items() if k != "usage"}
        rec = {**BASE_REC, "usage": U(2900, 3200)}
        verdict.judge(rec, prev)
        self.check(rec, "HIT", [], False)


if __name__ == "__main__":
    unittest.main()
