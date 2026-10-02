#!/usr/bin/env bash
# Always-on entrypoint: local demo server + Cloudflare named tunnel.
# Requires TUNNEL_TOKEN (from: cloudflared tunnel token vc-retail-demo)
set -euo pipefail
cd "$(dirname "$0")/.."

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8770}"

python3 -m app.server --host "$HOST" --port "$PORT" &
APP_PID=$!

cleanup() {
  kill "$APP_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for local listen
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if [[ -z "${TUNNEL_TOKEN:-}" ]]; then
  echo "TUNNEL_TOKEN not set — serving only on ${HOST}:${PORT} (no Cloudflare hostname)." >&2
  wait "$APP_PID"
  exit $?
fi

echo "Starting Cloudflare Tunnel (vc.datasharkbi.com)…"
# Named-tunnel tokens often ship without remote ingress; --url supplies the local service rule.
exec cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${PORT}" run --token "$TUNNEL_TOKEN"
