"""Price a request: what it cost, what the cache saved and what a miss wasted."""

from datetime import UTC, datetime

from cachetap import prices, record
from cachetap.prices import base

MILLION = 1_000_000


def rates_for(price: base.Price, input_total: int) -> tuple[record.CostRates, int | None]:
    """Rates this request pays, and the long-context threshold when it went over it."""
    over, long = price.get("over"), price.get("long")
    tier: base.Rates = price
    if over is not None and long is not None and input_total > over:
        tier = long
    else:
        over = None
    # a write the provider does not bill apart is plain input
    write = tier.get("write", tier["input"])
    rates: record.CostRates = {
        "input": tier["input"],
        "read": tier["read"],
        "write": write,
        "write_1h": tier.get("write_1h", write),
        "output": tier["output"],
    }
    if "write_12h" in tier:
        rates["write_12h"] = tier["write_12h"]
    return rates, over


def compute(
    usage: record.Usage, price: base.Price, tariff: str, write_1h: int = 0, *, write_12h: int = 0
) -> record.Cost:
    """Cost of a usage at a price, splitting cache writes by billed lifetime."""
    rates, over = rates_for(price, usage["input_total"])
    written = usage["write"] or 0
    write_1h = min(max(write_1h, 0), written)
    write_12h = min(max(write_12h, 0), written - write_1h) if "write_12h" in rates else 0
    write_cost = (
        (written - write_1h - write_12h) * rates["write"]
        + write_1h * rates["write_1h"]
        + write_12h * rates.get("write_12h", 0)
    )
    parts: record.CostParts = {
        "uncached": round(usage["uncached"] * rates["input"] / MILLION, 8),
        "read": round(usage["read"] * rates["read"] / MILLION, 8),
        "write": round(write_cost / MILLION, 8),
        "output": round(usage["output"] * rates["output"] / MILLION, 8),
    }
    usd = round(sum(parts.values()), 8)  # type: ignore[arg-type]
    no_cache = round(usage["input_total"] * rates["input"] / MILLION + parts["output"], 8)
    cost: record.Cost = {
        "tariff": tariff,
        "rates": rates,
        "parts": parts,
        "usd": usd,
        "no_cache_usd": no_cache,
        "saved_usd": round(no_cache - usd, 8),
    }
    if over is not None:
        cost["long_over"] = over
    if write_1h:
        cost["write_1h"] = write_1h
    if write_12h:
        cost["write_12h"] = write_12h
    if "note" in price:
        cost["note"] = price["note"]
    return cost


def lost(usage: record.Usage, previous: record.Usage, cost: record.Cost) -> float:
    """What was overpaid because the prefix of the previous request was not read from cache.

    The tokens that should have been read were billed as written or as plain input instead.
    """
    expected = min(previous["input_total"], usage["input_total"])
    shortfall = max(0, expected - usage["read"])
    written = usage["write"] or 0
    rates = cost["rates"]
    as_written = min(shortfall, written)
    as_input = min(shortfall - as_written, usage["uncached"])
    write_rate = cost["parts"]["write"] * MILLION / written if written else rates["write"]
    wasted = as_written * (write_rate - rates["read"]) + as_input * (rates["input"] - rates["read"])
    return round(max(wasted, 0) / MILLION, 8)


def price_record(
    rec: record.Record, prev: record.Record | None, write_1h: int = 0, *, write_12h: int = 0
) -> None:
    """Mutate rec by setting cost, or cost_missing when its model has no known price."""
    usage = rec.get("usage")
    if not usage:
        return
    model = rec.get("model")
    ts = rec.get("ts")
    at = datetime.fromtimestamp(ts, UTC).date() if ts is not None else None
    tariff, price = prices.lookup(rec.get("host"), model, at=at)
    if tariff is None:
        rec["cost_missing"] = f"sin tarifa conocida para {model or 'un modelo sin nombre'}"
        return
    if price is None:
        rec["cost_missing"] = f"sin precio para {model} en la tarifa de {tariff}"
        return
    cost = compute(usage, price, tariff, write_1h, write_12h=write_12h)
    previous_usage = prev.get("usage") if prev else None
    if (
        rec.get("verdict") in ("MISS", "PARTIAL")
        and previous_usage
        and not (rec.get("uncached_instructions") or (prev and prev.get("uncached_instructions")))
    ):
        wasted = lost(usage, previous_usage, cost)
        if wasted:
            cost["lost_usd"] = wasted
    rec["cost"] = cost
