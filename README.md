# VC Retail Analytics

**Domain:** Visual Comfort–flavored lighting retail (independent interview demo)  
**Scope:** Synthetic dealer sell-through with **margin depth, seasonality, salesperson grades, territories, materials planning, and vendor scorecards** — plus a governed assistant framed as an improvement over site FAQ/form/chat.  
**Author:** Paul Rendleman  
**Live demo:** https://vc.datasharkbi.com/ (Cloudflare Access OTP → hard-refresh → login)

Synthetic data only. Not Visual Comfort production data. Not commissioned client work.

## Start in one command

Requires Python 3.9+. Local mode uses only the standard library.

```sh
python3 -m app.server
```

Open **http://127.0.0.1:8770** → Login → `/app`.

| User | Password | Notes |
|---|---|---|
| `operator` | `vc-demo` | Full Field / Supply — use for interview walkthrough |
| `dlr-0001` / `dlr-0002` | `vc-demo` | Dealer-scoped session |

**Hard-refresh** after deploy or first load if Analytics looks like plain text tables.

**Snowflake-backed mode** (after cloud bootstrap): see `docs/SNOWFLAKE.md` — re-skins Snowflake's shared 10 TB TPC-DS dataset as the sales/inventory backbone — sized to Visual Comfort's public footprint (~$750M/yr, 75 showrooms + dealer network, ~31K SKUs, 4 DCs; `docs/VC_PUBLIC_CALIBRATION.md`) — and generates salespeople, vendors, POs/shipments/receipts, DC inventory, BOM, forecast, and MRP on top. Same schema and governed metric SQL as the local SQLite demo; heavy metrics read Gold. The hosted demo defaults to SQLite and offers a per-session **SQLite | Snowflake · 10 TB** switch in the header (`--enable-snowflake` locally, or `SNOWFLAKE_ACCOUNT/USER/PAT` env on a host — see `docs/HOSTING.md`).

## What this demo shows

- Portfolio KPIs + channel / family / region rolls
- **Margin:** %, price realization, mix waterfall, low-margin SKUs
- **Season:** heatmap, YoY, lead-vs-peak buy-ahead flags
- **Field:** territories, coverage, whitespace, rep A–D grades
- **Supply:** days of cover, reorder, plan-vs-season, vendor Prefer/Watch/Exit
- Bronze → Silver → Gold (+ monthly facts + vendor KPI)
- Governed exact-match assistant (not an LLM) with insight + table + SQL trace
- Today vs Proposed chatbot gap
- Always-on public URL via Fly + Cloudflare Tunnel + Access

## Interview framing

| Item | Value |
|---|---|
| Company flavor | Visual Comfort & Co. (public brand language only) |
| Site | https://www.visualcomfort.com |
| Relationship | Independent synthetic interview prototype |
| Walkthrough | [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |
| Access guests | `python3 scripts/cf_access_guests.py you@firm.com` |

See **CURSOR_START_HERE.md**, **docs/CHATBOT_GAP.md**, **docs/SHARE_PRIVATE.md**.
