# VC submission — internal delivery checklist

**For Paul before emailing Tyler (2026-10-02).** Not for the public PDF.

| Item | Status |
| --- | --- |
| Tyler Access policy membership | **Unable to verify** (Access API `not_enabled`; Zero Trust dashboard unavailable during check). **Action:** confirm/add `tyler@perceptiverecruiting.com` only on the `vc.datasharkbi.com` Access allow policy. Do not broaden to a whole domain. |
| Hosted authenticated walkthrough | **Passed** (~2026-10-02T20:45Z UTC) on deployed `b40c9f6` via Access + `operator` / `vc-demo`. |
| Local tested revision | **`b40c9f6`** (app tree); suite re-run PASS 20:38Z / 20:49Z. |
| Deployed application revision (smoke) | **`b40c9f6`** (`deployment-01M3Z4VCRS9F738Z5ZWMMR3Z28`). |
| Clarify UI fix | In working tree (`app.js` + `?v=20261002c`); deploy separately so hosted refusal text matches local clarify answer. |
| Final PDF | `docs/deck/VC_Retail_Analytics_Submission_Final.pdf` |
| Verification notes | `docs/VC_Submission_Verification.md` |
| Repo | https://github.com/prendleman/vc-retail-analytics (public) |
| Demo | https://vc.datasharkbi.com/ |

**Remaining for Paul**

1. Confirm Tyler on Access allowlist when dashboard is available.
2. Optionally deploy the clarify UI fix, then normal-refresh the demo.
3. Send PDF + demo/repo links (this checklist is internal; do not email Tyler’s address from automation).

Nothing emailed; no unapproved Access changes made under this brief.
