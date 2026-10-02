#!/bin/bash
# Runs any command through the proxy: ./via.sh opencode   |   ./via.sh opencode run -m ... "hola"
# Only this process trusts the proxy CA; nothing is installed in the system keychain.
DIR="$(dirname "$(realpath "$0")")"
PROXY="http://127.0.0.1:${TAP_PROXY_PORT:-8899}"
export HTTPS_PROXY="$PROXY" HTTP_PROXY="$PROXY" https_proxy="$PROXY" http_proxy="$PROXY"
export NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1"
export NODE_EXTRA_CA_CERTS="$DIR/ca/mitmproxy-ca-cert.pem"
exec "$@"
