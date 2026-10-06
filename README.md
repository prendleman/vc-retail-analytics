# VC Retail Analytics

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Domain:** Visual Comfort–flavored lighting retail (independent interview demo)  
**Scope:** Synthetic dealer sell-through with **margin depth, seasonality, salesperson grades, territories, materials planning, and vendor scorecards** — plus a governed assistant framed as an improvement over site FAQ/form/chat.  
**Author:** Paul Rendleman  
**Status:** Local portfolio archive. Hosted demo offline as of 2026-10-05 (process closed; cloud footprint torn down — see [`docs/UPDATE_2026-10-05_shutdown.md`](docs/UPDATE_2026-10-05_shutdown.md)).

Synthetic data only. Not Visual Comfort production data. Not commissioned client work.

## Start in one command

Requires Python 3.9+. Local mode uses only the standard library — no cloud account required.

```sh
python3 -m app.server
```

Open **http://127.0.0.1:8770** → Login → `/app`.

| User | Password | Notes |
|---|---|---|
| `operator` | `vc-demo` | Full Field / Supply — use for interview walkthrough |
| `dlr-0001` / `dlr-0002` | `vc-demo` | Dealer-scoped session |

**Hard-refresh** on first load if Analytics looks like plain text tables.

**Optional Snowflake mode:** if you bring your own Snowflake credentials, see [`docs/SNOWFLAKE.md`](docs/SNOWFLAKE.md). That path re-skins Snowflake's shared TPC-DS dataset as the sales/inventory backbone — sized to Visual Comfort's public footprint (~$750M/yr, 75 showrooms + dealer network, ~31K SKUs, 4 DCs; [`docs/VC_PUBLIC_CALIBRATION.md`](docs/VC_PUBLIC_CALIBRATION.md)) — and generates salespeople, vendors, POs/shipments/receipts, DC inventory, BOM, forecast, and MRP on top. Same schema and governed metric SQL as the local SQLite demo. Enable locally with `--enable-snowflake` or `SNOWFLAKE_ACCOUNT` / `USER` / `PAT` (see [`docs/HOSTING.md`](docs/HOSTING.md) for historical hosting notes). The default path is SQLite-only.

## What this demo shows

- Portfolio KPIs + channel / family / region rolls
- **Margin:** %, price realization, mix waterfall, low-margin SKUs
- **Season:** heatmap, YoY, lead-vs-peak buy-ahead flags
- **Field:** territories, coverage, whitespace, rep A–D grades
- **Supply:** days of cover, reorder, plan-vs-season, vendor Prefer/Watch/Exit
- Bronze → Silver → Gold (+ monthly facts + vendor KPI)
- Governed exact-match assistant (not an LLM) with insight + table + SQL trace
- Today vs Proposed chatbot gap
- Local-first archive (prior Fly + Cloudflare hosted demo fully torn down)

## Interview framing

| Item | Value |
|---|---|
| Company flavor | Visual Comfort & Co. (public brand language only) |
| Site | https://www.visualcomfort.com |
| Relationship | Independent synthetic interview prototype |
| Walkthrough | [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |

See **CURSOR_START_HERE.md**, **docs/CHATBOT_GAP.md**, and **docs/SHARE_PRIVATE.md** for walkthrough context.
