import os
import socketserver
import sys
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

# Only exception to "imports first": the root must be on sys.path before importing tests.replay.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.replay import adapter  # noqa: E402
from tests.replay.scenario import all_steps, run  # noqa: E402

DEFAULT_PORT = 8901
REAL_PROXY_PORTS = (8899, 8900)


class ReplayHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


def main():
    port = int(os.environ.get("TAP_UI_PORT", DEFAULT_PORT))
    if port in REAL_PROXY_PORTS:
        print(f"error: el puerto {port} es del proxy real; usa otro en TAP_UI_PORT", file=sys.stderr)
        return 1
    # Last request lands ~50 s ago, so its cache countdown is still alive.
    run(all_steps(), base_ts=time.time() - 20850)
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer.daemon_threads = True
    server = ReplayHTTPServer(("127.0.0.1", port), adapter.handler())
    print(f"panel de prueba: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
