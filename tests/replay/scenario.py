import json
import os
import queue
import tempfile
import time
from pathlib import Path
from unittest import mock

from tests.replay import adapter, builders, flows
from tests.replay import steps_anthropic, steps_misc, steps_openai
from tests.replay.step import Step  # noqa: F401  (re-exported for callers)

BASE_TS = 1790000000.0

def all_steps():
    return steps_anthropic.STEPS + steps_openai.STEPS + steps_misc.STEPS


def _body_text(body):
    if isinstance(body, str):
        return body
    return json.dumps(body, ensure_ascii=False)


def _play(hooks, step, base_ts, clock):
    T = base_ts + step.t
    flow = flows.FakeFlow(flows.FakeRequest(step.method, step.host, step.path, _body_text(step.body), T))
    hooks.request(flow)
    if step.chunks is None:
        clock[0] = T + 1.0
        flow.error = "connection reset"
        hooks.error(flow)
        return
    flow.response = flows.FakeResponse(step.status, builders.RESPONSE_HEADERS, T + 0.3)
    hooks.responseheaders(flow)
    if flow.response.stream is not None:
        offsets = [0.5, 0.8]
        for i, chunk in enumerate(step.chunks):
            clock[0] = T + (offsets[i] if i < 2 else 1.9)
            flow.response.stream(chunk.encode("utf-8"))
    clock[0] = T + 2.0
    hooks.response(flow)


def run(steps, base_ts=BASE_TS):
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "requests.jsonl"
            adapter.reset(log_path)
            q = adapter.subscribe()
            clock = [base_ts]
            hooks = adapter.hooks()
            with mock.patch("time.time", lambda: clock[0]):
                for step in steps:
                    _play(hooks, step, base_ts, clock)
            events = []
            while True:
                try:
                    events.append(q.get_nowait())
                except queue.Empty:
                    break
            log_lines = []
            if log_path.exists():
                log_lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            return {
                "events": events,
                "records": adapter.records(),
                "body_ids": adapter.body_ids(),
                "log_lines": log_lines,
            }
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()
