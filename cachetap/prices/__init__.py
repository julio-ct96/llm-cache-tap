"""Which price table bills a request, and the tables themselves for the dashboard help."""

from typing import TypedDict

from cachetap import providers
from cachetap.prices import anthropic, base, copilot, openai

# date on which the price pages of GitHub, Anthropic and OpenAI were last reviewed
REVIEWED = "octubre de 2026"

# the price tables, in the order the help shows them
TARIFFS = (copilot, anthropic, openai)

# list prices, by the provider that owns the model
LIST = ((providers.anthropic, anthropic), (providers.openai, openai))


class HelpRow(TypedDict):
    tariff: str
    model: str
    price: base.Price


class Reference(TypedDict):
    prices: list[HelpRow]
    prices_reviewed: str


def reference() -> Reference:
    """Every price of every table, for the dashboard help."""
    rows: list[HelpRow] = [
        {"tariff": tariff.TARIFF, "model": model, "price": price}
        for tariff in TARIFFS
        for model, price in tariff.PRICES.items()
    ]
    return {"prices": rows, "prices_reviewed": REVIEWED}


def lookup(host: str | None, model: str | None) -> tuple[str | None, base.Price | None]:
    """The price table that bills this request and the row of its model, when either is known.

    What goes through Copilot pays Copilot's prices; anything else pays the list price of the
    provider that owns the model.
    """
    name = base.canonical(str(model or ""))
    if copilot.serves(str(host or "").lower()):
        return copilot.TARIFF, copilot.PRICES.get(name)
    for provider, tariff in LIST:
        if provider.owns(name):
            return tariff.TARIFF, tariff.PRICES.get(name)
    return None, None
