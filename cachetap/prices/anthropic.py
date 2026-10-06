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


# List prices in US dollars per million tokens, from Anthropic's pricing page as of October 2026.
# No model here has a long-context tier: the whole 1M window is billed at the same rates.
PRICES: dict[str, base.Price] = {
    "claude-fable-5.1": _claude(10, 0.25),
    "claude-fable-5": _claude(10, 1),
    "claude-opus-5.5": _claude(4, 0.2),
    "claude-opus-5": _claude(5, 0.5),
    "claude-opus-4.8": _claude(5, 0.5),
    "claude-opus-4.7": _claude(5, 0.5),
    "claude-sonnet-5.5": _claude(2, 0.2),
    "claude-sonnet-5": _claude(2, 0.2),
    "claude-sonnet-4.6": _claude(3, 0.3),
    "claude-haiku-4.5": _claude(1, 0.1),
}
