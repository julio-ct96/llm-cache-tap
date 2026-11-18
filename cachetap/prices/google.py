"""Standard paid-tier token prices of the Gemini Developer API."""

from datetime import date

from cachetap.prices import base

TARIFF = "Google"

# https://ai.google.dev/gemini-api/docs/pricing
FRONTIER_PROMO: base.Price = {"input": 2, "read": 0.1, "output": 10}
FRONTIER_STANDARD: base.Price = {"input": 4, "read": 0.2, "output": 20}
HYDROGEN: base.Price = {"input": 1.5, "read": 0.075, "output": 7.5}
FLASH_PROMO: base.Price = {"input": 0.75, "read": 0.075, "output": 3.75}
FLASH_STANDARD: base.Price = {"input": 1.5, "read": 0.15, "output": 7.5}
FRONTIER_CHANGE = date(2026, 12, 1)
FLASH_CHANGE = date(2027, 1, 1)

PRICES: dict[str, base.Price] = {
    "gemini-4-argon": FRONTIER_PROMO,
    "gemini-4-carbon": FRONTIER_PROMO,
    "gemini-4-hydrogen": HYDROGEN,
    "gemini-3.8-flash": FLASH_PROMO,
    "gemini-3.6-flash": FLASH_PROMO,
    "gemini-3.5-flash-lite": {"input": 0.3, "read": 0.03, "output": 2.5},
}

AFTER_PROMO: dict[str, tuple[date, base.Price | None]] = {
    "gemini-4-argon": (FRONTIER_CHANGE, FRONTIER_STANDARD),
    "gemini-4-carbon": (FRONTIER_CHANGE, FRONTIER_STANDARD),
    "gemini-3.8-flash": (FLASH_CHANGE, FLASH_STANDARD),
    "gemini-3.6-flash": (FLASH_CHANGE, FLASH_STANDARD),
}
