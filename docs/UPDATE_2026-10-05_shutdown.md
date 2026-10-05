# VC Retail Analytics — shutdown (2026-10-05)

**Context:** Janice Egenberg (HR, Visual Comfort) is not moving the interview process forward. Hosted demo spend is stopped. Repo and local code remain as a portfolio artifact.

## What was shut down

| Resource | Action | Result |
| --- | --- | --- |
| Fly.io app `vc-retail-analytics` | `flyctl apps destroy vc-retail-analytics --yes` | **Destroyed** — machine gone; `vc-retail-analytics.fly.dev` no longer resolves |
| Fly secrets (tunnel token, Snowflake PAT, ElevenLabs, etc.) | Destroyed with the app | Gone |
| Snowflake `VC_FLY_SVC` PAT `VC_FLY_READER` | `REMOVE PROGRAMMATIC ACCESS TOKEN` | **Removed** — hosted reader can no longer auth |
| Snowflake warehouses `AQ_VC_RETAIL_WH` / `AQ_VC_BUILD_WH` | `ALTER … SUSPEND` | Already suspended (invalid state to suspend again) |

## Still in place (optional cleanup later)

| Resource | Status |
| --- | --- |
| DNS / Cloudflare Tunnel `vc-retail-demo` → `vc.datasharkbi.com` | Still configured; Access returns **302** with no healthy origin behind it |
| Cloudflare Access allowlist (Tyler / Janice / Rahul / owner) | Unchanged — leaf dead |
| Snowflake account data (TPC-DS build, RAP, evidence) | Intact in account; warehouses idle |
| GitHub repo + local tree | Intact — portfolio / archive |

Optional later: delete Zero Trust app **vc**, remove tunnel DNS, drop `VC_FLY_SVC`, or delete the Snowflake demo DB if you want zero residual cloud footprint.

## Process outcome

| Reviewer | Outcome |
| --- | --- |
| Tyler Rose | Signed in earlier; recruiter path |
| Rahul Agarwal | Emailed 2026-10-04 with Lab/Market demo; no further product work |
| Janice Egenberg | **Not moving forward** (2026-10-05) |

## Local use (if you reopen)

```sh
python3 -m app.server
# optional laptop tunnel — do not recreate Fly unless intentional
./scripts/share_private.sh
```

Snowflake toggle needs a fresh PAT if you ever host again (`docs/HOSTING.md`).
