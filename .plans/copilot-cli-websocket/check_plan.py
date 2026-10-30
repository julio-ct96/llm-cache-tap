"""Validate the task index and reproduce the payload's existing HTTP analysis."""

import json
import re
import sys
from pathlib import Path

PLAN = Path(__file__).resolve().parent
ROOT = PLAN.parents[1]


def check_index():
    text = (PLAN / "README.md").read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| (\d+\.\d+) \| [^|]+ \| \[[^]]+\]\(([^)]+)\) \| ([^|]+) \| ([^|]+) \|",
        text,
        re.MULTILINE,
    )
    assert len(rows) == 12, f"Expected 12 tasks, found {len(rows)}"
    seen = set()
    linked = set()
    statuses = {
        "pendiente", "en curso", "terminada sin commit", "terminada con commit", "bloqueada"
    }
    for task_id, relative, dependencies, status in rows:
        assert task_id not in seen, f"Duplicate task: {task_id}"
        path = (PLAN / relative).resolve()
        assert path.is_relative_to(PLAN), f"External task link: {relative}"
        assert path.is_file(), f"Missing task: {relative}"
        task = path.read_text(encoding="utf-8")
        assert task.startswith(f"# {task_id} "), f"Wrong task ID: {relative}"
        for section in ("**Objetivo:**", "**Lee:**", "**Puedes tocar:**", "## Pasos", "## Verificación"):
            assert section in task, f"Missing {section}: {relative}"
        for dependency in re.findall(r"\d+\.\d+", dependencies):
            assert dependency in seen, f"Missing or unordered dependency {dependency}: {task_id}"
        assert status.strip() in statuses, f"Unknown status: {task_id}"
        assert "```" not in task, f"Code block in task: {relative}"
        assert "/Users/" not in task, f"Personal path: {relative}"
        seen.add(task_id)
        linked.add(path)
    actual = {path.resolve() for path in PLAN.glob("fase-*/*.md")}
    assert linked == actual, f"Unindexed or missing tasks: {linked ^ actual}"
    for path in PLAN.rglob("*"):
        if path.suffix not in {".md", ".py", ".json"}:
            continue
        content = path.read_text(encoding="utf-8")
        assert content.endswith("\n"), f"Missing final newline: {path.name}"
        for number, line in enumerate(content.splitlines(), 1):
            assert line == line.rstrip(), f"Trailing whitespace: {path.name}:{number}"


def check_case():
    sys.path.insert(0, str(ROOT))
    from cachetap import providers, response_body
    from tests.replay import builders, scenario

    case = json.loads((PLAN / "caso.json").read_text(encoding="utf-8"))
    request = {key: value for key, value in case["client"].items() if key not in {"type", "headers"}}
    chunks = [builders.sse(event) for event in case["server"]]
    expected = case["expected"]
    usage = providers.normalize(response_body.usage_events("".join(chunks)))
    assert usage == expected["usage"], (usage, expected["usage"])
    result = scenario.run([
        scenario.Step(
            key="COPILOT-WS-PAYLOAD", t=0, host=case["host"], path=case["path"],
            body=request, status=200, chunks=chunks, expect=expected["verdict"],
        )
    ])
    assert len(result["records"]) == 1
    rec = result["records"][0]
    for key in ("model", "usage", "output", "verdict", "ttl_s"):
        assert rec[key] == expected[key], (key, rec[key], expected[key])
    for key in ("tariff", "usd", "no_cache_usd", "saved_usd"):
        assert rec["cost"][key] == expected[key], (key, rec["cost"][key], expected[key])
    assert [segment["name"] for segment in rec["segs"]] == ["msg0:system", "msg1:user"]
    assert "SYNTHETIC_SECRET_DO_NOT_STORE" not in json.dumps(result)


def main():
    check_index()
    check_case()
    print("Plan OK: 12 tareas; enlaces, dependencias y caso verificado")


if __name__ == "__main__":
    main()
