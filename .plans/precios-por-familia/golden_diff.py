"""Registros del golden que cambian respecto al último commit: id, modelo y claves distintas.

Uso: venv/bin/python .plans/precios-por-familia/golden_diff.py
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = "tests/replay/golden.json"

before = json.loads(subprocess.check_output(["git", "show", f"HEAD:{GOLDEN}"], cwd=ROOT))
after = json.loads((ROOT / GOLDEN).read_text(encoding="utf-8"))
if len(before["records"]) != len(after["records"]):
    print(f"distinto número de registros: {len(before['records'])} -> {len(after['records'])}")
for old, new in zip(before["records"], after["records"], strict=False):
    if old != new:
        keys = sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))
        print(old["id"], old.get("model"), " ".join(keys))
