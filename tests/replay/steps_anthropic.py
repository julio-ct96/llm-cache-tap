import json

from tests.replay import builders
from tests.replay.step import Step

HOST = "api.anthropic.com"
PATH = "/v1/messages?beta=true"

OP = "claude-opus-5-5"
SO = "claude-sonnet-5-5"
O47 = "claude-opus-4-7"
X = {"system": "S2", "tools": False, "thinking": True, "effort": "low"}

OVERLOADED = json.dumps(
    {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
    separators=(",", ":"),
    ensure_ascii=False,
)


def _step(key, t, model, conv, n, status, chunks, expect, **extra):
    return Step(key, t, HOST, PATH, builders.claude_body(model, conv, n, **extra), status, chunks, expect)


STEPS = [
    _step("A1", 0, OP, "A", 1, 200, builders.anthropic_sse(0, 3000, 20), "COLD"),
    _step("A2", 60, OP, "A", 2, 200, builders.anthropic_sse(3000, 200, 20), "HIT"),
    _step("A3", 120, OP, "A", 3, 200, builders.anthropic_sse(3200, 200, 20), "HIT", effort="high"),
    _step("A4", 180, OP, "A", 4, 200, builders.anthropic_sse(1000, 2600, 20), "PARTIAL", effort="high"),
    _step("A5", 580, OP, "A", 5, 200, builders.anthropic_sse(0, 3800, 20), "MISS", effort="high"),
    _step("A6", 640, OP, "A", 6, 200, builders.anthropic_sse(0, 4000, 20), "MISS", effort="high", system="S2"),
    _step("A7", 700, OP, "A", 7, 200, builders.anthropic_sse(3700, 300, 20), "HIT",
          effort="high", system="S2", tools=False),
    _step("A8", 760, SO, "A", 8, 200, builders.anthropic_sse(0, 4100, 20), "MISS", **X),
    _step("A9", 820, SO, "A", 9, 529, [OVERLOADED], "N/A", **X),
    _step("A10", 880, SO, "A", 10, 200, builders.anthropic_sse(0, 4300, 20), "MISS", **X),
    _step("A11", 940, SO, "A", 11, 200, None, "ERR", **X),
    _step("A12", 1000, SO, "A", 12, 200, builders.anthropic_sse(4400, 100, 20), "HIT", **X),
    _step("B1", 1100, O47, "B", 1, 200, builders.anthropic_sse(0, 5000, 10, (0, 5000)), "COLD", system_ttl="1h"),
    _step("B2", 2100, O47, "B", 2, 200, builders.anthropic_sse(5000, 100, 10, (0, 100)), "HIT", system_ttl="1h"),
    _step("B3", 2160, O47, "B", 3, 200, builders.anthropic_sse(5100, 50, 10, (50, 0)), "HIT",
          system_ttl="1h", mark_last=True),
    _step("C1", 2300, "claude-haiku-4-5", "C", 1, 200, builders.anthropic_sse(0, 0, 3000), "N/A"),
    _step("C2", 2360, "claude-haiku-4-5", "C", 2, 200, builders.anthropic_sse(0, 0, 3100), "N/A"),
    _step("D1", 2400, "claude-fable-5-1", "D1", 1, 200, builders.anthropic_sse(0, 0, 600), "COLD"),
    _step("D2", 2410, "claude-mythos-preview", "D2", 1, 200, builders.anthropic_sse(0, 0, 600), "N/A"),
    _step("D3", 2420, "claude-opus-4-6", "D3", 1, 200, builders.anthropic_sse(0, 0, 600), "N/A"),
    _step("D4", 2430, "claude-sonnet-4-5", "D4", 1, 200, builders.anthropic_sse(0, 0, 600), "N/A"),
    _step("D5", 2440, "claude-3-5-haiku-20241022", "D5", 1, 200, builders.anthropic_sse(0, 0, 600), "N/A"),
    _step("D6", 2450, "claude-sonnet-4-5", "D6", 1, 200, builders.anthropic_sse(0, 0, 1500), "COLD"),
    _step("D7", 2460, O47, "D7", 1, 200, builders.anthropic_sse(0, 0, 1500), "N/A"),
    _step("E1", 2500, OP, "E", 1, 200, builders.anthropic_sse(2000, 80, 20), "HIT"),
    _step("P1", 2600, OP, "P", 1, 200, builders.anthropic_json(0, 2000, 10), "COLD"),
]
