"""Compare what Copilot bills (its GET /models billing data) with the Copilot price table.

Without --run it makes no request. With --run it starts the Copilot CLI behind a temporary
mitmdump that keeps only each model's billing data and answers every model call locally with
403, so it spends no AI credits. Exit code 1 when a priced model is billed differently.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cachetap import prices  # noqa: E402
from scripts import check_copilot  # noqa: E402

READY = "READY: no requests made; use --run to read Copilot's billing data"
CREDIT_USD = 0.01  # 1 AI credit
FIELDS = {
    "input_price": "input",
    "cache_read_price": "read",
    "cache_write_price": "write",
    "cache_write_1h_price": "write_1h",
    "output_price": "output",
}
RATE_KEYS = ("input", "read", "write", "write_1h", "output")
PROXY_READY_SECONDS = 10.0
CLI_TIMEOUT_SECONDS = 90.0

Billed = dict[str, object]


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _tier(raw: dict[str, object], factor: float) -> dict[str, float]:
    rates: dict[str, float] = {}
    for field, key in FIELDS.items():
        value = _number(raw.get(field))
        if value is None:
            continue
        usd = round(value * CREDIT_USD * factor, 6)
        if key == "write" and usd == 0:
            continue  # no separate write rate
        rates[key] = usd
    return rates


def unknown_fields(billing: object) -> set[str]:
    """Price fields this check does not compare yet, such as a new kind of cache write."""
    token_prices = billing.get("token_prices") if isinstance(billing, dict) else None
    found: set[str] = set()
    for tier in token_prices.values() if isinstance(token_prices, dict) else []:
        if isinstance(tier, dict):
            found |= {key for key in tier if key.endswith("_price") and key not in FIELDS}
    return found


def billed_rates(billing: object, at: datetime) -> Billed | None:
    """One model's billing entry as USD per million tokens, with any running promotion applied."""
    if not isinstance(billing, dict):
        return None
    token_prices = billing.get("token_prices")
    if not isinstance(token_prices, dict) or not isinstance(token_prices.get("default"), dict):
        return None
    batch = _number(token_prices.get("batch_size")) or 1_000_000
    factor = 1_000_000 / batch
    promo = billing.get("promo")
    if isinstance(promo, dict) and isinstance(promo.get("ends_at"), str):
        ends = datetime.fromisoformat(promo["ends_at"].replace("Z", "+00:00"))
        if at < ends:
            factor *= 1 - (_number(promo.get("discount_percent")) or 0) / 100
    default = _tier(token_prices["default"], factor)
    result: Billed = {"rates": default}
    long = token_prices.get("long_context")
    if isinstance(long, dict):
        long_rates = _tier(long, factor)
        if long_rates != default:  # a tier at the same rates changes nothing
            result["over"] = token_prices["default"].get("max_prompt_tokens")
            result["long"] = long_rates
    return result


def table_rates(model: str, at: datetime) -> Billed | None:
    """The Copilot table's price for a model, in the same shape as billed_rates."""
    _, price = prices.lookup("api.githubcopilot.com", model, at=at.date())
    if price is None:
        return None
    result: Billed = {"rates": {k: round(float(price[k]), 6) for k in RATE_KEYS if k in price}}  # type: ignore[literal-required]
    if "long" in price and "over" in price:
        long = price["long"]
        result["over"] = price["over"]
        result["long"] = {k: round(float(long[k]), 6) for k in RATE_KEYS if k in long}  # type: ignore[literal-required]
    return result


def compare(billing: dict[str, object], at: datetime) -> tuple[list[str], list[str]]:
    """Lines for priced models billed differently, and lines for billed models without a price."""
    differences: list[str] = []
    unpriced: list[str] = []
    for model in sorted(billing):
        billed = billed_rates(billing[model], at)
        if billed is None:
            continue
        unknown = unknown_fields(billing[model])
        if unknown:
            differences.append(
                f"{model}: campos de precio sin comparar: {', '.join(sorted(unknown))}"
            )
        ours = table_rates(model, at)
        if ours is None:
            unpriced.append(f"{model}: facturado {json.dumps(billed, sort_keys=True)}")
        elif ours != billed:
            differences.append(
                f"{model}: facturado {json.dumps(billed, sort_keys=True)}"
                f" · tabla {json.dumps(ours, sort_keys=True)}"
            )
    return differences, unpriced


def _wait_for_port(port: int, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + PROXY_READY_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise check_copilot.RunnerError("mitmdump exited before listening")
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise check_copilot.RunnerError("mitmdump did not start listening in time")


def read_billing(copilot_argument: str | None = None) -> dict[str, object]:
    """Run the Copilot CLI behind the blocking probe and return each model's billing data."""
    copilot = check_copilot.find_copilot(copilot_argument)
    mitmdump = ROOT / "venv" / "bin" / "mitmdump"
    if not mitmdump.is_file() or not (ROOT / "ca" / "mitmproxy-ca-cert.pem").is_file():
        raise check_copilot.RunnerError("the checkout's venv mitmdump and ca/ files are required")
    with tempfile.TemporaryDirectory(prefix="llm-cache-tap-prices-") as name:
        temporary = Path(name)
        (temporary / "workspace").mkdir()
        (temporary / "logs").mkdir()
        output = temporary / "billing.json"
        reservations, (port, _) = check_copilot.reserve_ports()
        for reservation in reservations:
            reservation.close()
        processes: list[subprocess.Popen[bytes]] = []
        try:
            proxy = subprocess.Popen(
                [str(mitmdump), "--listen-host", "127.0.0.1", "-p", str(port),
                 "--set", f"confdir={ROOT / 'ca'}", "--set", "termlog_verbosity=error",
                 "--set", "flow_detail=0", "-s", str(ROOT / "scripts" / "copilot_models_probe.py")],
                cwd=ROOT, env={**os.environ, "PROBE_OUT": str(output)},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )  # fmt: skip
            processes.append(proxy)
            _wait_for_port(port, proxy)
            cli = subprocess.Popen(
                [str(ROOT / "via.sh"), str(copilot), "--model=gpt-6-luna",
                 "--no-custom-instructions", "--no-ask-user", "--disable-builtin-mcps",
                 "--no-auto-update", "--disable-client-telemetry", "--sync-session=off",
                 "--log-level=error", f"--log-dir={temporary / 'logs'}",
                 "--deny-tool", "shell", "--deny-tool", "write", "--deny-tool", "url",
                 "--prompt", "holi"],
                cwd=temporary / "workspace",
                env={**os.environ, "TAP_PROXY_PORT": str(port), "COPILOT_OTEL_ENABLED": "false"},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )  # fmt: skip
            processes.append(cli)
            try:
                cli.wait(timeout=CLI_TIMEOUT_SECONDS)  # it fails on purpose: every call is refused
            except subprocess.TimeoutExpired:
                pass
        finally:
            for process in reversed(processes):
                check_copilot.stop_process(
                    process,
                    kill_group=os.killpg,
                    group_exists=check_copilot.process_group_exists,
                    clock=time.monotonic,
                    sleep=time.sleep,
                )
        if not output.is_file():
            raise check_copilot.RunnerError("Copilot did not request its model list")
        billing = json.loads(output.read_text(encoding="utf-8")).get("billing")
        if not isinstance(billing, dict) or not billing:
            raise check_copilot.RunnerError("Copilot's model list carried no models")
        return billing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--run", action="store_true", help="read Copilot's billing data (no model calls)"
    )
    parser.add_argument("--copilot", help="path to the Copilot CLI executable")
    arguments = parser.parse_args(argv)
    if not arguments.run:
        print(READY)
        return 0
    try:
        billing = read_billing(arguments.copilot)
    except check_copilot.RunnerError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    differences, unpriced = compare(billing, datetime.now(UTC))
    print(f"{len(billing)} modelos en la facturación de Copilot")
    for line in differences:
        print(f"DISTINTO  {line}")
    for line in unpriced:
        print(f"SIN PRECIO  {line}")
    print("precios de la tabla iguales a la facturación" if not differences else "hay diferencias")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
