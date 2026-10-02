# VC Retail Analytics — submission verification notes

**Date (UTC):** 2026-10-02  
**Local tested revision (application):** `b40c9f6` — unit/API suite re-run PASS at 2026-10-02T20:38Z on a tree whose `app/` matched `b40c9f6` (docs-only follow-ups excluded). Quarantine full-seed re-check at 20:39Z: `quarantined=4`.  
**Deployed application revision (hosted smoke):** `b40c9f6` image `deployment-01M3Z4VCRS9F738Z5ZWMMR3Z28` (machine `d89510ea7d4e38`, started). Authenticated smoke at ~2026-10-02T20:45Z.  
**Clarify UI fix (post-smoke):** local change to `app/static/app.js` so HTTP 400 `kind=clarify` renders the refusal answer (previously empty `error` in UI). Cache-bust bumped to `?v=20261002c`. Deploy of this fix is separate from the smoke evidence above.  
**Demo URL:** https://vc.datasharkbi.com/  
**Repository:** https://github.com/prendleman/vc-retail-analytics (public)

This note records what was actually verified. Deck claims must match this file.

## Implementation status

| Component | Status | Evidence |
| --- | --- | --- |
| Hosted app + SQLite | Running + authenticated smoke PASS | Fly machine started; Access OTP; operator walkthrough on public hostname (see Hosted smoke). |
| Deterministic assistant | Implemented + tested | Exact-match router (`METRIC_PHRASES`). Local API tests; hosted `show margin percent` returned `margin_pct` + SQL/tool trace. |
| Session dealer scope | Implemented + tested | HMAC cookie. Local isolation: dealer cannot read another dealer (403). |
| Analytics sections | Implemented | Core / Margin / Season / Field / Supply confirmed on hosted UI without hard refresh. |
| Snowflake adapter / RAP | Code present, live not verified | `sql/snowflake/*`, `scripts/cloud.py`. No reconcile run. |
| LLM integration | Proposed only | Not present in runtime. |

## Checks run (local synthetic fixtures)

| Check | Result | Detail |
| --- | --- | --- |
| `python3 -m unittest tests.test_core tests.test_assistant` | PASS | 6/6 at 2026-10-02T20:38Z and again 20:49Z |
| Login / bad password | PASS | Covered by suite |
| Dealer isolation | PASS | Covered by suite |
| Metric reconcile | PASS | Prior pass + suite; tolerance $0.02 |
| Forecast refusal | PASS | Local 400 clarify; hosted HTTP 400 (no metric rows) |
| Quarantine on full seed (50×200) | PASS | `quarantined=4` |
| Snowflake backend consistency | Not run | No live Snowflake session |
| Hosted Fly `.fly.dev` direct HTTP | Observed 501 | Use Cloudflare hostname |

## Hosted authenticated smoke (vc.datasharkbi.com)

**Browser:** Cursor IDE browser · **Account:** synthetic `operator` / `vc-demo` after owner Access OTP · **Build:** deployed `b40c9f6` · **UTC:** ~2026-10-02T20:45Z

| Step | Result |
| --- | --- |
| Access OTP → marketing | PASS |
| App login operator | PASS → `/app` |
| Overview KPIs + portfolio | PASS (e.g. dealers 50, net sales present, quarantined 4) |
| Analytics Core / Margin / Season / Field / Supply | PASS charts/tables/insights without hard refresh |
| Asset versions | PASS `app.js?v=20261002b` / `style.css?v=20261002b` on that image |
| Assistant `show margin percent` | PASS metric + insight + SQL/tool trace |
| Unsupported forecast prompt | PASS HTTP 400; UI showed empty error string until clarify fix (no fabricated forecast) |
| Catalog search `alabaster` | PASS matching rows |
| Log out | PASS → marketing `/` |

Console: no blocking failures observed for the above path. OTP/cookies/tokens were not captured into repository artifacts.

## Access and entry path

- Cloudflare Access OTP enabled (unauthenticated GET → 302 to Access).
- **Tyler (`tyler@perceptiverecruiting.com`) policy membership: Unable to verify.** Access Apps API returns `access.api.error.not_enabled` for the configured token; Zero Trust dashboard was temporarily unavailable during the check window. Do not infer permission from OTP UI alone.
- **Action for Paul:** In Zero Trust → Access → Applications → `vc.datasharkbi.com` policy, confirm or add only `tyler@perceptiverecruiting.com`. This brief did not change allowlists.
- Demo accounts (synthetic): `operator` / `vc-demo`, `dlr-0001` / `vc-demo`, `dlr-0002` / `vc-demo`.
- GitHub is public.

### Hard-refresh / cache

- `Cache-Control: no-store` on responses; versioned CSS/JS query strings.
- Hosted smoke confirmed charts without hard refresh on `?v=20261002b` image.
- Local clarify-display fix uses `?v=20261002c` after deploy.

## Screenshots in the PDF

From local synthetic build (Playwright), not hosted OTP session:

- `docs/deck/assets/shot_overview.png`
- `docs/deck/assets/shot_analytics_margin.png`
- `docs/deck/assets/shot_assistant_margin.png`

## Unresolved / honest limitations

1. Snowflake and Cortex paths are not live-verified.
2. Tyler Access membership unable to verify (API + dashboard blockers); owner must confirm allowlist before emailing.
3. Direct `*.fly.dev` returns 501; reviewers use `https://vc.datasharkbi.com`.
4. Clarify UI empty-error on hosted `b40c9f6` image; fixed in working tree (`app.js`), pending deploy for live clarity text.
5. No demo video recorded.

## Deliverable mapping

| Deliverable | Path |
| --- | --- |
| Final PDF | `docs/deck/VC_Retail_Analytics_Submission_Final.pdf` |
| Revised alias | `docs/deck/VC_Retail_Analytics_Submission_Revised.pdf` |
| Editable HTML | `docs/deck/VC_Retail_Analytics_Deck.html` |
| This note | `docs/VC_Submission_Verification.md` |
| Delivery checklist | `docs/VC_Delivery_Checklist.md` |
