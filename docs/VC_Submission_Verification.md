# VC Retail Analytics — submission verification notes

**Date (UTC):** 2026-10-02T20:19Z (checks) / deck regenerated same day  
**Checked commit family:** `700167c` plus subsequent local changes for submission polish  
**Hosted image (pre-redeploy of cache-bust):** `deployment-01M3Z3M16C51X916VH35S9YVYM`  
**Demo URL:** https://vc.datasharkbi.com/  
**Repository:** https://github.com/prendleman/vc-retail-analytics (public)

This note records what was actually verified. Deck claims must match this file.

## Implementation status

| Component | Status | Evidence |
| --- | --- | --- |
| Hosted app + SQLite | Running | `flyctl status` machine `d89510ea7d4e38` state `started` (ord). Unauthenticated GET to demo host returns `302` to Cloudflare Access. |
| Deterministic assistant | Implemented + tested | Exact-match router in `app/core.py` (`METRIC_PHRASES`). API test + ad-hoc ask; unsupported forecast → HTTP 400. |
| Session dealer scope | Implemented + tested | HMAC cookie (`app/demo_auth.py`). Isolation: dealer session cannot read another dealer via `?dealer=` or ask body (403). |
| Analytics sections | Implemented | Core / Margin / Season / Field / Supply UI + METRICS keys; screenshots captured from local build. |
| Snowflake adapter / RAP | Code present, live not verified | `sql/snowflake/*`, `scripts/cloud.py`. No reconcile run in this pass. |
| LLM integration | Proposed only | Not present in runtime. |

## Checks run (local synthetic fixtures)

Command context: temporary DB via `seed(..., dealers=12…50)`, `ThreadingHTTPServer` + `app.server.Handler`.

| Check | Result | Detail |
| --- | --- | --- |
| `python3 -m unittest tests.test_core tests.test_assistant` | PASS | 6/6 |
| Login `dlr-0001` / `vc-demo` | PASS | 200 |
| Bad password | PASS | 403 |
| Dealer isolation on `/api/summary?dealer=DLR-0002` | PASS | 403 |
| Dealer isolation on `/api/ask` with foreign dealer | PASS | 403 |
| Portfolio rows scoped | PASS | only `DLR-0001` |
| Summary vs independent SQL reconcile | PASS | net_sales and margin matched within $0.02 |
| Forecast refusal | PASS | 400 + offline text |
| Quarantine on full seed (50×200) | PASS | `quarantined=4` |
| Snowflake backend consistency | Not run | No live Snowflake session in this pass |
| Hosted Fly `.fly.dev` direct HTTP | Observed 501 | Public path is intended via Cloudflare Tunnel hostname, not fly.dev marketing URL |

## Access and entry path

- Cloudflare Access OTP is enabled on `vc.datasharkbi.com` (302 to `*.cloudflareaccess.com` without session).
- **Tyler / reviewers were not auto-added to the allowlist** (per task instructions). Owner must add emails in Zero Trust UI if needed (`tyler@perceptiverecruiting.com` noted in the task brief only).
- Demo accounts (synthetic only): `operator` / `vc-demo`, `dlr-0001` / `vc-demo`, `dlr-0002` / `vc-demo`.
- GitHub repository is public; no extra permissions required to read source.

### Hard-refresh / cache

- Server already sends `Cache-Control: no-store` on responses.
- Prior “hard-refresh for TSV UI” reflected an older Analytics renderer that was replaced by charts/tables. Stale browsers could still hold old `app.js`.
- **Mitigation applied:** cache-busting query strings on CSS/JS (`?v=20261002b`) in HTML entry points. Hard-refresh is no longer instructed as a required step; a normal refresh after deploy should suffice.
- Hosted redeploy of this mitigation should be confirmed after push/deploy of the polish commit.

## Screenshots used in the revised PDF

Captured from local `python3 -m app.server` with Playwright (operator login), synthetic data:

- `docs/deck/assets/shot_overview.png`
- `docs/deck/assets/shot_analytics_margin.png`
- `docs/deck/assets/shot_assistant_margin.png` (prompt `show margin percent`)

## Unresolved / honest limitations

1. Snowflake and Cortex paths are not live-verified for this submission.
2. Access guest management via API token returned Access-not-enabled for the token; UI allowlisting remains the operational path.
3. Direct `*.fly.dev` returned 501 in this environment; reviewers should use the Cloudflare hostname.
4. No demo video was recorded (optional; not blocking).

## Deliverable mapping

| Deliverable | Path |
| --- | --- |
| Revised PDF | `docs/deck/VC_Retail_Analytics_Submission_Revised.pdf` |
| Editable HTML source | `docs/deck/VC_Retail_Analytics_Deck.html` (from `scripts/gen_pdf.py`) |
| Alias PDF | `docs/deck/VC_Retail_Analytics_Deck.pdf` (same render) |
| This note | `docs/VC_Submission_Verification.md` |
