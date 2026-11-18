"""What GitHub Copilot charges for the models it serves, whoever made them."""

from datetime import date

from cachetap.prices import anthropic, base, google, openai

TARIFF = "Copilot"
HOST = "githubcopilot.com"


def serves(host: str) -> bool:
    return host == HOST or host.endswith("." + HOST)


def _single_write(rates: base.Rates) -> base.Rates:
    # GitHub publishes a single cache write rate per model, with no separate 1 hour rate
    single: base.Rates = {"input": rates["input"], "read": rates["read"], "output": rates["output"]}
    if "write" in rates:
        single["write"] = rates["write"]
    return single


def _one_write_rate(price: base.Price) -> base.Price:
    rates: base.Price = {**_single_write(price)}
    if "over" in price and "long" in price:
        # a long-context tier, such as Claude Haiku 5.5's over 100K, keeps its threshold
        rates["over"], rates["long"] = price["over"], _single_write(price["long"])
    return rates


def _without_12h(price: base.Price) -> base.Price:
    rates = price.copy()
    rates.pop("write_12h", None)
    if "long" in rates:
        rates["long"] = rates["long"].copy()
        rates["long"].pop("write_12h", None)
    return rates


_UTILITY: base.Price = {
    "input": 0,
    "read": 0,
    "output": 0,
    "note": "modelo utilitario de Copilot: no consume créditos",
}


def _grok(read: float) -> base.Price:
    return base.long_context({"input": 2, "read": read, "output": 6}, 200_000, output_factor=2)


# US dollars per million tokens; see https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing
# Copilot bills tokens at each vendor's list price (1 AI credit = 0.01 USD), so the Claude and
# GPT rows are the vendors' own; what follows them is what differs or what only GitHub lists.
FROM_LISTS: dict[str, base.Price] = {
    **{model: _one_write_rate(price) for model, price in anthropic.PRICES.items()},
    **{model: _without_12h(price) for model, price in openai.PRICES.items()},
}

DIFFERENT_TIERS: dict[str, base.Price] = {
    # GitHub starts this model's long-context tier at 200K input tokens, OpenAI at 272K
    "gpt-5.6-luna": {**openai.PRICES["gpt-5.6-luna"], "over": 200_000},
}

UTILITY_MODELS: dict[str, base.Price] = {
    # session titles and commit messages: not billed and absent from usage reports
    "gpt-4.1": _UTILITY,
    "gpt-4o": _UTILITY,
    "gpt-4o-mini": _UTILITY,
}

GEMINI: dict[str, base.Price] = {
    "gemini-3.5-flash": {"input": 1.5, "read": 0.15, "output": 9},
    # Promo rates as published; do not assume future Copilot rates match the Gemini API.
    "gemini-3.6-flash": {"input": 0.75, "read": 0.075, "output": 3.75},
    "gemini-3.7-flash": {"input": 0.75, "read": 0.075, "output": 3.75},
    "gemini-3.8-flash": {"input": 0.75, "read": 0.075, "output": 3.75},
    "gemini-4-argon": google.FRONTIER_PROMO,
    "gemini-4-carbon": google.FRONTIER_PROMO,
    "gemini-4-hydrogen": google.HYDROGEN,
}

GROK: dict[str, base.Price] = {
    "grok-4.5": _grok(0.5),
    "grok-4.6": _grok(0.5),
    "grok-4.7": _grok(0.5),
}

KIMI: dict[str, base.Price] = {
    "kimi-k3": {"input": 3, "read": 0.3, "output": 15},
    "kimi-k2.7-code": {"input": 0.95, "read": 0.19, "output": 4},
}

MAI: dict[str, base.Price] = {
    "mai-code-1.1-flash": {"input": 0.2, "read": 0.02, "output": 1.2},
}

PRICES: dict[str, base.Price] = {
    **FROM_LISTS,
    **DIFFERENT_TIERS,
    **UTILITY_MODELS,
    **GEMINI,
    **GROK,
    **KIMI,
    **MAI,
}

AFTER_PROMO: dict[str, tuple[date, base.Price | None]] = {
    # GitHub publishes Carbon's post-promo rate, but not Argon's or Flash's.
    "gemini-4-argon": (google.FRONTIER_CHANGE, None),
    "gemini-4-carbon": (google.FRONTIER_CHANGE, google.FRONTIER_STANDARD),
    "gemini-3.8-flash": (google.FLASH_CHANGE, None),
}
