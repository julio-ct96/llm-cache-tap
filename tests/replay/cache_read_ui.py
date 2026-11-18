"""Synthetic records for the cache-read browser matrix, through real capture hooks."""

import json
import tempfile
from pathlib import Path

from cachetap import record, store
from tests.replay import adapter, builders, scenario
from tests.test_websocket_hooks import _load_fixture, _play_fixture_case


def _google_step(method, t, streaming):
    body = {"contents": [{"role": "user", "parts": [{"text": method}]}]}
    data = {
        "usageMetadata": {
            "promptTokenCount": 6000,
            "cachedContentTokenCount": 5000,
            "candidatesTokenCount": 10,
        },
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "respuesta"}]}}],
    }
    path = f"/v1beta/models/gemini-4-carbon:{method}"
    if streaming:
        path += "?alt=sse"
    chunk = builders.sse(data) if streaming else json.dumps(data)
    return scenario.Step(
        method, t, "generativelanguage.googleapis.com", path, body, 200, [chunk], None
    )


def _incremental_record():
    with tempfile.TemporaryDirectory(prefix="tap-c35-") as temporary:
        adapter.reset(Path(temporary) / "requests.jsonl")
        case = _load_fixture()
        case["client"]["previous_response_id"] = "resp_synthetic_previous"
        completed = next(event for event in case["server"] if event["type"] == "response.completed")
        usage = completed["response"]["usage"]
        usage.update(
            input_tokens=13847,
            input_tokens_details={"cached_tokens": 13789, "cache_write_tokens": 55},
            total_tokens=13883,
        )
        _, rid = _play_fixture_case(case, case["host"])
        with store.LOCK:
            rec = store.RECORDS[rid]
            return {"detail": record.public(rec), "light": record.light(rec)}


def fixtures():
    steps = [
        scenario.Step(
            "copilot-http",
            0,
            "api.githubcopilot.com",
            "/chat/completions",
            builders.chat_body("gemini-3.8-flash", "copilot", 1, effort="low"),
            200,
            builders.chat_sse(14399, 0),
            None,
        ),
        _google_step("generateContent", 5, streaming=False),
        _google_step("streamGenerateContent", 10, streaming=True),
    ]
    captured = scenario.run(steps)["records"]
    result = {
        step.key: {"detail": rec, "light": record.light(rec)}
        for step, rec in zip(steps, captured, strict=True)
    }
    result["copilot-incremental"] = _incremental_record()
    return result


if __name__ == "__main__":
    print(json.dumps(fixtures(), ensure_ascii=False))
