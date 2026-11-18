"""List prices of the Claude models."""

from cachetap.prices import base

TARIFF = "Anthropic"


def _claude(input_price: float, read: float) -> base.Price:
    # a cache write costs 1.25x the input for 5 minutes and 2x for 1 hour; output costs 5x
    return {
        "input": input_price,
        "read": read,
        "write": round(input_price * 1.25, 6),
        "write_1h": round(input_price * 2, 6),
        "output": round(input_price * 5, 6),
    }


def _family(family: str, versions: dict[str, base.Price]) -> dict[str, base.Price]:
    """Prefix each version with its family to build the full model names."""
    return {f"claude-{family}-{version}": price for version, price in versions.items()}


# List prices in US dollars per million tokens, from Anthropic's pricing page as of November 2026.
# Every model except Claude Haiku 5.5 bills the whole 1M window at the same rates.
FABLE: dict[str, base.Price] = _family(
    "fable", {"5.2": _claude(8, 0.2), "5.1": _claude(10, 0.25), "5": _claude(10, 1)}
)
MYTHOS: dict[str, base.Price] = _family(
    "mythos", {"5.2": _claude(8, 0.2), "5.1": _claude(10, 0.25), "5": _claude(10, 1)}
)
OPUS: dict[str, base.Price] = _family(
    "opus",
    {
        "5.5": _claude(4, 0.2),
        "5": _claude(5, 0.5),
        "4.8": _claude(5, 0.5),
        "4.7": _claude(5, 0.5),
        "4.6": _claude(5, 0.5),
        "4.5": _claude(5, 0.5),
        "4.1": _claude(15, 1.5),
        "4": _claude(15, 1.5),
    },
)
SONNET: dict[str, base.Price] = _family(
    "sonnet",
    {
        "5.5": _claude(2, 0.1),
        "5": _claude(2, 0.2),
        "4.6": _claude(3, 0.3),
        "4.5": _claude(3, 0.3),
        "4": _claude(3, 0.3),
    },
)
# Only Claude Haiku 5.5 has a long-context tier: a prompt over 100K tokens (cache reads and
# writes included) pays 5x on every rate.
HAIKU: dict[str, base.Price] = _family(
    "haiku",
    {
        "5.5": {**_claude(0.1, 0.01), "over": 100_000, "long": _claude(0.5, 0.05)},
        "4.5": _claude(1, 0.1),
    },
)

PRICES: dict[str, base.Price] = {**FABLE, **MYTHOS, **OPUS, **SONNET, **HAIKU}
