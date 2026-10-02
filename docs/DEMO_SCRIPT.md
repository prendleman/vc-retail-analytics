# Ten-minute interview walkthrough — VC Retail Analytics

## Before you share

1. **Access guests:** `python3 scripts/cf_access_guests.py recruiter@firm.com` (merges into allowlist). Confirm with `--list`.
2. **Hard-refresh:** After Access OTP, Cmd+Shift+R so `app.js` / charts load (not cached TSV UI).
3. **Always-on URL:** https://vc.datasharkbi.com/ (Fly + Cloudflare Tunnel — laptop not required).

## 0:00 | Frame the problem

“Independent portfolio demo: Visual Comfort–flavored retail analytics on **synthetic** data — margin depth, seasonality, field grades, materials planning, vendor scorecards — plus a governed assistant that improves on form/FAQ/chat support.”

Open https://vc.datasharkbi.com/ → Access OTP → show **SYNTHETIC** badge.

## 1:00 | Two logins (say this out loud)

| Login | Password | Why |
|---|---|---|
| `dlr-0001` | `vc-demo` | Dealer tenancy — scoped KPIs |
| `operator` | `vc-demo` | Full Field / Supply (territories, all reps, vendor scorecard) |

Start **`operator`** for the analytics story; switch to `dlr-0001` once to prove session lock.

## 2:00 | Overview

KPIs + channel bars. Session scope in the header. Catalog lineage via `/api/catalog` if asked.

## 3:00 | Deep analytics (operator)

Walk Analytics subnav — each panel is a governed metric + insight callouts:

1. **Core** — channel / family / region bars + stock risk  
2. **Margin** — margin %, **waterfall mix contribution**, price realization, low-margin SKUs  
3. **Season** — **heatmap**, units sparkline, YoY, **lead vs peak** (buy-ahead)  
4. **Field** — territories, coverage vs capacity, whitespace, **rep A–D grades**  
5. **Supply** — days of cover, **plan vs season**, reorder, vendor Prefer/Watch/Exit  

Talk track: “Not vanity volume — margin discipline, seasonal buy-ahead, Prefer/Watch/Exit.”

## 5:30 | Today vs Proposed

Assistant tab:

1. Today: `custom order lead time` → FAQ snippet (no warehouse)  
2. Today: `where is my order 12345` → escalate form/phone pattern  
3. Proposed: `show margin percent` or `show vendor scorecard` → insight + table + SQL trace  
4. Escalate packet → structured handoff JSON  

Say: offline assistant is a **FAQ + metric router, not an LLM**.

## 7:30 | Engineering honesty

Bronze → Silver → Gold (+ monthly + vendor KPI). Quarantine exists. Snowflake optional — only claim live cloud with reconcile evidence. Public host is Fly + named tunnel.

## 8:30 | Close

“Synthetic portfolio piece — not Visual Comfort production — showing how I’d ground retail AI in governed metrics across margin, season, field, and supply.”
