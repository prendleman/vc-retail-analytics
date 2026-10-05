# Always-on host (no laptop)

> **Shutdown 2026-10-05:** Fly app `vc-retail-analytics` was destroyed. Public demo is offline. See `docs/UPDATE_2026-10-05_shutdown.md`. Steps below are historical / for a future re-host.

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

## Optional: Snowflake backend toggle on the host

The app serves SQLite by default. If these secrets are present it also opens a Snowflake connection at boot and shows a **SQLite | Snowflake · 10 TB** switch in the header (per browser session, login required; see `docs/SNOWFLAKE.md`).

| Secret | Value |
| --- | --- |
| `SNOWFLAKE_ACCOUNT` | org-account identifier (`ORG-ACCOUNT`) |
| `SNOWFLAKE_USER` | a dedicated `TYPE = SERVICE` user holding only `AQ_VC_READER` |
| `SNOWFLAKE_PAT` | programmatic access token on that user, `ROLE_RESTRICTION = 'AQ_VC_READER'`, 90-day expiry |
| `SNOWFLAKE_ROLE` / `SNOWFLAKE_WAREHOUSE` | optional; default `AQ_VC_READER` / `AQ_VC_RETAIL_WH` |

Mint and stage without the token touching disk or the terminal (Snowflake will not let a PAT-authenticated session mint a PAT for the *same* user, which is one more reason to use a separate service user):

```sh
python3 - <<'EOF' | flyctl secrets import --stage
import snowflake.connector
c = snowflake.connector.connect(connection_name="aq")            # owner profile, ~/.snowflake/connections.toml
cur = c.cursor()
cur.execute("CREATE USER IF NOT EXISTS VC_FLY_SVC TYPE = SERVICE DEFAULT_ROLE = AQ_VC_READER DEFAULT_WAREHOUSE = AQ_VC_RETAIL_WH")
cur.execute("GRANT ROLE AQ_VC_READER TO USER VC_FLY_SVC")
cur.execute("ALTER USER VC_FLY_SVC ADD PROGRAMMATIC ACCESS TOKEN VC_FLY_READER ROLE_RESTRICTION = 'AQ_VC_READER' DAYS_TO_EXPIRY = 90")
tok = dict(zip([d[0].lower() for d in cur.description], cur.fetchone()))["token_secret"]
print(f"SNOWFLAKE_ACCOUNT={c.account}\nSNOWFLAKE_USER=VC_FLY_SVC\nSNOWFLAKE_PAT={tok}")
EOF
flyctl deploy --remote-only            # applies staged secrets
```

The service user also needs a row in `GOVERNANCE.USER_DEALERS` (`'VC_FLY_SVC', '*'`), or the row access policy returns zero dealer rows. Rotate by re-running the mint block (remove the old token first: `ALTER USER VC_FLY_SVC REMOVE PROGRAMMATIC ACCESS TOKEN VC_FLY_READER`). To turn the toggle off, `flyctl secrets unset SNOWFLAKE_PAT` and redeploy — the app falls back to SQLite-only.

Verify: `curl -s https://vc-retail-analytics.fly.dev/api/health` should list `"backends_available": ["local", "snowflake"]`.

Optional: remove Cloudflare Access (or leave it) in Zero Trust → Access controls.

## Local share (laptop) still works

```sh
python3 -m app.server
./scripts/share_private.sh
```

Do **not** run local `share_private.sh` at the same time as the Fly tunnel connector — two connectors on one tunnel can fight.
