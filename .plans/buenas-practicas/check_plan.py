"""Validate task links, dependency order and mandatory task sections."""

import re
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    index = (root / "README.md").read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| (\d+\.\d+[a-z]?) \| [^|]+ \| \[[^]]+\]\(([^)]+)\) \| ([^|]+) \|",
        index,
        re.MULTILINE,
    )
    seen = set()
    linked = set()
    for task_id, relative, dependencies in rows:
        assert task_id not in seen, f"Duplicate task {task_id}"
        path = root / relative
        assert path.is_file(), f"Missing task file: {relative}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith(f"# {task_id} "), f"Wrong task ID in {relative}"
        for section in ("**Objetivo:**", "**Lee:**", "**Puedes tocar:**", "## Pasos", "## Verificación"):
            assert section in text, f"Missing {section} in {relative}"
        for dependency in re.findall(r"\d+\.\d+[a-z]?", dependencies):
            assert dependency in seen, f"Unknown or unordered dependency {dependency} in {task_id}"
        assert "```" not in text, f"Code example in {relative}"
        assert "/Users/" not in text, f"Machine-specific path in {relative}"
        seen.add(task_id)
        linked.add(path.resolve())
    actual = {path.resolve() for path in root.glob("fase-*/*.md")}
    assert linked == actual, f"Unindexed or missing tasks: {linked ^ actual}"
    assert len(rows) == 21, f"Expected 21 tasks, found {len(rows)}"
    for path in root.rglob("*"):
        if path.suffix not in (".md", ".py"):
            continue
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n"), f"Missing final newline in {path.name}"
        for number, line in enumerate(text.splitlines(), 1):
            assert line == line.rstrip(), f"Trailing whitespace in {path.name}:{number}"
    print(f"Plan OK: {len(rows)} tasks, links and dependencies valid")


if __name__ == "__main__":
    main()
