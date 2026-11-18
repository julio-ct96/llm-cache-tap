"""Huella de las tablas de precios: el contenido, sin importar el orden ni cómo se construyen.

Uso: venv/bin/python .plans/precios-por-familia/huella.py
"""

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cachetap import prices  # noqa: E402
from cachetap.prices import anthropic, copilot, google, openai  # noqa: E402


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


for tariff in (anthropic, openai, google, copilot):
    print(f"{tariff.TARIFF} {len(tariff.PRICES)} {digest(tariff.PRICES)}")
print(f"ayuda {len(prices.reference(at=date(2026, 11, 18))['prices'])}")
