"""Which price table bills a request, and the tables themselves for the dashboard help."""

from datetime import UTC, date, datetime
from typing import TypedDict

from cachetap import providers
from cachetap.prices import anthropic, base, copilot, google, openai

# Last update to the price tables.
REVIEWED = "noviembre de 2026"

# the price tables, in the order the help shows them
TARIFFS = (copilot, anthropic, openai, google)
PROMOTIONS = {copilot.TARIFF: copilot.AFTER_PROMO, google.TARIFF: google.AFTER_PROMO}

# list prices, by the provider that owns the model
LIST = ((providers.anthropic, anthropic), (providers.openai, openai))


class HelpRow(TypedDict):
    tariff: str
    model: str
    price: base.Price


class Reference(TypedDict):
    prices: list[HelpRow]
    prices_reviewed: str


def _price(tariff: str, table: dict[str, base.Price], model: str, at: date) -> base.Price | None:
    change = PROMOTIONS.get(tariff, {}).get(model)
    if change:
        starts, next_price = change
        if at >= starts:
            return next_price
        return {**table[model], "note": f"promoción hasta {starts:%d/%m/%Y} (no incluido)"}
    return table.get(model)


def reference(*, at: date | None = None) -> Reference:
    """Every price of every table, for the dashboard help."""
    at = at or datetime.now(UTC).date()
    rows: list[HelpRow] = [
        {"tariff": tariff.TARIFF, "model": model, "price": price}
        for tariff in TARIFFS
        for model in tariff.PRICES
        if (price := _price(tariff.TARIFF, tariff.PRICES, model, at)) is not None
    ]
    return {"prices": rows, "prices_reviewed": REVIEWED}


def lookup(
    host: str | None, model: str | None, *, at: date | None = None
) -> tuple[str | None, base.Price | None]:
    """The price table that bills this request and the row of its model, when either is known.

    What goes through Copilot pays Copilot's prices; anything else pays the list price of the
    provider that owns the model. Gemini Developer API rates only apply on its own host;
    they are not Vertex AI or Antigravity rates.
    """
    name = base.canonical(str(model or ""))
    host = (host or "").lower().rstrip(".")
    at = at or datetime.now(UTC).date()
    if copilot.serves(host):
        return copilot.TARIFF, _price(copilot.TARIFF, copilot.PRICES, name, at)
    if host == providers.google.HOST and providers.google.owns(name):
        return google.TARIFF, _price(google.TARIFF, google.PRICES, name, at)
    for provider, tariff in LIST:
        if provider.owns(name):
            return tariff.TARIFF, tariff.PRICES.get(name)
    return None, None
