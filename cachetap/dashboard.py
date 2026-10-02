"""HTTP server of the dashboard: static files from ui/, record API and the live event stream."""

import json
import queue
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cachetap import config, record, store

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".woff2": "font/woff2",
}


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
            with store.LOCK:
                if m.group(1) == "body":
                    body = store.BODIES.get(rid)
                else:
                    rec = store.RECORDS.get(rid)
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
            with store.LOCK:
                store.clear()
            return self._send(200, "{}")
        self._send(404, "{}")

    def _events(self):
        q = queue.Queue()
        with store.LOCK:
            snap = [record.light(r) for r in store.RECORDS.values()]
            store.CLIENTS.append(q)
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
            if q in store.CLIENTS:
                store.CLIENTS.remove(q)


_server = None


def start():
    global _server
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer(("127.0.0.1", config.UI_PORT), Handler)
    srv.daemon_threads = True
    _server = srv
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def stop():
    global _server
    if _server:
        _server.shutdown()
        _server.server_close()
    _server = None
