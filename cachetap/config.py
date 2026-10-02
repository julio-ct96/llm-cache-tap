"""Paths, ports and limits of the addon."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOG = DATA / "requests.jsonl"
UI = ROOT / "ui"
UI_PORT = int(os.environ.get("TAP_UI_PORT", "8900"))
# TAP_TTL_S forces one TTL for every request; without it the TTL is worked out per request.
TTL_FORCED = int(os.environ.get("TAP_TTL_S") or 0) or None
TTL_S = TTL_FORCED or 300
MAX = 300
