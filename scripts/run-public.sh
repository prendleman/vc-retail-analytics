#!/usr/bin/env bash
# Start local demo + Cloudflare quick tunnel (public HTTPS URL).
# Requires: python3, scripts/bin/cloudflared
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8770}"
CF="${ROOT}/scripts/bin/cloudflared"
if [[ ! -x "$CF" ]]; then
  echo "Missing $CF — download cloudflared into scripts/bin/" >&2
  exit 1
fi

cleanup() {
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

python3 -m app.server --port "$PORT" &
SERVER_PID=$!

# Wait for local listen
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

echo ""
echo "Local:   http://127.0.0.1:${PORT}/"
echo "Tunnel:  starting Cloudflare quick tunnel…"
echo "         (URL prints below — paste into the deck / share in interview)"
echo ""

exec "$CF" tunnel --url "http://127.0.0.1:${PORT}"
