#!/usr/bin/env bash
# Named Cloudflare Tunnel for VC Retail Analytics (permanent URL).
# Refuses public quick tunnels. Requires ~/.cloudflared from browser login + setup.
# See docs/SHARE_PRIVATE.md.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CF="${ROOT}/scripts/bin/cloudflared"
if [[ ! -x "$CF" ]]; then
  if command -v cloudflared >/dev/null 2>&1; then
    CF="$(command -v cloudflared)"
  else
    echo "cloudflared not found (expected $ROOT/scripts/bin/cloudflared)" >&2
    exit 1
  fi
fi

HOSTNAME="${CLOUDFLARE_DEMO_HOSTNAME:-vc.datasharkbi.com}"
CFG="${HOME}/.cloudflared/config.vc-retail.yml"
TOKEN_FILE="${HOME}/.cloudflared/vc-retail-demo.run.token"

if [[ ! -f "$CFG" && ! -f "$TOKEN_FILE" ]]; then
  cat >&2 <<EOF
Missing tunnel config.

This script will NOT start a public quick tunnel.
  1) cloudflared tunnel login  (browser — aureaquantra account)
  2) python3 scripts/cf_setup_permanent.py   OR create tunnel + DNS as in docs/SHARE_PRIVATE.md
  3) python3 -m app.server
  4) re-run ./scripts/share_private.sh
EOF
  exit 2
fi

echo "Permanent share: https://${HOSTNAME}"
echo "Attach Cloudflare Access (email allowlist) before wide share — same as relief.datasharkbi.com."
echo "Local origin must be up: python3 -m app.server   (http://127.0.0.1:8770)"

if [[ -f "$TOKEN_FILE" ]]; then
  echo "Starting named tunnel via run token (Ctrl+C to stop)..."
  TOKEN="$(tr -d '\n\r' < "$TOKEN_FILE")"
  exec "$CF" tunnel run --token "$TOKEN"
fi

echo "Starting named tunnel via $CFG (Ctrl+C to stop)..."
exec "$CF" tunnel --config "$CFG" run
