# Private share — Cloudflare Tunnel + Access

Permanent hostname: **https://vc.datasharkbi.com**  
Always-on: Fly.io app `vc-retail-analytics` runs the demo + Cloudflare Tunnel (laptop not required).

Synthetic data only. Independent interview demo — not Visual Comfort production.

## Invite Access guests (OTP allowlist)

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

## One-time Cloudflare setup (already done)

```sh
python3 scripts/cf_setup_permanent.py --allow-email you@example.com
```

Tunnel `vc-retail-demo` → DNS `vc.datasharkbi.com` → Access app.

## Local fallback (optional)

```sh
python3 -m app.server          # Terminal 1
./scripts/share_private.sh     # Terminal 2 — only if Fly is down
```

Prefer Fly always-on so the URL does not depend on your Mac.

## Status (2026-10-02)

- Tunnel + DNS active; Fly hosts origin + `cloudflared --url http://127.0.0.1:8770`
- Unauthenticated `/` → `302` Cloudflare Access
- After Access + hard-refresh → marketing / app with deep Analytics UI
