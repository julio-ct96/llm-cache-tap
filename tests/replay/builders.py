import json

SYSTEMS = {
    "S1": "Eres un asistente de pruebas.",
    "S2": "Eres un asistente de pruebas. Responde breve.",
}

RESPONSE_HEADERS = {
    "request-id": "req",
    "anthropic-ratelimit-requests-remaining": "99",
    "anthropic-ratelimit-tokens-remaining": "1000",
    "set-cookie": "a=b",
    "cf-ray": "x",
    "via": "1.1 proxy",
    "content-type": "text/event-stream",
}


def turns(conv, n):
    messages = []
    for i in range(1, n + 1):
        messages.append({"role": "user", "content": f"{conv} pregunta {i}"})
        if i != n:
            messages.append({"role": "assistant", "content": f"{conv} respuesta {i}"})
    return messages


def claude_body(model, conv, n, system="S1", tools=True, effort=None, thinking=False,
                system_ttl=None, mark_last=False, messages=None):
    cc = {"type": "ephemeral"}
    if system_ttl is not None:
        cc["ttl"] = system_ttl
    body = {"model": model, "max_tokens": 1024, "stream": True}
    if tools:
        body["tools"] = [
            {"name": "read_file", "description": "Lee un fichero", "input_schema": {"type": "object"}},
            {"name": "run", "description": "Ejecuta un comando", "input_schema": {"type": "object"}},
        ]
    body["system"] = [{"type": "text", "text": SYSTEMS[system], "cache_control": cc}]
    body["messages"] = messages if messages is not None else turns(conv, n)
    if effort is not None:
        body["output_config"] = {"effort": effort}
    if thinking:
        body["thinking"] = {"type": "enabled", "budget_tokens": 2000}
    if mark_last:
        last = body["messages"][-1]
        last["content"] = [{"type": "text", "text": last["content"],
                            "cache_control": {"type": "ephemeral"}}]
    return body


def responses_body(model, conv, n, effort=None, cache_options=False, raw_input=None):
    if raw_input is not None:
        return {"model": model, "stream": True, "input": raw_input}
    body = {
        "model": model,
        "stream": True,
        "instructions": "Eres un asistente.",
        "tools": [{"type": "function", "name": "read_file"}],
        "input": turns(conv, n),
    }
    if effort is not None:
        body["reasoning"] = {"effort": effort}
    if cache_options:
        body["prompt_cache_options"] = {"ttl": "30m"}
    return body


def chat_body(model, conv, n, system="S1", effort=None, retention=None, stream=True):
    body = {
        "model": model,
        "stream": stream,
        "tools": [{"type": "function", "function": {"name": "read_file"}}],
        "messages": [{"role": "system", "content": SYSTEMS[system]}] + turns(conv, n),
    }
    if effort is not None:
        body["reasoning_effort"] = effort
    if retention is not None:
        body["prompt_cache_retention"] = retention
    return body


def sse(*events):
    out = ""
    for event in events:
        if not isinstance(event, str):
            event = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        out += "data: " + event + "\n\n"
    return out


def anthropic_sse(read, write, inp, creation=None):
    usage = {
        "input_tokens": inp,
        "cache_creation_input_tokens": write,
        "cache_read_input_tokens": read,
        "output_tokens": 1,
    }
    if creation is not None:
        usage["cache_creation"] = {
            "ephemeral_5m_input_tokens": creation[0],
            "ephemeral_1h_input_tokens": creation[1],
        }
    return [
        sse({"type": "message_start", "message": {"usage": usage}}),
        sse(
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hola"}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": " mundo"}},
        ),
        sse(
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 50}},
            {"type": "message_stop"},
        ),
    ]


def responses_sse(inp, cached):
    return [
        sse({"type": "response.created", "response": {"id": "resp_1", "reasoning": {"effort": "medium"}}}),
        sse(
            {"type": "response.output_text.delta", "delta": "Hola"},
            {"type": "response.output_text.delta", "delta": " mundo"},
        ),
        sse({"type": "response.completed", "response": {"usage": {
            "input_tokens": inp,
            "input_tokens_details": {"cached_tokens": cached},
            "output_tokens": 80,
            "output_tokens_details": {"reasoning_tokens": 30},
        }}}),
    ]


def chat_sse(inp, cached):
    chunk = "chat.completion.chunk"
    return [
        sse({"object": chunk, "choices": [{"delta": {"role": "assistant"}}]}),
        sse(
            {"object": chunk, "choices": [{"delta": {"content": "Hola"}}]},
            {"object": chunk, "choices": [{"delta": {"content": " mundo"}}]},
        ),
        sse(
            {"object": chunk, "choices": [{"delta": {}, "finish_reason": "stop"}]},
            {"object": chunk, "choices": [], "usage": {
                "prompt_tokens": inp,
                "prompt_tokens_details": {"cached_tokens": cached},
                "completion_tokens": 40,
                "completion_tokens_details": {"reasoning_tokens": 5},
            }},
            "[DONE]",
        ),
    ]


def _compact(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def anthropic_json(read, write, inp):
    return [_compact({
        "type": "message",
        "content": [{"type": "text", "text": "Hola"}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": inp,
            "cache_creation_input_tokens": write,
            "cache_read_input_tokens": read,
            "output_tokens": 50,
        },
    })]


def chat_json(inp, cached):
    return [_compact({
        "object": "chat.completion",
        "choices": [{"message": {"content": "Hola"}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": inp,
            "prompt_tokens_details": {"cached_tokens": cached},
            "completion_tokens": 40,
        },
    })]
