from tests.replay import builders
from tests.replay.step import Step

ANT = "api.anthropic.com"
OAI = "api.openai.com"
MIS = "api.mistral.ai"
MSG = "/v1/messages?beta=true"
OP = "claude-opus-5-5"

Q1_MESSAGES = [
    {"role": "user", "content": "Q pregunta 1"},
    {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "pienso"},
        {"type": "tool_use", "id": "t1", "name": "run", "input": {"cmd": "ls"}},
    ]},
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]},
    {"type": "document", "name": "doc.pdf"},
    {"type": "image", "source": {"kind": "none"}},
]

STEPS = [
    Step("M1", 20000, MIS, "/v1/chat/completions", builders.chat_body("mistral-large", "M", 1),
         200, builders.chat_sse(1500, 0), "COLD"),
    Step("M2", 20400, MIS, "/v1/chat/completions", builders.chat_body("mistral-large", "M", 2),
         200, builders.chat_sse(1600, 0), "MISS"),
    Step("N1", 20500, ANT, "/v1/messages", "esto no es JSON",
         200, [builders.sse({"type": "ping"}) + 'data: {"usage" roto\n\n'], "N/A"),
    Step("Q1", 20600, ANT, MSG, builders.claude_body(OP, "Q", 1, messages=Q1_MESSAGES),
         200, builders.anthropic_sse(0, 0, 600), "COLD"),
    Step("R1", 20700, OAI, "/v1/responses",
         builders.responses_body("gpt-5.6", "R", 1, raw_input=["R texto suelto", 42]),
         200, builders.responses_sse(1100, 0), "COLD"),
    Step("R2", 20800, ANT, MSG, builders.claude_body(OP, "R2", 1),
         500, ["{no es json"], "N/A"),
    Step("O1", 21000, ANT, "/v1/messages", builders.claude_body(OP, "Z", 1),
         200, builders.anthropic_sse(0, 0, 10), None, "GET"),
    Step("O2", 21010, ANT, "/v1/models", builders.claude_body(OP, "Z", 1),
         200, builders.anthropic_sse(0, 0, 10), None),
    Step("O3", 21020, ANT, "/v1/messages/count_tokens", builders.claude_body(OP, "Z", 1),
         200, builders.anthropic_sse(0, 0, 10), None),
    Step("O4", 21100, ANT, "/v1/messages", builders.claude_body(OP, "Z", 1),
         200, None, None, "GET"),
]
