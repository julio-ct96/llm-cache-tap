"""mitmproxy addon: live prompt-cache inspector for LLM calls.

Captures every POST to */messages, */responses or */chat/completions that goes
through the proxy, and serves a live dashboard on http://127.0.0.1:8900.

Privacy: request headers are never read or stored (that is where the auth token
lives). Request bodies are kept in memory only (last MAX requests) so the UI can
show them; data/requests.jsonl only stores metrics.
"""

import json
import queue
import re
import sys
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if __name__.startswith("__mitmproxy_script__"):
    # mitmproxy re-executes this file on save; dropping cachetap modules reloads submodules too.
    for _name in [m for m in sys.modules if m == "cachetap" or m.startswith("cachetap.")]:
        del sys.modules[_name]

from cachetap import config, record, segments
from cachetap.providers import anthropic, base

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".woff2": "font/woff2",
}
LLM_PATHS = ("/messages", "/responses", "/chat/completions")
FIRST_TOKEN = (b"content_block_delta", b"output_text.delta", b'"delta":{"content"', b"reasoning")
STATIC_SEG = re.compile(r"^(tools|system)$|:(system|developer)$")
SAFE_HEADER = re.compile(r"request-id|region|geo|served|backend|azure|ratelimit|quota|processing|x-cache|via$", re.I)
UNSAFE_HEADER = re.compile(r"token|auth|cookie|secret|key", re.I)

LOCK = threading.Lock()
RECORDS: "OrderedDict[int, dict]" = OrderedDict()
BODIES: dict = {}
CLIENTS: list = []
STATE = {"next_id": 1, "next_conv": 1, "server": None}


# ---------- request analysis ----------

def effort_of(req):
    oc = req.get("output_config") or {}
    r = req.get("reasoning")
    return (
        (oc.get("effort") if isinstance(oc, dict) else None)
        or (r.get("effort") if isinstance(r, dict) else None)
        or req.get("reasoning_effort")
    )


def cache_ttl(req):
    """How long the provider keeps this prefix cached, and how we know.

    ttl_s is the lifetime that can be relied on; ttl_max_s, when present, is how
    long the entry may survive beyond that. ttl_anchor says whether the provider
    counts from the start or the end of the request. Sources: the prompt caching
    guides of Anthropic and OpenAI, as of October 2026.
    """
    if config.TTL_FORCED:
        return {"ttl_s": config.TTL_FORCED, "ttl_source": "forzado con TAP_TTL_S", "ttl_anchor": "end"}
    model = str(req.get("model") or "").lower()
    if anthropic.owns(model):
        return anthropic.cache_ttl(req, model)
    gpt = base.version(model, "gpt")
    if gpt and gpt >= (5, 6):
        declared = isinstance(req.get("prompt_cache_options"), dict) and req["prompt_cache_options"].get("ttl")
        source = "declarado en prompt_cache_options" if declared else "por defecto de GPT-5.6 y posteriores"
        return {"ttl_s": 1800, "ttl_source": source, "ttl_anchor": "end"}
    if gpt or re.match(r"o\d", model):
        retention = req.get("prompt_cache_retention")
        if retention == "24h":
            return {"ttl_s": 1800, "ttl_max_s": 86400, "ttl_source": "declarado: retención 24h", "ttl_anchor": "end"}
        if retention == "in_memory":
            return {"ttl_s": 300, "ttl_max_s": 3600, "ttl_source": "declarado: retención in_memory", "ttl_anchor": "end"}
        if not (gpt == (4, 1) or (gpt and (5, 0) <= gpt)):
            return {"ttl_s": 300, "ttl_max_s": 3600, "ttl_source": "por defecto: este modelo solo admite in_memory", "ttl_anchor": "end"}
        # the default retention depends on the organisation (24h unless it has zero data retention)
        return {"ttl_s": 300, "ttl_max_s": 86400, "ttl_source": "supuesto: la retención por defecto depende de la organización", "ttl_anchor": "end"}
    return {"ttl_s": config.TTL_S, "ttl_source": "supuesto: proveedor sin TTL conocido", "ttl_anchor": "end"}


def min_cacheable(model):
    """Shortest prefix the provider will cache, in tokens."""
    model = str(model or "").lower()
    if not anthropic.owns(model):
        return 1024
    return anthropic.min_cacheable(model)


def _common(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def link_to_previous(rec, req):
    """Find the earlier request of the same conversation and describe what changed since.

    Conversations are matched on their messages only, so a client that rewrites
    tools or system between turns still links to its previous turn and the
    rewrite shows up as the divergence.
    """
    static = {s["name"]: s["hash"] for s in rec["segs"] if STATIC_SEG.search(s["name"])}
    msgs = [s["hash"] for s in rec["segs"] if not STATIC_SEG.search(s["name"])]
    rec["_static"], rec["_msgs"] = static, msgs
    best, best_n = None, 0
    for prev in RECORDS.values():
        n = _common(msgs, prev["_msgs"])
        if n >= 1 and n >= best_n:
            best, best_n = prev, n
    if best is None:
        rec["conv"] = f"c{STATE['next_conv']}"
        STATE["next_conv"] += 1
        rec["prev_id"] = None
        return
    rec["conv"] = best["conv"]
    rec["prev_id"] = best["id"]
    rec["gap_s"] = round(rec["ts"] - (best.get("ts_end") or best["ts"]), 1)
    # age of the previous cache entry, counted the way its provider counts it
    anchor = best["ts"] if best.get("ttl_anchor") == "start" else best.get("ts_end") or best["ts"]
    rec["age_s"] = round(rec["ts"] - anchor, 1)
    rec["prev_effort"] = best.get("effort")
    rec["prev_model"] = best.get("model")
    rec["effort_changed"] = best.get("effort") != rec.get("effort")
    rec["model_changed"] = best.get("model") != rec.get("model")
    rec["params_changed"] = best.get("_params") != rec.get("_params")
    diverge, mi = None, 0
    for s in rec["segs"]:
        if STATIC_SEG.search(s["name"]):
            same = best["_static"].get(s["name"]) == s["hash"]
        else:
            same = mi < best_n
            in_prev = mi < len(best["_msgs"])
            mi += 1
            if not same and not in_prev:
                s["same"] = False
                continue
        s["same"] = same and diverge is None
        if not same and diverge is None:
            diverge = s["name"]
    if diverge is None and set(best["_static"]) - set(static):
        diverge = sorted(set(best["_static"]) - set(static))[0] + " (eliminado)"
    rec["prefix_intact"] = diverge is None
    rec["diverge_at"] = diverge
    if diverge:
        rec["diff"] = segments.first_diff(BODIES.get(best["id"]), diverge, req)


# ---------- response analysis ----------

def _usage_events(body):
    events = []

    def grab(ev):
        if not isinstance(ev, dict):
            return
        for holder in (ev, ev.get("message"), ev.get("response")):
            if isinstance(holder, dict) and isinstance(holder.get("usage"), dict):
                events.append({"event": ev.get("type") or ev.get("object") or "json", "usage": holder["usage"]})
                return

    stripped = body.lstrip()
    if stripped.startswith("{"):
        try:
            grab(json.loads(stripped))
        except ValueError:
            pass
        return events
    for line in body.splitlines():
        if line.startswith("data:") and '"usage"' in line:
            try:
                grab(json.loads(line[5:]))
            except ValueError:
                continue
    return events


def _output_text(body):
    out, stop = [], None
    for line in body.splitlines():
        if not line.startswith("data:") or line.strip() == "data: [DONE]":
            continue
        try:
            ev = json.loads(line[5:])
        except ValueError:
            continue
        d = ev.get("delta")
        if isinstance(d, dict):
            if isinstance(d.get("text"), str):
                out.append(d["text"])
            stop = d.get("stop_reason") or stop
        elif isinstance(d, str) and str(ev.get("type", "")).endswith("output_text.delta"):
            out.append(d)
        for ch in ev.get("choices") or []:
            c = (ch.get("delta") or {}).get("content")
            if isinstance(c, str):
                out.append(c)
            stop = ch.get("finish_reason") or stop
    return "".join(out)[:2000], stop


def normalize(events):
    merged = {}
    for e in events:
        merged.update({k: v for k, v in e["usage"].items() if v is not None})
    if not merged:
        return None
    if "cache_read_input_tokens" in merged or "cache_creation_input_tokens" in merged:
        read = merged.get("cache_read_input_tokens") or 0
        write = merged.get("cache_creation_input_tokens") or 0
        unc = merged.get("input_tokens") or 0
        return {"read": read, "write": write, "uncached": unc, "input_total": read + write + unc,
                "output": merged.get("output_tokens") or 0, "reasoning": None}
    inp = merged.get("input_tokens", merged.get("prompt_tokens")) or 0
    det = merged.get("input_tokens_details") or merged.get("prompt_tokens_details") or {}
    odet = merged.get("output_tokens_details") or merged.get("completion_tokens_details") or {}
    read = det.get("cached_tokens") or 0
    return {"read": read, "write": None, "uncached": inp - read, "input_total": inp,
            "output": merged.get("output_tokens", merged.get("completion_tokens")) or 0,
            "reasoning": odet.get("reasoning_tokens")}


def judge(rec):
    u = rec.get("usage")
    if not u:
        rec["verdict"], rec["notes"] = "N/A", ["la respuesta no trae usage"]
        return
    prev = RECORDS.get(rec.get("prev_id"))
    read, total = u["read"], u["input_total"]
    base = (prev.get("usage") or {}).get("input_total") if prev else None
    minimum = min_cacheable(rec.get("model"))
    if read == 0 and total < minimum:
        verdict = "N/A"
    elif read == 0:
        verdict = "MISS" if prev else "COLD"
    elif base:
        verdict = "HIT" if read >= 0.9 * base else "PARTIAL"
    else:
        verdict = "HIT" if read >= 0.9 * total else "PARTIAL"
    notes, server_side = [], False
    if verdict == "N/A":
        notes.append(f"menos de {minimum} tokens de entrada: por debajo del mínimo cacheable de este modelo")
    elif not prev:
        notes.append("primera petición de esta conversación")
        if read:
            notes.append("parte del prefijo ya estaba en caché de otra conversación")
    else:
        ef = f"{rec.get('prev_effort')} → {rec.get('effort')}"
        if verdict == "HIT":
            if rec.get("effort_changed"):
                notes.append(f"hit pese al cambio de esfuerzo ({ef})")
            if not rec.get("prefix_intact"):
                notes.append(f"el cliente modificó el prefijo en {rec.get('diverge_at')}; el hit viene de una variante ya cacheada")
        else:
            if rec.get("model_changed"):
                notes.append(f"cambió el modelo ({rec.get('prev_model')} → {rec.get('model')})")
            if rec.get("effort_changed"):
                notes.append(f"cambió el esfuerzo ({ef})")
            if rec.get("params_changed"):
                notes.append("cambiaron thinking/tool_choice")
            if not rec.get("prefix_intact"):
                notes.append(f"el cliente modificó el prefijo en {rec.get('diverge_at')}")
            ttl, age = prev.get("ttl_s", config.TTL_S), rec.get("age_s", 0)
            if age > ttl:
                since = "el inicio" if prev.get("ttl_anchor") == "start" else "el final"
                notes.append(f"pasaron {age:.0f} s desde {since} de #{prev['id']} (TTL {ttl} s, {prev.get('ttl_source')})")
            if prev.get("state") != "done" or (prev.get("status") or 0) >= 400:
                notes.append(f"la petición anterior (#{prev['id']}) no terminó bien")
            if not notes:
                server_side = True
                notes.append(f"sin causa en el cliente: mismo prefijo, mismo esfuerzo, {rec.get('gap_s')} s desde #{prev['id']}")
    rec["verdict"], rec["notes"], rec["server_side"] = verdict, notes, server_side


# ---------- publishing ----------

def publish(ev):
    for q in list(CLIENTS):
        q.put(ev)


def push(rec):
    publish({"type": "record", "rec": record.light(rec)})


# ---------- mitmproxy hooks ----------

def _is_llm(flow):
    return flow.request.method == "POST" and flow.request.path.split("?")[0].rstrip("/").endswith(LLM_PATHS)


def request(flow):
    if not _is_llm(flow):
        return
    # the stream hook below sees raw bytes, so ask for an uncompressed response
    flow.request.headers["accept-encoding"] = "identity"
    text = flow.request.get_text(strict=False) or ""
    try:
        req = json.loads(text)
    except ValueError:
        req = {}
    with LOCK:
        rid = STATE["next_id"]
        STATE["next_id"] += 1
        rec = {
            "id": rid,
            "ts": flow.request.timestamp_start,
            "time": time.strftime("%H:%M:%S", time.localtime(flow.request.timestamp_start)),
            "host": flow.request.pretty_host,
            "path": flow.request.path.split("?")[0],
            "model": req.get("model"),
            "effort": effort_of(req),
            "effort_fields": {k: req[k] for k in ("output_config", "thinking", "reasoning", "reasoning_effort", "tool_choice", "max_tokens", "max_output_tokens", "stream") if k in req},
            "_params": segments.dump({k: req.get(k) for k in ("thinking", "tool_choice")}),
            "req_bytes": len(flow.request.raw_content or b""),
            "n_tools": len(req.get("tools") or []),
            "n_msgs": len(req.get("messages") or req.get("input") or []),
            "cc_marks": text.count('"cache_control"'),
            "segs": segments.segments(req),
            "state": "pending",
            **cache_ttl(req),
        }
        link_to_previous(rec, req)
        RECORDS[rid] = rec
        BODIES[rid] = text
        while len(RECORDS) > config.MAX:
            old, _ = RECORDS.popitem(last=False)
            BODIES.pop(old, None)
        push(rec)
    flow.metadata["tap_id"] = rid


def responseheaders(flow):
    rid = flow.metadata.get("tap_id")
    if rid is None:
        return
    st = {"chunks": [], "first": None}
    flow.metadata["tap_stream"] = st

    def stream(data: bytes):
        if data:
            st["chunks"].append(data)
            if st["first"] is None and any(k in data for k in FIRST_TOKEN):
                st["first"] = time.time()
        return data

    flow.response.stream = stream
    with LOCK:
        rec = RECORDS.get(rid)
        if rec:
            rec["state"] = "streaming"
            rec["status"] = flow.response.status_code
            rec["hdr_s"] = round(flow.response.timestamp_start - flow.request.timestamp_end, 3)
            rec["resp_headers"] = {k: v for k, v in flow.response.headers.items() if SAFE_HEADER.search(k) and not UNSAFE_HEADER.search(k)}
            push(rec)


def response(flow):
    rid = flow.metadata.get("tap_id")
    st = flow.metadata.get("tap_stream")
    if rid is None or st is None:
        return
    now = time.time()
    body = b"".join(st["chunks"]).decode("utf8", "replace")
    events = _usage_events(body)
    output, stop = _output_text(body)
    t0 = flow.request.timestamp_end
    with LOCK:
        rec = RECORDS.get(rid)
        if not rec:
            return
        rec.update({
            "state": "done",
            "ts_end": now,
            "ttft_s": round(st["first"] - t0, 3) if st["first"] else None,
            "total_s": round(now - t0, 3),
            "raw_usage": events,
            "usage": normalize(events),
            "output": output if flow.response.status_code < 400 else body[:2000],
            "stop_reason": stop,
        })
        written = anthropic.written_ttl(events)
        if written and not config.TTL_FORCED:
            minutes = written // 60
            rec.update({"ttl_s": written, "ttl_source": f"confirmado por usage: escritura a {minutes} min"})
        judge(rec)
        push(rec)
        with open(config.LOG, "a") as f:
            f.write(json.dumps(record.light(rec), ensure_ascii=False) + "\n")


def error(flow):
    rid = flow.metadata.get("tap_id")
    if rid is None:
        return
    with LOCK:
        rec = RECORDS.get(rid)
        if rec:
            rec.update({"state": "error", "ts_end": time.time(), "verdict": "ERR", "notes": [str(flow.error)]})
            push(rec)


# ---------- dashboard server ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _local(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json; charset=utf-8", cache="no-store"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._local():
            return self._send(403, "{}")
        path = self.path.split("?")[0]
        if path == "/events":
            return self._events()
        m = re.match(r"^/api/(record|body)/(\d+)$", path)
        if m:
            rid = int(m.group(2))
            with LOCK:
                if m.group(1) == "body":
                    body = BODIES.get(rid)
                else:
                    rec = RECORDS.get(rid)
                    body = json.dumps(record.public(rec), ensure_ascii=False) if rec else None
            return self._send(200, body) if body is not None else self._send(404, "{}")
        self._static(path)

    def _static(self, path):
        """Serve a dashboard file from ui/, and nothing outside of it."""
        f = (config.UI / (path.lstrip("/") or "index.html")).resolve()
        if config.UI not in f.parents or f.suffix not in MIME or not f.is_file():
            return self._send(404, "{}")
        # fonts never change; everything else is edited live
        cache = "max-age=86400" if f.suffix == ".woff2" else "no-store"
        self._send(200, f.read_bytes(), MIME[f.suffix], cache)

    def do_POST(self):
        if not self._local():
            return self._send(403, "{}")
        if self.path == "/api/clear":
            with LOCK:
                RECORDS.clear()
                BODIES.clear()
                publish({"type": "clear"})
            return self._send(200, "{}")
        self._send(404, "{}")

    def _events(self):
        q = queue.Queue()
        with LOCK:
            snap = [record.light(r) for r in RECORDS.values()]
            CLIENTS.append(q)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(f"data: {json.dumps({'type': 'snapshot', 'recs': snap, 'ttl': config.TTL_S})}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    ev = q.get(timeout=15)
                    self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            if q in CLIENTS:
                CLIENTS.remove(q)


def load(loader):
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(("127.0.0.1", config.UI_PORT), Handler)
    srv.daemon_threads = True
    STATE["server"] = srv
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[tap] dashboard: http://127.0.0.1:{config.UI_PORT}", flush=True)


def done():
    if STATE["server"]:
        STATE["server"].shutdown()
        STATE["server"].server_close()
