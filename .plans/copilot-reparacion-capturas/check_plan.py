"""Validate the repair plan; optional checks never send inference requests."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import re
import sys
import tempfile
from pathlib import Path

PLAN = Path(__file__).resolve().parent
ROOT = PLAN.parents[1]
STATES = {"pendiente", "en curso", "terminada sin commit", "terminada con commit", "bloqueada"}
GATES = {
    "websocket": ("2.01", ("Fuentes", "Hechos", "Regla candidata", "Contraejemplos", "Decisión")),
    "uso-cli": (
        "2.02",
        (
            "Fuentes",
            "Esquema demostrado",
            "Rechazo observado",
            "Ausencias y contradicciones",
            "Decisión",
        ),
    ),
    "precios": ("2.03", ("Fuentes", "Fila y unidades", "Caché y contexto", "Vigencia", "Decisión")),
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def within(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    assert path.is_relative_to(root.resolve()) and path.is_file(), relative
    return path


def check_index() -> None:
    rows = re.findall(
        r"^\| (\d+\.\d+) \| [^|]+ \| \[[^]]+\]\(([^)]+)\) \| ([^|]+) \| ([^|]+) \|",
        (PLAN / "README.md").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert len(rows) == 9, f"Expected 9 tasks, found {len(rows)}"
    seen: set[str] = set()
    linked: set[Path] = set()
    tasks: dict[str, tuple[str, str]] = {}
    for task_id, relative, dependencies, state in rows:
        assert task_id not in seen, task_id
        path = within(PLAN, relative)
        text = path.read_text(encoding="utf-8")
        assert text.startswith(f"# {task_id} ")
        for section in (
            "**Objetivo:**",
            "**Lee:**",
            "**Puedes tocar:**",
            "## Pasos",
            "## Verificación",
        ):
            assert section in text, (relative, section)
        assert "```" not in text, relative
        assert state.strip() in STATES, task_id
        for dependency in re.findall(r"\d+\.\d+", dependencies):
            assert dependency in seen, (task_id, dependency)
        seen.add(task_id)
        linked.add(path)
        tasks[task_id] = (state.strip(), text)
    assert linked == {path.resolve() for path in PLAN.glob("fase-*/*.md")}
    for path in PLAN.rglob("*"):
        if path.suffix not in {".md", ".py", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n"), path.name
        assert "/" + "Users/" not in text, path.name
        assert all(line == line.rstrip() for line in text.splitlines()), path.name
    for name, (task_id, headings) in GATES.items():
        contract = load(PLAN / "contratos" / f"{name}.json")
        assert contract["status"] in {"pendiente", "verificado", "insuficiente"}, name
        assert type(contract["approved"]) is bool, name
        assert isinstance(contract["sources"], list), name
        assert isinstance(contract["unknowns"], list), name
        if contract["status"] != "pendiente":
            report = within(PLAN, f"contratos/{name}.md").read_text(encoding="utf-8")
            for heading in headings:
                assert f"## {heading}" in report, (name, heading)
        if tasks[task_id][0] != "bloqueada":
            assert contract["approved"], f"Unapproved task was unlocked: {task_id}"
        if contract["approved"]:
            assert contract["status"] == "verificado" and not contract["unknowns"], name
            assert contract["sources"] and contract["decision"], name
            assert "reserva bloqueada" not in tasks[task_id][1].lower(), task_id


def check_preserved() -> None:
    for relative, expected in load(PLAN / "base-ejecucion.json")["preserved_sha256"].items():
        assert hashlib.sha256(within(ROOT, relative).read_bytes()).hexdigest() == expected, relative


def check_evidence() -> None:
    base = load(PLAN / "base-ejecucion.json")
    folder = (ROOT / base["evidence_directory"]).resolve()
    assert folder.is_relative_to(ROOT)
    manifest_path = within(folder, "manifest.json")
    assert (
        hashlib.sha256(manifest_path.read_bytes()).hexdigest() == base["evidence_manifest_sha256"]
    )
    hashes = load(manifest_path)["files_sha256"]
    assert len(hashes) == 16
    for relative, expected in hashes.items():
        assert hashlib.sha256(within(folder, relative).read_bytes()).hexdigest() == expected, (
            relative
        )
    print("Evidence OK: 16 ficheros originales verificados")


def check_baseline() -> None:
    sys.path.insert(0, str(ROOT))
    from cachetap import config, prices, store, websocket
    from scripts import check_copilot as runner
    from tests.replay import adapter
    from tests.test_check_copilot import cli_usage

    manifest = load(PLAN / "casos.json")
    assert len(manifest["cases"]) == len({case["name"] for case in manifest["cases"]}) == 6
    fixture = load(within(ROOT, manifest["fixture"]))
    original_log = config.LOG
    diagnostics: dict[str, dict] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="copilot-repair-baseline-") as temporary:
            for case in manifest["cases"]:
                path = Path(temporary) / f"{case['name']}.jsonl"
                adapter.reset(path)
                session = websocket.Session(
                    fixture["host"], fixture["path"], logging.getLogger(__name__)
                )
                try:
                    for index, step in enumerate(case["steps"], start=1):
                        if step == "close":
                            session.close(float(index))
                            continue
                        if step == "create":
                            event = copy.deepcopy(fixture["client"])
                            send = session.client
                        else:
                            kind, artificial_id = step.rsplit("_", 1)
                            event = {
                                "type": "response." + kind,
                                "response": {"id": "synthetic_" + artificial_id},
                            }
                            if kind == "completed":
                                event["response"]["usage"] = copy.deepcopy(
                                    fixture["server"][-1]["response"]["usage"]
                                )
                            send = session.server
                        send(json.dumps(event).encode("utf-8"), float(index))
                    with store.LOCK:
                        rows = copy.deepcopy(list(store.RECORDS.values()))
                        assert not store.ACTIVE_CAPTURES, case["name"]
                        totals = copy.deepcopy(store.CONV_TOTALS)
                    assert len(rows) == 1, case["name"]
                    rec = rows[0]
                    assert rec["state"] == case["state"], case["name"]
                    assert rec["verdict"] == case["verdict"], case["name"]
                    if case["state"] == "error":
                        diagnostics[case["name"]] = rec["ws_diagnostic"]
                        assert [step["action"] for step in rec["ws_diagnostic"]["events"]] == case[
                            "actions"
                        ]
                        assert "usage" not in rec and "cost" not in rec and not totals
                        assert not path.exists()
                    else:
                        assert rec["usage"] == fixture["expected"]["usage"]
                        assert rec["cost"]["usd"] == fixture["expected"]["usd"]
                        assert "ws_diagnostic" not in rec
                        assert sum(total["priced"] for total in totals.values()) == 1
                        assert len(path.read_text().splitlines()) == 1
                finally:
                    session.close()
    finally:
        adapter.reset(original_log)
    assert diagnostics["other_same"] == diagnostics["other_different"]
    for missing, label in (
        ("reasoningTokens", "usage"),
        ("cache_write", "tokenDetails"),
        ("tokenDetails", None),
    ):
        value = cli_usage()
        row = next(iter(value["modelMetrics"].values()))
        del (row if label is None else row[label])[missing]
        try:
            runner.decode_cli_usage(value)
        except runner.RunnerError:
            pass
        else:
            raise AssertionError(f"Synthetic missing field was accepted: {missing}")
    assert prices.lookup("api.githubcopilot.com", "gemini-4-argon") == ("Copilot", None)
    print("Baseline OK: 6 secuencias WebSocket; 3 variantes CLI rechazadas")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--evidence", action="store_true")
    parser.add_argument("--gate", choices=("websocket", "uso-cli", "precios"))
    args = parser.parse_args()
    check_index()
    check_preserved()
    print("Plan OK: 9 tareas; invariantes preservadas")
    if args.baseline:
        check_baseline()
    if args.evidence:
        check_evidence()
    if args.gate:
        approved = load(PLAN / "contratos" / f"{args.gate}.json")["approved"]
        print(f"Gate {args.gate}: {'APPROVED' if approved else 'BLOCKED'}")
        return 0 if approved else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
