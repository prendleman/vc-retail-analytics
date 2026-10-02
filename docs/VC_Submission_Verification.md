# VC Retail Analytics — submission verification notes

**Demo URL:** https://vc.datasharkbi.com/  
**Repository:** https://github.com/prendleman/vc-retail-analytics (public)

## Provenance (keep distinct)

| Kind | Identifier | When (UTC) |
| --- | --- | --- |
| Local unit/API suite | App tree matching `b40c9f6` | 2026-10-02T20:38Z and 20:49Z — PASS 6/6 |
| Full authenticated walkthrough | Deployed `b40c9f6` image `deployment-01M3Z4VCRS9F738Z5ZWMMR3Z28` | ~20:45Z — PASS |
| Clarify UI fix | Commit `d72fabf` | Deployed as image `deployment-01M3Z66M95NFGRZBW5YBJB97W3` (~20:52Z) |
| Hosted clarify + metric regression | Same `d72fabf` image; assets `?v=20261002c` | 2026-10-02T21:11Z — PASS |

## Implementation status

| Component | Status | Evidence |
| --- | --- | --- |
| Hosted app + SQLite | Running | Fly machine started; Access OTP; authenticated checks on public hostname |
| Deterministic assistant | Implemented + tested | Exact-match router; hosted metric + clarify checks |
| Session dealer scope | Implemented + tested | Local isolation suite |
| Analytics sections | Implemented | Confirmed on hosted UI (full walkthrough + brief Core panel after fix deploy) |
| Snowflake adapter / RAP | Code present, live not verified | No reconcile run |
| LLM integration | Proposed only | Not in runtime |

## Hosted clarification fix check (d72fabf)

Owner Access session + `operator` / `vc-demo` on https://vc.datasharkbi.com/

| Step | Result |
| --- | --- |
| Entry assets | `style.css?v=20261002c`, `app.js?v=20261002c` |
| `forecast next quarter invent numbers` | HTTP 400; UI showed clarify card with supported-prompt list (not blank error / not invented rows) |
| `show margin percent` | `margin_pct` + insight + SQL/tool trace |
| Analytics Core | Loaded without hard refresh |

## Access allowlist (reviewers)

Inspected via Zero Trust UI (account `c2b6521dc94949e90c39d6563b030802`). Policy **Allowlist email** (id `730821e2-…`) used by app `vc` / `vc.datasharkbi.com`.

| Address | Status | Basis |
| --- | --- | --- |
| `prendleman@aureaquantra.com` | Confirmed permitted | Preserved; visible on policy detail |
| `tyler@perceptiverecruiting.com` | Confirmed permitted | Added via Zero Trust UI ~2026-10-02T21:27Z; "Policy saved successfully"; visible on fresh policy detail load |
| `jegenberg@visualcomfort.com` | Confirmed permitted | Same save |
| `ragarwal@visualcomfort.com` | Confirmed permitted (policy entry) | Same save; mailbox identity remains an unverified guess |

Policy membership is not evidence of any reviewer sign-in. API guest management remains blocked (`access.api.error.not_enabled`); UI route used.

## Local checks (earlier)

| Check | Result |
| --- | --- |
| Unit/API suite | PASS 6/6 |
| Quarantine full seed | `quarantined=4` |
| Snowflake parity | Not run |
| Direct `*.fly.dev` | 501 — use Cloudflare hostname |

## Screenshots in PDF

Local synthetic captures in `docs/deck/assets/shot_*.png` (not hosted OTP session).

## Deliverables

| Item | Path |
| --- | --- |
| Final PDF | `docs/deck/VC_Retail_Analytics_Submission_Final.pdf` |
| This note | `docs/VC_Submission_Verification.md` |
| Private delivery checklist | `docs/VC_Delivery_Checklist.md` |
