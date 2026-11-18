"""List prices of the OpenAI models."""

from cachetap.prices import base

TARIFF = "OpenAI"
LONG_CONTEXT = 272_000


def _gpt(
    input_price: float,
    read: float,
    output: float,
    write: bool = False,
    long: bool = False,
) -> base.Price:
    rates: base.Rates = {"input": input_price, "read": read, "output": output}
    if write:
        # GPT-5.6 and later bill a 30 min cache write at 1.25x the input and, in the Responses
        # API, a 12 h write at 2.5x; earlier models do not bill writes
        rates["write"] = round(input_price * 1.25, 6)
        rates["write_12h"] = round(input_price * 2.5, 6)
    return base.long_context(rates, LONG_CONTEXT) if long else {**rates}


def _release(
    release: str,
    models: dict[str, tuple[float, float, float]],
    *,
    write: bool = False,
    long: bool = False,
) -> dict[str, base.Price]:
    """Price every model of one release, keyed by the release name plus its suffix."""
    return {
        release if suffix == "" else f"{release}-{suffix}": _gpt(
            input_price, read, output, write=write, long=long
        )
        for suffix, (input_price, read, output) in models.items()
    }


def _without_cached_input(input_price: float, output: float, *, long: bool = False) -> base.Price:
    """Price a Pro model, which publishes no cached-input rate, billing reads as input."""
    return {
        **_gpt(input_price, input_price, output, long=long),
        "note": "sin precio de caché publicado: la lectura se cobra como entrada",
    }


# Standard-tier list prices in US dollars per million tokens, from OpenAI's pricing page as of
# November 2026 (https://developers.openai.com/api/docs/pricing).

# GPT-6.2: 30 min and 12 h cache writes, long-context tier
GPT_6_2: dict[str, base.Price] = _release(
    "gpt-6.2", {"astra": (8, 0.4, 40), "sol": (2, 0.1, 10)}, write=True, long=True
)
# GPT-6.1: 30 min and 12 h cache writes, long-context tier
GPT_6_1: dict[str, base.Price] = _release(
    "gpt-6.1", {"sol": (2, 0.1, 10), "terra": (1, 0.05, 5)}, write=True, long=True
)
# GPT-6: 30 min and 12 h cache writes, long-context tier
GPT_6: dict[str, base.Price] = _release(
    "gpt-6",
    {"astra": (10, 1, 50), "sol": (2, 0.2, 10), "luna": (0.1, 0.01, 0.5)},
    write=True,
    long=True,
)
# GPT-5.6: 30 min and 12 h cache writes, long-context tier
GPT_5_6: dict[str, base.Price] = _release(
    "gpt-5.6",
    {"sol": (4, 0.4, 20), "terra": (2, 0.2, 12), "luna": (0.2, 0.02, 1.2)},
    write=True,
    long=True,
)
# GPT-5.5: no billed writes, long-context tier
GPT_5_5: dict[str, base.Price] = {
    **_release("gpt-5.5", {"": (5, 0.5, 30)}, long=True),
    "gpt-5.5-pro": _without_cached_input(30, 180, long=True),
}
# GPT-5.4: long-context tier on the full model only; mini and nano have a single tier
GPT_5_4: dict[str, base.Price] = {
    **_release("gpt-5.4", {"": (2.5, 0.25, 15)}, long=True),
    **_release("gpt-5.4", {"mini": (0.75, 0.075, 4.5), "nano": (0.2, 0.02, 1.25)}),
    "gpt-5.4-pro": _without_cached_input(30, 180, long=True),
}
# GPT-5.3: no billed writes, single tier
GPT_5_3: dict[str, base.Price] = _release("gpt-5.3", {"codex": (1.75, 0.175, 14)})
# GPT-5.2: no billed writes, single tier; Pro has no cached-input price
GPT_5_2: dict[str, base.Price] = {
    **_release("gpt-5.2", {"": (1.75, 0.175, 14)}),
    "gpt-5.2-pro": _without_cached_input(21, 168),
}
# GPT-5.1: no billed writes, single tier
GPT_5_1: dict[str, base.Price] = _release("gpt-5.1", {"": (1.25, 0.125, 10)})
# GPT-5: no billed writes, single tier; Pro has no cached-input price
GPT_5: dict[str, base.Price] = {
    **_release(
        "gpt-5",
        {"": (1.25, 0.125, 10), "mini": (0.25, 0.025, 2), "nano": (0.05, 0.005, 0.4)},
    ),
    "gpt-5-pro": _without_cached_input(15, 120),
}
# GPT-4.1: no billed writes, single tier
GPT_4_1: dict[str, base.Price] = _release("gpt-4.1", {"": (2, 0.5, 8), "mini": (0.4, 0.1, 1.6)})
# GPT-4o: no billed writes, single tier
GPT_4O: dict[str, base.Price] = _release(
    "gpt-4o", {"": (2.5, 1.25, 10), "mini": (0.15, 0.075, 0.6)}
)
# o3: no billed writes, single tier; Pro has no cached-input price
O3: dict[str, base.Price] = {
    **_release("o3", {"": (2, 0.5, 8)}),
    "o3-pro": _without_cached_input(20, 80),
}

# Above 272K input tokens the whole request pays 2x input and cache, 1.5x output.
PRICES: dict[str, base.Price] = {
    **GPT_6_2,
    **GPT_6_1,
    **GPT_6,
    **GPT_5_6,
    **GPT_5_5,
    **GPT_5_4,
    **GPT_5_3,
    **GPT_5_2,
    **GPT_5_1,
    **GPT_5,
    **GPT_4_1,
    **GPT_4O,
    **O3,
}
