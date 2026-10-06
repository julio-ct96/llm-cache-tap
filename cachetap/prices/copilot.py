"""What GitHub Copilot charges for the models it serves, whoever made them."""

from cachetap.prices import anthropic, base, openai

TARIFF = "Copilot"
HOST = "githubcopilot.com"


def serves(host: str) -> bool:
    return host == HOST or host.endswith("." + HOST)


def _one_write_rate(price: base.Price) -> base.Price:
    # GitHub publishes a single cache write rate per model, with no separate 1 hour rate
    rates: base.Price = {"input": price["input"], "read": price["read"], "output": price["output"]}
    if "write" in price:
        rates["write"] = price["write"]
    return rates


_UTILITY: base.Price = {
    "input": 0,
    "read": 0,
    "output": 0,
    "note": "modelo utilitario de Copilot: no consume créditos",
}


def _grok(read: float) -> base.Price:
    return base.long_context({"input": 2, "read": read, "output": 6}, 200_000, output_factor=2)


# US dollars per million tokens, from GitHub's "Models and pricing" page as of October 2026.
# Copilot bills tokens at each vendor's list price (1 AI credit = 0.01 USD), so the Claude and
# GPT rows are the vendors' own; what follows them is what differs or what only GitHub lists.
PRICES: dict[str, base.Price] = {
    **{model: _one_write_rate(price) for model, price in anthropic.PRICES.items()},
    **openai.PRICES,
    # GitHub starts this model's long-context tier at 200K input tokens, OpenAI at 272K
    "gpt-5.6-luna": {**openai.PRICES["gpt-5.6-luna"], "over": 200_000},
    # session titles and commit messages: not billed and absent from usage reports
    "gpt-4.1": _UTILITY,
    "gpt-4o": _UTILITY,
    "gpt-4o-mini": _UTILITY,
    "gemini-3.5-flash": {"input": 1.5, "read": 0.15, "output": 9},
    # promotional prices until 2026-12-31; they double afterwards
    "gemini-3.6-flash": {"input": 0.75, "read": 0.075, "output": 3.75},
    "gemini-3.7-flash": {"input": 0.75, "read": 0.075, "output": 3.75},
    "gemini-3.8-flash": {"input": 0.75, "read": 0.075, "output": 3.75},
    "grok-4.5": _grok(0.5),
    "grok-4.6": _grok(0.5),
    "grok-4.7": _grok(0.5),
    "kimi-k3": {"input": 3, "read": 0.3, "output": 15},
    "kimi-k2.7-code": {"input": 0.95, "read": 0.19, "output": 4},
    "mai-code-1.1-flash": {"input": 0.2, "read": 0.02, "output": 1.2},
}
