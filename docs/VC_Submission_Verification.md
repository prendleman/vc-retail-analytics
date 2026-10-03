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
| Hosted app + SQLite | Running | Fly machine started; Cloudflare Access gate; authenticated checks on public hostname (owner signed in via the Cloudflare-account IdP, not OTP — see below) |
| Deterministic assistant | Implemented + tested | Exact-match router; hosted metric + clarify checks |
| Session dealer scope | Implemented + tested | Local isolation suite |
| Analytics sections | Implemented | Confirmed on hosted UI (full walkthrough + brief Core panel after fix deploy) |
| Snowflake adapter / RAP | **Built and verified 2026-10-03** | Full `cloud.py` chain run on a dedicated Enterprise account (AWS us-east-1): TPC-DS SF10TCL backbone (56.9B rows / 2.63 TB compressed) + generated sales-org / procurement / inventory / MRP layer; `validate` integrity checks 0/0/0/0; `reconcile` event subset = local exactly; app served on reader role incl. dealer-scoped RAP session. Evidence: `docs/evidence/snowflake_*.log`, `reconcile.json`. Not yet shown: Cortex path, second RAP principal. See `docs/SNOWFLAKE.md`. |
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
| `ragarwal@visualcomfort.com` | Confirmed permitted | Same save; address confirmed correct 2026-10-02 |

Policy membership is not evidence of any reviewer sign-in. API guest management remains blocked (`access.api.error.not_enabled`); UI route used.

## Access login method correction (2026-10-02T22:07Z)

Reported: a reviewer entered an email on the Cloudflare screen and received no code. Read-only inspection (authenticated dash session, account `c2b6521d…`) found:

| Item | Before | After |
| --- | --- | --- |
| Identity providers on org `dark-wood-4a5f.cloudflareaccess.com` | One only: type `cloudflare` (`53189405-…`, `restrict_to_account_members: true`) — **no One-time PIN provider** | `cloudflare` unchanged **+** `onetimepin` "One-time PIN login" (`1c0b31c2-723d-49e6-bd9e-1db30128807f`) |
| Fresh-session login page for `vc.datasharkbi.com` | "Sign in with: Cloudflare" only (no email field) | "Sign in with: Cloudflare — or — Email / Send login code" (email input present; confirmed 22:08:41Z–22:09:43Z) |
| App `vc` `allowed_idps` | `[]` (all providers) | unchanged |
| Policy `Allowlist email` | 4 emails, Allow, no Require/Exclude | unchanged |
| Access auth logs 21:30–22:10Z | Only owner logins (`allowed=true`, connection `cloudflare`); no reviewer entries — expected, since Access logs only after a code is submitted | — |

Root cause: the org was created with the Cloudflare-account identity provider as its only login method, so the Access screen offered no email-code option; the owner could sign in because he is an account member, reviewers could not. The policy allowlist was correct and was never the limiting factor. Earlier "Access OTP" wording in these notes described the intended flow, not the live one, before this correction.

Change made: one IdP added (above). Nothing removed, no bypass, no domain-wide rule. Rollback: delete identity provider `1c0b31c2-723d-49e6-bd9e-1db30128807f` (Zero Trust → Integrations → Identity providers). Unauthenticated `/` and `/api/ask` still return 302 to the Access login.

Confirmed: Access auth log entry `2026-10-02T22:16:46Z tyler@perceptiverecruiting.com vc.datasharkbi.com allowed=true connection=onetimepin`; reviewer reported successful entry to the demo. Other reviewers have not yet signed in.

## Local checks (earlier)

| Check | Result |
| --- | --- |
| Unit/API suite | PASS 6/6 |
| Quarantine full seed | `quarantined=4` |
| Snowflake parity | PASS on 2026-10-03 (`reconcile.json`: event subset diff 0.0 facts / 0.0 sales) |
| Direct `*.fly.dev` | 501 — use Cloudflare hostname |

## Screenshots in PDF

Local synthetic captures in `docs/deck/assets/shot_*.png` (not a hosted Access session).

## Deliverables

| Item | Path |
| --- | --- |
| Final PDF | `docs/deck/VC_Retail_Analytics_Submission_Final.pdf` |
| This note | `docs/VC_Submission_Verification.md` |
| Private delivery checklist | `docs/VC_Delivery_Checklist.md` |
