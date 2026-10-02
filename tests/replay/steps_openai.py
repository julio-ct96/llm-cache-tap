from tests.replay import builders
from tests.replay.step import Step

HOST = "api.openai.com"
RSP = "/v1/responses"
CHT = "/v1/chat/completions"

STEPS = [
    Step("F1", 10000, HOST, RSP,
         builders.responses_body("gpt-5.6", "F", 1, effort="medium", cache_options=True),
         200, builders.responses_sse(4000, 0), "COLD"),
    Step("F2", 10120, HOST, RSP,
         builders.responses_body("gpt-5.6", "F", 2, effort="high", cache_options=True),
         200, builders.responses_sse(4200, 3900), "HIT"),
    Step("F3", 12200, HOST, RSP,
         builders.responses_body("gpt-5.6", "F", 3, effort="high", cache_options=True),
         200, builders.responses_sse(4400, 0), "MISS"),
    Step("G1", 12300, HOST, RSP,
         builders.responses_body("gpt-5.6", "G", 1, raw_input="G pregunta suelta"),
         200, builders.responses_sse(500, 0), "N/A"),
    Step("H1", 12400, HOST, CHT,
         builders.chat_body("gpt-5.2", "H", 1, effort="low"),
         200, builders.chat_sse(2000, 0), "COLD"),
    Step("H2", 12460, HOST, CHT,
         builders.chat_body("gpt-5.2", "H", 2, effort="low", system="S2"),
         200, builders.chat_sse(2100, 0), "MISS"),
    Step("H3", 12520, HOST, CHT,
         builders.chat_body("gpt-5.2", "H", 3, effort="low", system="S2"),
         200, builders.chat_sse(2200, 1024), "PARTIAL"),
    Step("I1", 12600, HOST, CHT,
         builders.chat_body("gpt-4.1", "I", 1, retention="24h", stream=False),
         200, builders.chat_json(1500, 0), "COLD"),
    Step("I2", 12660, HOST, CHT,
         builders.chat_body("gpt-4.1", "I", 2, retention="in_memory", stream=False),
         200, builders.chat_json(1600, 1400), "HIT"),
    Step("J1", 12700, HOST, CHT,
         builders.chat_body("gpt-4o", "J", 1),
         200, builders.chat_sse(1200, 0), "COLD"),
    Step("K1", 12800, HOST, RSP,
         builders.responses_body("o3-mini", "K", 1),
         200, builders.responses_sse(1100, 0), "COLD"),
    Step("L1", 12900, HOST, CHT,
         builders.chat_body("gpt-5-2025-08-07", "L", 1),
         200, builders.chat_sse(1300, 0), "COLD"),
]
