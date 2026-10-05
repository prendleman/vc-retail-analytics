# VC Retail Analytics — full teardown (2026-10-05)

**Context:** Janice Egenberg (HR, Visual Comfort) is not moving the interview process forward. All hosted / cloud demo footprint for this project is removed. Repo remains as a local portfolio archive.

## Destroyed / removed

| Resource | Action | Result |
| --- | --- | --- |
| Fly.io `vc-retail-analytics` | `flyctl apps destroy --yes` | Gone (earlier today) |
| Snowflake `VC_RETAIL_DEMO` | `DROP DATABASE … CASCADE` | Gone |
| Snowflake `AQ_VC_RETAIL_WH` / `AQ_VC_BUILD_WH` | `DROP WAREHOUSE` | Gone |
| Snowflake role `AQ_VC_READER` | `DROP ROLE` | Gone |
| Snowflake users `VC_FLY_SVC`, `VC_DLR0001_SVC` | `DROP USER` | Gone |
| Cloudflare Tunnel `vc-retail-demo` | `cloudflared tunnel delete -f` | Gone (FORTH `forth-relief-demo` kept) |
| DNS `vc.datasharkbi.com` CNAME | Deleted via Zero Trust / dash session | Gone |
| Access app **vc** | Deleted | Gone |
| Access policy **Allowlist email** (`730821e2-…`) | Deleted | Gone |
| Local tunnel cred `~/.cloudflared/ad9521c3-….json` | Removed | Gone |

## Left intentionally

| Resource | Why |
| --- | --- |
| GitHub repo + local tree | Portfolio / archive |
| FORTH Relief tunnel + `relief.datasharkbi.com` Access app | Separate project |
| Cloudflare One-time PIN IdP | Shared Zero Trust org; may still serve FORTH |
| Owner Cloudflare account | Unchanged |

## Verify

- `vc-retail-analytics.fly.dev` — does not resolve  
- `vc.datasharkbi.com` — no DNS record (stale resolvers may briefly show CF 530)  
- Snowflake `SHOW … LIKE 'VC_%'` / `AQ_VC%` — empty  

## Local archive only

```sh
python3 -m app.server   # SQLite seed only; no hosted Snowflake
```

Re-hosting would require recreating Fly, tunnel, DNS, Access, and a full Snowflake rebuild (`docs/SNOWFLAKE.md` / `docs/HOSTING.md` — historical).
