# VC submission — internal delivery checklist

**For Paul before emailing reviewers (2026-10-02).** Not for the public PDF.

## Access policy (vc.datasharkbi.com → Allowlist email)

| Reviewer | Address | Policy status | Notes |
| --- | --- | --- | --- |
| Tyler Rose | `tyler@perceptiverecruiting.com` | **Unable to verify / not confirmed on policy** | Playwright reached policy detail; emails were not persisted. Readback still showed only owner email. |
| Janice Egenberg | `jegenberg@visualcomfort.com` | **Unable to verify / not confirmed on policy** | Same |
| Rahul Agarwal | `ragarwal@visualcomfort.com` | **Unable to verify / not confirmed on policy** | Same. Mailbox identity remains an **unverified guess** even after a future successful save. |

**Confirmed on policy today:** `prendleman@aureaquantra.com` only (screenshot readback).

### Exact manual step for Paul

1. Cloudflare Zero Trust → **Access controls** → **Policies** → **Allowlist email** → **Configure**
2. Under Include → Emails, add (preserve existing):
   - `tyler@perceptiverecruiting.com`
   - `jegenberg@visualcomfort.com`
   - `ragarwal@visualcomfort.com`
3. Save, reopen the policy detail, confirm all three appear next to the owner email.
4. Do not allow `@visualcomfort.com` as a whole domain.

API token path remains blocked (`access.api.error.not_enabled`).

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

**Remaining blocker before email:** add the three reviewer emails on the Allowlist email policy (manual Configure step above). Flag Rahul’s mailbox as unverified in any note to yourself.

Nothing emailed from this task.
