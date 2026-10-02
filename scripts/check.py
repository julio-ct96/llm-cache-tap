"""Run the project's local quality checks in a single, reproducible order."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / "venv" / "bin" / "python"


def _checks() -> list[list[str]]:
    js_tests = sorted((ROOT / "tests" / "ui" / "unit").glob("*.test.mjs"))
    return [
        [sys.executable, "-m", "ruff", "check", "tap.py", "cachetap"],
        [sys.executable, "-m", "ruff", "format", "--check", "tap.py", "cachetap"],
        [sys.executable, "-m", "mypy"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"],
        ["node", "--test", *(str(path.relative_to(ROOT)) for path in js_tests)],
    ]


def _local_network_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("NO_PROXY", "no_proxy"):
        entries = [item.strip() for item in env.get(key, "").split(",") if item.strip()]
        for host in ("localhost", "127.0.0.1", "::1"):
            if host not in entries:
                entries.append(host)
        env[key] = ",".join(entries)
    return env


def run_checks(full: bool = False, runner: Callable[..., object] = subprocess.run) -> None:
    """Run quality checks, optionally including the Chrome-driven UI suite."""
    checks = _checks()
    for command in checks:
        runner(command, check=True, cwd=ROOT)

    if full:
        if not VENV_PYTHON.is_file():
            raise FileNotFoundError(
                f"{VENV_PYTHON} is required for the UI checks; create the project venv first"
            )
        runner(
            ["node", "tests/ui/check.mjs", "--full"],
            check=True,
            cwd=ROOT,
            env=_local_network_env(),
        )


def main() -> int:
    full = "--full" in sys.argv[1:]
    try:
        run_checks(full=full)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        return error.returncode or 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
