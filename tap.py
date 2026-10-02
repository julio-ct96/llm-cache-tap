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

from cachetap import config, linking, providers, record, response_body, segments, verdict

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".woff2": "font/woff2",
}
LLM_PATHS = ("/messages", "/responses", "/chat/completions")
SAFE_HEADER = re.compile(r"request-id|region|geo|served|backend|azure|ratelimit|quota|processing|x-cache|via$", re.I)
UNSAFE_HEADER = re.compile(r"token|auth|cookie|secret|key", re.I)

LOCK = threading.Lock()
RECORDS: "OrderedDict[int, dict]" = OrderedDict()
BODIES: dict = {}
CLIENTS: list = []
STATE = {"next_id": 1, "next_conv": 1, "server": None}


# ---------- request analysis ----------

# ---------- response analysis ----------

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
            "effort": providers.effort_of(req),
            "effort_fields": {k: req[k] for k in ("output_config", "thinking", "reasoning", "reasoning_effort", "tool_choice", "max_tokens", "max_output_tokens", "stream") if k in req},
            "_params": segments.dump({k: req.get(k) for k in ("thinking", "tool_choice")}),
            "req_bytes": len(flow.request.raw_content or b""),
            "n_tools": len(req.get("tools") or []),
            "n_msgs": len(req.get("messages") or req.get("input") or []),
            "cc_marks": text.count('"cache_control"'),
            "segs": segments.segments(req),
            "state": "pending",
            **providers.cache_ttl(req),
        }
        best, best_n = linking.find_previous(rec, RECORDS.values())
        if best is None:
            rec["conv"] = f"c{STATE['next_conv']}"
            STATE["next_conv"] += 1
            rec["prev_id"] = None
        else:
            linking.link(rec, req, best, best_n, BODIES.get(best["id"]))
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
            if st["first"] is None and any(k in data for k in providers.FIRST_TOKEN):
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
    events = response_body.usage_events(body)
    output, stop = response_body.output_text(body)
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
            "usage": providers.normalize(events),
            "output": output if flow.response.status_code < 400 else body[:2000],
            "stop_reason": stop,
        })
        written = providers.written_ttl(events)
        if written and not config.TTL_FORCED:
            minutes = written // 60
            rec.update({"ttl_s": written, "ttl_source": f"confirmado por usage: escritura a {minutes} min"})
        verdict.judge(rec, RECORDS.get(rec.get("prev_id")))
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
