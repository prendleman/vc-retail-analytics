# Private share — Cloudflare Tunnel + Access

> **Teardown 2026-10-05:** Public demo `vc.datasharkbi.com` is offline. Tunnel, DNS, Access app, Fly origin, and Snowflake demo DB were removed. See `docs/UPDATE_2026-10-05_shutdown.md`. Steps below are historical.

Permanent hostname was **https://vc.datasharkbi.com**  
Always-on was Fly.io app `vc-retail-analytics` + Cloudflare Tunnel.

Synthetic data only. Independent interview demo — not Visual Comfort production.

## Invite Access guests (OTP allowlist) — historical

**Preferred (Zero Trust UI)** — API tokens on this account often cannot edit Access:

1. https://one.dash.cloudflare.com/ → **Access** → **Applications**
2. Open the **vc.datasharkbi.com** app → **Policies** → allowlist emails
3. Guests: https://vc.datasharkbi.com/ → email OTP → **hard-refresh** → `operator` / `vc-demo`

Optional CLI helper (works when the API token has Access edit):

```sh
python3 scripts/cf_access_guests.py recruiter@firm.com
python3 scripts/cf_access_guests.py --list
```

Demo logins:

| User | Password | Scope |
|---|---|---|
| `operator` | `vc-demo` | Full analytics (preferred for interview) |
| `dlr-0001` | `vc-demo` | Dealer-scoped |
| `dlr-0002` | `vc-demo` | Dealer-scoped |

Owner OTP emails used in setup: `prendleman@aureaquantra.com` (+ `CLOUDFLARE_ACCESS_ALLOW_EMAIL` in `.env`).

## One-time Cloudflare setup (historical)

```sh
python3 scripts/cf_setup_permanent.py --allow-email you@example.com
```

Tunnel `vc-retail-demo` → DNS `vc.datasharkbi.com` → Access app.

## Local only

```sh
python3 -m app.server
```

Do not recreate the VC public hostname unless intentional — FORTH Relief still uses `relief.datasharkbi.com` on the same Cloudflare account.
