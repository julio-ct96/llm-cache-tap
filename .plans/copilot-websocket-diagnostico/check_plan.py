"""Check this diagnostic plan and its baseline scenarios without provider calls."""

from __future__ import annotations

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
STATES = {
    "pendiente",
    "en curso",
    "terminada sin commit",
    "terminada con commit",
    "bloqueada",
}


def check_index() -> None:
    text = (PLAN / "README.md").read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| (\d+\.\d+) \| [^|]+ \| \[[^]]+\]\(([^)]+)\) \| ([^|]+) \| ([^|]+) \|",
        text,
        re.MULTILINE,
    )
    assert len(rows) == 5, f"Expected 5 tasks, found {len(rows)}"
    seen: set[str] = set()
    linked: set[Path] = set()
    for task_id, relative, dependencies, state in rows:
        assert task_id not in seen, f"Duplicate task: {task_id}"
        path = (PLAN / relative).resolve()
        assert path.is_relative_to(PLAN) and path.is_file(), f"Invalid task: {relative}"
        task = path.read_text(encoding="utf-8")
        assert task.startswith(f"# {task_id} "), f"Wrong task ID: {relative}"
        for section in (
            "**Objetivo:**",
            "**Lee:**",
            "**Puedes tocar:**",
            "## Pasos",
            "## Verificación",
        ):
            assert section in task, f"Missing {section}: {relative}"
        assert state.strip() in STATES, f"Unknown state: {task_id}"
        for dependency in re.findall(r"\d+\.\d+", dependencies):
            assert dependency in seen, f"Missing or unordered dependency: {dependency}"
        assert "```" not in task, f"Code block in task: {relative}"
        seen.add(task_id)
        linked.add(path)
    assert linked == {path.resolve() for path in PLAN.glob("fase-*/*.md")}
    for path in PLAN.rglob("*"):
        if path.suffix not in {".md", ".py", ".json"}:
            continue
        content = path.read_text(encoding="utf-8")
        assert content.endswith("\n"), f"Missing final newline: {path.name}"
        assert "/" + "Users/" not in content, f"Personal path: {path.name}"
        for number, line in enumerate(content.splitlines(), 1):
            assert line == line.rstrip(), f"Trailing whitespace: {path.name}:{number}"
    report = PLAN / "resultado.md"
    if report.exists():
        content = report.read_text(encoding="utf-8")
        for title in (
            "Hechos reales",
            "Matriz offline",
            "Privacidad y límites",
            "Verificaciones",
            "Incertidumbres",
            "Siguiente decisión",
        ):
            assert f"## {title}" in content, f"Missing report section: {title}"
        assert "causa real indeterminada" in content


def check_preserved() -> None:
    baseline = json.loads((PLAN / "base-ejecucion.json").read_text(encoding="utf-8"))
    for relative, expected in baseline["preserved_sha256"].items():
        path = (ROOT / relative).resolve()
        assert path.is_relative_to(ROOT), f"External invariant path: {relative}"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, relative


def check_cases() -> None:
    sys.path.insert(0, str(ROOT))
    from cachetap import config, store, websocket
    from tests.replay import adapter

    manifest = json.loads((PLAN / "casos.json").read_text(encoding="utf-8"))
    fixture_path = (ROOT / manifest["fixture"]).resolve()
    assert fixture_path.is_relative_to(ROOT)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = manifest["cases"]
    assert len(cases) == 7
    assert len({case["name"] for case in cases}) == 7

    original_log = config.LOG
    try:
        with tempfile.TemporaryDirectory(prefix="ws-diagnostic-plan-") as temporary:
            for case in cases:
                # Only a child test process's in-memory state and temporary log.
                adapter.reset(Path(temporary) / "requests.jsonl")
                session = websocket.Session(
                    fixture["host"], fixture["path"], logging.getLogger("diagnostic-plan")
                )
                try:
                    for index, step in enumerate(case["steps"]):
                        at = 100.0 + index
                        if step == "close":
                            session.close(at)
                            continue
                        if step in {"create", "create_generate_false"}:
                            event = copy.deepcopy(fixture["client"])
                            if step == "create_generate_false":
                                event["generate"] = False
                            send = session.client
                        elif step in {"created", "completed", "wrong_completed"}:
                            event = copy.deepcopy(fixture["server"][0 if step == "created" else -1])
                            if step == "wrong_completed":
                                event["response"]["id"] = "synthetic-other"
                            send = session.server
                        else:
                            raise AssertionError(f"Unknown synthetic step: {step}")
                        send(json.dumps(event, separators=(",", ":")).encode("utf-8"), at)

                    with store.LOCK:
                        rows = copy.deepcopy(list(store.RECORDS.values()))
                        reserved = len(store.ACTIVE_CAPTURES)
                        totals = copy.deepcopy(store.CONV_TOTALS)
                    assert [row.get("state") for row in rows] == case["states"], case["name"]
                    assert [row.get("verdict") for row in rows] == case["verdicts"], case["name"]
                    assert reserved == case["reserved"], case["name"]
                    assert session._disabled == case["disabled"], case["name"]
                    if case["error_note"] is not None:
                        assert len(rows) == 1 and rows[0]["notes"] == [case["error_note"]]
                        assert "usage" not in rows[0] and "cost" not in rows[0]
                        assert totals == {}
                    if case["name"] == "generate_false_then_create":
                        request = copy.deepcopy(fixture["client"])
                        request["generate"] = False
                        decoded = websocket.decode_client(json.dumps(request).encode("utf-8"))
                        assert decoded is not None and "generate" not in decoded
                finally:
                    session.close()
                    with store.LOCK:
                        assert not store.ACTIVE_CAPTURES
    finally:
        adapter.reset(original_log)


def main() -> None:
    check_index()
    check_preserved()
    check_cases()
    print("Plan OK: 5 tareas; 7 casos offline; invariantes preservadas")


if __name__ == "__main__":
    main()
