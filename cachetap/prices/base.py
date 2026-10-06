"""The shape of a price and the name a model has in the price tables."""

import re
from typing import NotRequired, Required, TypedDict


class Rates(TypedDict):
    """US dollars per million tokens."""

    input: Required[float]  # input not served from cache
    read: Required[float]  # input read from cache
    output: Required[float]  # output, reasoning included
    write: NotRequired[float]  # cache write; absent when the provider does not bill it
    write_1h: NotRequired[float]  # cache write kept for one hour


class Price(Rates):
    over: NotRequired[int]  # input tokens above which the whole request pays `long`
    long: NotRequired[Rates]  # long-context rates
    note: NotRequired[str]  # why the price is what it is, when it needs saying


def canonical(model: str) -> str:
    """Name a model the way the price tables do: "claude-haiku-4-5-20251001" -> "claude-haiku-4.5"."""
    name = re.sub(r"-(\d{8}|\d{4}-\d{2}-\d{2})$", "", (model or "").strip().lower())
    return re.sub(r"(?<=\d)-(\d{1,2})(?!\d)", r".\1", name)


def long_context(rates: Rates, over: int, output_factor: float = 1.5) -> Price:
    """Add the long-context tier: input and cache rates double, output grows by output_factor."""
    long: Rates = {
        "input": round(rates["input"] * 2, 6),
        "read": round(rates["read"] * 2, 6),
        "output": round(rates["output"] * output_factor, 6),
    }
    if "write" in rates:
        long["write"] = round(rates["write"] * 2, 6)
    if "write_1h" in rates:
        long["write_1h"] = round(rates["write_1h"] * 2, 6)
    return {**rates, "over": over, "long": long}
