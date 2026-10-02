# Always-on host (no laptop)

FORTH Relief was also **local server + Cloudflare Tunnel** — it only looked “always on” while that machine was running.

This project is set up for a **real always-on host**: Docker image runs the demo + `cloudflared` with a tunnel token so **https://vc.datasharkbi.com/** stays up without your Mac.

## What was added

- `HOST` / `PORT` bind (`0.0.0.0` in containers)
- `Dockerfile` — Python app + cloudflared
- `scripts/start_hosted.sh` — starts app, then tunnel
- `fly.toml` — Fly.io app config (`min_machines_running = 1`, no auto-stop)

## Deploy (Fly.io)

```sh
# one-time
curl -L https://fly.io/install.sh | sh   # or use ~/.fly/bin/flyctl already installed
flyctl auth login

cd /path/to/vc-retail-analytics
flyctl apps create vc-retail-analytics --org personal   # if needed

# Tunnel token (from your Mac, after tunnel login)
TOKEN="$(./scripts/bin/cloudflared tunnel token vc-retail-demo)"
flyctl secrets set TUNNEL_TOKEN="$TOKEN"

flyctl deploy
```

Keep DNS as-is: `vc.datasharkbi.com` → Cloudflare Tunnel. The connector now runs on Fly, not on your laptop.

Optional: remove Cloudflare Access (or leave it) in Zero Trust → Access controls.

## Local share (laptop) still works

```sh
python3 -m app.server
./scripts/share_private.sh
```

Do **not** run local `share_private.sh` at the same time as the Fly tunnel connector — two connectors on one tunnel can fight.
