# VC Retail Analytics — update (2026-10-04, Access confirmed)

**Demo:** https://vc.datasharkbi.com/ (Access OTP → `operator` / `vc-demo`)  
**Repo:** https://github.com/prendleman/vc-retail-analytics  
**For:** Rahul Agarwal — AI Engineer III (`ragarwal@visualcomfort.com`)  
**Related:** [day narrative](./UPDATE_2026-10-04.md) · [execute runbook](./EXECUTE_2026-10-04.md) · [earlier ready note](./UPDATE_2026-10-04_ready.md)

## Short version

The interview surface is live and measured. Lab + Market + Snowflake voice are green on Fly. Cloudflare Access was re-checked in Zero Trust today: **`ragarwal@visualcomfort.com` is on the allowlist**. Ready to send.

## Access eyeball (2026-10-04 ~3:40 PM CT)

Policy **Allowlist email** (`730821e2-…`) on app **vc** (`vc.datasharkbi.com`), Action Allow. Live readback from the policy editor:

| Email | On policy |
| --- | --- |
| `prendleman@aureaquantra.com` | Yes |
| `tyler@perceptiverecruiting.com` | Yes |
| `jegenberg@visualcomfort.com` | Yes |
| `ragarwal@visualcomfort.com` | **Yes** |

No policy edit was required.

## What shipped today (product)

| Area | Status |
| --- | --- |
| Snowflake-only voice + live header controls | Live |
| Market analytics + continuous Mic + competitor share | Live |
| Interview Lab (board / evals / Cortex vs governed / scope / 90-day) | Live |
| `share_expansion` Snowflake JOIN fix | Live (`deployment-01M43Q80D90YJABKXAD15YMJ1T`) |
| Deck / PDF / `DEMO_SCRIPT` for Lab · Market · voice | Updated |

## Live verification

| Check | Result |
| --- | --- |
| Lab dry-run (Fly origin) | **`DRY_RUN_PASS`** — board, evals **20/20**, Cortex compare, scope pin, 90-day |
| Market asks on Snowflake | **PASS** — share expansion, competitor landscape, demand outlook, GM opportunity |
| Access allowlist for Rahul | **Confirmed** (Zero Trust UI, this afternoon) |

## How he walks it

1. https://vc.datasharkbi.com/ → email OTP → `operator` / `vc-demo` → hard-refresh  
2. Header → **Snowflake · 10 TB**  
3. **Analytics → Market** — forecast / GM / growth / competitors (public-estimate peers)  
4. **Lab** — board brief → evals → Cortex compare → pin `DLR-0001` → 90-day plan  
5. **Mic** — continuous voice on a governed Market or margin phrase  

## Honesty (say out loud)

- Synthetic data — not Visual Comfort production  
- Competitor revenues are calibrated public estimates  
- Typed assistant = FAQ + metric router; Lab Cortex is honesty / discovery  
- UI dealer pin mirrors RAP; production RAP stays on Snowflake SERVING  

## Owner send

- [x] Access allowlist includes Rahul  
- [x] Lab + Market green on live host  
- [x] Email Rahul the demo URL + `operator` / `vc-demo` + “start on **Lab** after Snowflake toggle”

**Status (2026-10-04 ~3:48 PM CT):** emailed. Waiting on his feedback.

**Closed (2026-10-05):** Janice (HR) is not moving the process forward. Hosted demo destroyed — see `docs/UPDATE_2026-10-05_shutdown.md`.
