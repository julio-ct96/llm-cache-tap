#!/bin/bash
# Starts the proxy (127.0.0.1:8899) and the dashboard (http://127.0.0.1:8900).
# Override ports with TAP_PROXY_PORT / TAP_UI_PORT, and the assumed cache TTL with TAP_TTL_S.
DIR="$(dirname "$(realpath "$0")")"
if [ ! -x "$DIR/venv/bin/mitmdump" ]; then
  python3 -m venv "$DIR/venv" && "$DIR/venv/bin/pip" install -q mitmproxy || exit 1
fi
exec "$DIR/venv/bin/mitmdump" --listen-host 127.0.0.1 -p "${TAP_PROXY_PORT:-8899}" \
  --set confdir="$DIR/ca" --set termlog_verbosity=warn --set flow_detail=0 -s "$DIR/tap.py"
