"""What GitHub Copilot charges for the models it serves, whoever made them."""

from datetime import date

from cachetap.prices import anthropic, base, google, openai

TARIFF = "Copilot"
HOST = "githubcopilot.com"
# Copilot's billing data ends the MAI Code 2 launch promotion at 2027-05-18T00:00Z
MAI_CHANGE = date(2027, 5, 18)


def serves(host: str) -> bool:
    return host == HOST or host.endswith("." + HOST)


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
    # Copilot's billing data (GET /models) prices Claude at the list rates, 1 h cache writes
    # included, although the public pricing page shows a single write rate
    **anthropic.PRICES,
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

# fast mode is a separate model that only GitHub prices
CLAUDE_FAST: dict[str, base.Price] = {
    "claude-opus-4.8-fast": {"input": 10, "read": 1, "write": 12.5, "output": 50},
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
    # the billing data lists a cache write rate the public page omits
    "mai-code-1.1-flash": {"input": 0.2, "read": 0.02, "write": 0.25, "output": 1.2},
    # launch promotion; GitHub lists no cache write for Microsoft models
    "mai-code-2": {"input": 0.5, "read": 0.025, "output": 2.5},
    "mai-code-2-flash": {"input": 0.05, "read": 0.005, "output": 0.25},
}

PRICES: dict[str, base.Price] = {
    **FROM_LISTS,
    **DIFFERENT_TIERS,
    **UTILITY_MODELS,
    **CLAUDE_FAST,
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
    "mai-code-2": (MAI_CHANGE, {"input": 1, "read": 0.05, "output": 5}),
    "mai-code-2-flash": (MAI_CHANGE, {"input": 0.1, "read": 0.01, "output": 0.5}),
}
