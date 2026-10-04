# VC Retail Analytics — ready update (2026-10-04)

**Demo:** https://vc.datasharkbi.com/ (Access OTP → `operator` / `vc-demo`)  
**Repo:** https://github.com/prendleman/vc-retail-analytics  
**For:** Rahul Agarwal (`ragarwal@visualcomfort.com`) — AI Engineer III  
**Runbook executed:** [EXECUTE_2026-10-04.md](./EXECUTE_2026-10-04.md)  
**Day narrative:** [UPDATE_2026-10-04.md](./UPDATE_2026-10-04.md)

## Verdict

**Product path is ready.** Lab + Market + voice are live on Fly and measured green.  
**One owner action left before send:** eyeball Cloudflare Access and confirm `ragarwal@visualcomfort.com` is still on the allowlist (automation cannot read Zero Trust today).

## What we executed

| Check | Result |
| --- | --- |
| Lab dry-run (`scripts/dry_run_lab.py` → Fly origin) | **`DRY_RUN_PASS`** — Snowflake switch, board brief, evals **20/20**, Cortex compare, `DLR-0001` scope, 90-day plan |
| Market ask smoke on Snowflake | **PASS** — `share_expansion` 4 rows, `competitor_landscape` 13, `demand_outlook` 21, `gm_opportunity_usd` 7; analytics payload includes Market keys |
| Docs | `DEMO_SCRIPT.md` Rahul path · delivery checklist Rahul-ready section · competitor honesty in known limitations |
| Access allowlist re-verify | **Blocked** — Playwright hits Cloudflare bot interstitial on Zero Trust; API token still cannot list Access. Last confirmed permitted **2026-10-02**. |

## What shipped earlier today (already on `main` / Fly)

1. Snowflake-only voice + live header controls  
2. Market analytics + continuous Mic + competitor share plays  
3. Interview Lab (board / evals / Cortex vs governed / scope / 90-day)  
4. `share_expansion` JOIN fix + deck/PDF refresh + dry-run harness  
5. Demo script + Oct 4 update docs  

Image with board fix: `deployment-01M43Q80D90YJABKXAD15YMJ1T`.

## How Rahul should walk it

1. Access OTP on https://vc.datasharkbi.com/ → `operator` / `vc-demo` → hard-refresh.  
2. Header → **Snowflake · 10 TB**.  
3. **Analytics → Market** — forecast / GM / growth / competitors (say “public-estimate peers”).  
4. **Lab** — board brief → evals → Cortex compare → pin `DLR-0001` → 90-day plan.  
5. **Mic** — continuous voice on a governed Market or margin phrase.

## Honesty (say out loud)

- Synthetic data — not Visual Comfort production.  
- Competitor revenues are calibrated public estimates.  
- Typed assistant = FAQ + metric router; Lab Cortex is honesty / discovery.  
- UI dealer pin mirrors RAP; production RAP remains on Snowflake SERVING.

## Owner send checklist

- [ ] Zero Trust UI: confirm `ragarwal@visualcomfort.com` on `vc.datasharkbi.com` allowlist  
- [ ] Optional: hard-refresh the demo once yourself on Snowflake Lab  
- [ ] Send link + `operator` / `vc-demo` + point at **Lab** tab  

Do not wait on more product work.
