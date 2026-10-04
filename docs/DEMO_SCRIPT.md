# Ten-minute interview walkthrough — VC Retail Analytics

## Before you share

1. **Access guests:** Prefer Zero Trust UI (API token often cannot edit Access): https://one.dash.cloudflare.com/ → Access → Applications → **vc.datasharkbi.com** → Policies → allowlist. Confirm `ragarwal@visualcomfort.com` is listed. Optional CLI: `python3 scripts/cf_access_guests.py --list` / `… ragarwal@visualcomfort.com`.
2. **Hard-refresh:** After Access OTP, Cmd+Shift+R so `app.js` / charts load (not cached TSV UI).
3. **Always-on URL:** https://vc.datasharkbi.com/ (Fly + Cloudflare Tunnel — laptop not required).
4. **Smoke Lab (optional):** `python3 scripts/dry_run_lab.py https://vc-retail-analytics.fly.dev` → expect `DRY_RUN_PASS` (public hostname blocks non-browser clients).

## 0:00 | Frame the problem

“Independent portfolio demo: Visual Comfort–flavored retail analytics on **synthetic** data — margin, season, field, supply, **Market** share/GM/growth — plus a governed assistant and an Interview Lab that shows how I’d measure AI routing before shipping voice.”

Open https://vc.datasharkbi.com/ → Access OTP → show **SYNTHETIC** badge.

## 1:00 | Two logins (say this out loud)

| Login | Password | Why |
|---|---|---|
| `operator` | `vc-demo` | Full portfolio + Lab scope pin + Market |
| `dlr-0001` | `vc-demo` | Dealer tenancy — scoped KPIs |

Start **`operator`**. Flip header to **Snowflake · 10 TB** before Lab / voice / Market warehouse numbers.

## 2:00 | Overview

KPIs + channel bars. Session scope in the header. Catalog lineage via `/api/catalog` if asked.

## 3:00 | Deep analytics (operator)

Walk Analytics subnav — each panel is a governed metric + insight callouts:

1. **Core** — channel / family / region bars + stock risk
2. **Margin** — margin %, **waterfall mix contribution**, price realization, low-margin SKUs
3. **Season** — **heatmap**, units sparkline, YoY, **lead vs peak** (buy-ahead)
4. **Field** — territories, coverage vs capacity, whitespace, **rep A–D grades**
5. **Supply** — days of cover, **plan vs season**, reorder, vendor Prefer/Watch/Exit
6. **Market** — demand outlook, forecast vs run-rate, GM opportunity, growth, **competitor landscape / share expansion** (public-estimate peers — say that out loud)

Talk track: “Not vanity volume — margin discipline, seasonal buy-ahead, Prefer/Watch/Exit, and where we’d take share.”

## 5:00 | Interview Lab (Rahul path)

Stay on Snowflake. Open **Lab**:

1. **Board brief** — multi-metric spoken chain (share → GM → forecast → growth)
2. **Run evals** — 20 golden prompts; call out pass rate + latency
3. **Cortex vs governed** — same question side-by-side; prefer closed metrics
4. **Pin `DLR-0001`** — same ask, fewer rows (app-layer RAP story)
5. **90-day plan** — grounding → measure → harden; read the non-goals

## 6:30 | Assistant + voice

Assistant tab:

1. Today: `custom order lead time` → FAQ snippet (no warehouse)
2. Today: `where is my order 12345` → escalate form/phone pattern
3. Proposed: `show margin percent` or `show vendor scorecard` → insight + table + SQL trace
4. Escalate packet → structured handoff JSON

Then **Mic** (Snowflake only, continuous listening): ask a Market / margin phrase; spoken brief must match the screen. Header **Voice** is a real control — not a badge.

Say: offline typed assistant is a **FAQ + metric router, not an LLM**; Lab Cortex path is honesty / discovery, not the default runtime.

## 8:00 | Engineering honesty

Bronze → Silver → Gold (+ monthly + vendor KPI). Quarantine exists. Snowflake toggle is live; RAP evidence in `docs/evidence/`. Competitor revenues are calibrated public estimates, not filed financials. Public host is Fly + named tunnel + Access.

## 9:00 | Close

“Synthetic portfolio piece — not Visual Comfort production — showing how I’d ground retail AI in governed metrics, measure routing with evals, and keep generative paths behind a closed vocabulary.”
