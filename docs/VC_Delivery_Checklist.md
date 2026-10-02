# VC submission — internal delivery checklist

**For Paul before emailing reviewers (2026-10-02).** Not for the public PDF.

## Access policy (vc.datasharkbi.com → Allowlist email)

Policy **Allowlist email** (`730821e2-a838-49ec-9b19-6b7b7614fbbe`), single Include → Emails rule, Action Allow. Edited via Zero Trust UI (Playwright, owner session) at ~2026-10-02T21:27Z; toast "Policy saved successfully"; readback from a fresh load of the policy detail page.

| Reviewer | Address | Policy status | Notes |
| --- | --- | --- | --- |
| Tyler Rose | `tyler@perceptiverecruiting.com` | **Confirmed permitted** | Visible on policy detail after save |
| Janice Egenberg | `jegenberg@visualcomfort.com` | **Confirmed permitted** | Visible on policy detail after save |
| Rahul Agarwal | `ragarwal@visualcomfort.com` | **Confirmed permitted** (policy entry) | Mailbox identity remains an **unverified guess**; a saved entry means that exact address is permitted, not that the mailbox exists or is Rahul's |
| Owner | `prendleman@aureaquantra.com` | Confirmed permitted | Preserved |

No domain-wide allow; Access gate unchanged otherwise. Policy status is not evidence that any reviewer has signed in.

API token path remains blocked (`access.api.error.not_enabled`); UI is the operational route (`scripts/cf_access_add_guest_playwright.py` for future guests).

## Clarification-message fix

| Item | Status |
| --- | --- |
| Fix commit | `d72fabf` (`app/static/app.js` returns `kind=clarify` on HTTP 400; assets `?v=20261002c`) |
| Deployed image | `deployment-01M3Z66M95NFGRZBW5YBJB97W3` (Fly machine version 9, started ~2026-10-02T20:52Z) |
| Hosted clarification text | **Pass** — 2026-10-02T21:11Z UTC; forecast prompt → HTTP 400; UI showed clarify answer listing supported prompts (not blank/`undefined`/fabricated rows) |
| Supported metric regression | **Pass** — `show margin percent` → `margin_pct` + insight + SQL/tool trace |
| Analytics smoke | **Pass** — Core panel loaded without hard refresh |

Earlier full walkthrough remains attributed to `b40c9f6` (~20:45Z). Targeted fix checks belong to `d72fabf` / image above.

## Package for send

| Item | Path / URL |
| --- | --- |
| Final PDF | `docs/deck/VC_Retail_Analytics_Submission_Final.pdf` |
| Demo | https://vc.datasharkbi.com/ |
| Repo | https://github.com/prendleman/vc-retail-analytics |
| Demo login | `operator` / `vc-demo` (after Access OTP) |

**Status:** technical package ready to send (PDF + demo URL + GitHub + demo login). Rahul's mailbox is still an unverified guess; if he does not receive the OTP, confirm his address and add the correct one.

Nothing emailed from this task.
