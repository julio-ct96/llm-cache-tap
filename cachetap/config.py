"""Paths, ports and limits of the addon."""

import os
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent
DATA: Path = ROOT / "data"
LOG: Path = DATA / "requests.jsonl"
UI: Path = ROOT / "ui"
UI_PORT: int = int(os.environ.get("TAP_UI_PORT", "8900"))
# TAP_TTL_S forces one TTL for every request; without it the TTL is worked out per request.
TTL_FORCED: int | None = int(os.environ.get("TAP_TTL_S") or 0) or None
TTL_S: int = TTL_FORCED or 300
MAX: int = 300
MAX_REQUEST_BYTES: int = 4 * 1024 * 1024
MAX_BODY_BYTES: int = 64 * 1024 * 1024
MAX_RESPONSE_BYTES: int = 8 * 1024 * 1024
MAX_ACTIVE_CAPTURES: int = 16
MAX_CLIENT_EVENTS: int = 512
