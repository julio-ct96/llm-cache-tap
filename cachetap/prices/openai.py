"""List prices of the OpenAI models."""

from cachetap.prices import base

TARIFF = "OpenAI"
LONG_CONTEXT = 272_000


def _gpt(
    input_price: float, read: float, output: float, write: bool = False, long: bool = False
) -> base.Price:
    rates: base.Rates = {"input": input_price, "read": read, "output": output}
    if write:
        # GPT-5.6 and later bill a cache write at 1.25x the input; earlier models do not bill it
        rates["write"] = round(input_price * 1.25, 6)
    return base.long_context(rates, LONG_CONTEXT) if long else {**rates}


# Standard-tier list prices in US dollars per million tokens, from OpenAI's pricing page as of
# October 2026. Above 272K input tokens the whole request pays 2x input and cache, 1.5x output.
PRICES: dict[str, base.Price] = {
    "gpt-6-astra": _gpt(10, 1, 50, write=True, long=True),
    "gpt-6-sol": _gpt(2, 0.2, 10, write=True, long=True),
    "gpt-6-luna": _gpt(0.1, 0.01, 0.5, write=True, long=True),
    "gpt-6.1-sol": _gpt(2, 0.1, 10, write=True, long=True),
    "gpt-5.6-sol": _gpt(4, 0.4, 20, write=True, long=True),
    "gpt-5.6-terra": _gpt(2, 0.2, 12, write=True, long=True),
    "gpt-5.6-luna": _gpt(0.2, 0.02, 1.2, write=True, long=True),
    "gpt-5.5": _gpt(5, 0.5, 30, long=True),
    "gpt-5.4": _gpt(2.5, 0.25, 15, long=True),
    "gpt-5.4-mini": _gpt(0.75, 0.075, 4.5),
    "gpt-5.4-nano": _gpt(0.2, 0.02, 1.25),
    "gpt-5.3-codex": _gpt(1.75, 0.175, 14),
    "gpt-5-mini": _gpt(0.25, 0.025, 2),
    "gpt-4.1": _gpt(2, 0.5, 8),
}
