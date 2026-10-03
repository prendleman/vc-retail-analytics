# AQ Snowflake setup — VC Retail Analytics (10 TB backbone)

Isolated database: **VC_RETAIL_DEMO** (do not reuse RELIEF_DEMO objects).

## What lands in Snowflake

| Layer | Source | Size | Cost profile |
| --- | --- | --- | --- |
| **Backbone** (BRONZE views) | `SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL` — Snowflake's shared TPC-DS 10 TB retail dataset (store/catalog/web sales ~50B rows, weekly inventory 783M, 402K items, 1,500 stores, 25 warehouses) | ~10 TB, **zero storage** (share) | Compute only when scanned |
| **Re-skinned dims** (BRONZE tables) | store→dealers, item→products, warehouse→distribution centers, state→territories, plus generated vendors | MBs | — |
| **Generated layer** (BRONZE tables) | `GENERATOR()`: salespeople, rep assignments/quotas, vendor contracts, components, BOM, purchase orders/lines, shipments, receipts, inventory snapshots (backbone weekly + on-order), demand forecast, MRP plan, work orders | ~10–20 GB at `--scale 1.0` | ~$0.25–0.50/month storage |
| **Silver** | `SILVER.FACTS` dealer×SKU for 50 demo dealers (trailing 12 mo) ∪ event-sourced facts; `SILVER.MONTHLY` all 1,500 dealers × family × channel × month; `SILVER.QUARANTINE` invalid source rows | ~20M + <1M + ~15M rows | — |
| **Gold** | Channel/family (scoped and all-dealer), weekly DC inventory, forecast by family-month, MRP exception summary, vendor scorecard | KBs–MBs | What the app reads for heavy metrics |

Channel mapping: `store_sales`→Trade, `catalog_sales`→Contract, `web_sales`→Consumer. Dates shift +24 years so TPC-DS 2000-10..2002-09 lands on the demo window ending **2026-09-30**. Prices re-scale to a lighting range ($250–$4,450 list); margin = net − cost, floored at 0 and capped at 55% of net (same rule as the SQLite seed).

## Profiles (local `~/.snowflake/connections.toml` — never commit)

```toml
[aq]
account = "YOUR_AQ_ORG-YOUR_AQ_ACCOUNT"
user = "YOUR_AQ_DEMO_OWNER"
authenticator = "externalbrowser"

[aq_vc_reader]
account = "YOUR_AQ_ORG-YOUR_AQ_ACCOUNT"
user = "YOUR_AQ_READER_USER"
authenticator = "externalbrowser"
role = "AQ_VC_READER"
warehouse = "AQ_VC_RETAIL_WH"
database = "VC_RETAIL_DEMO"
schema = "SERVING"
```

The owner profile needs: CREATE DATABASE/WAREHOUSE/ROLE, and read access to `SNOWFLAKE_SAMPLE_DATA` (present by default in most accounts; `doctor` checks).

## Ordered setup

```sh
python3 -m pip install -r requirements-cloud.txt
python3 -m scripts.seed                                   # local SQLite seed (also used by `load`)
python3 -m scripts.cloud doctor     --connection aq       # account, role, SNOWFLAKE_SAMPLE_DATA present?
python3 -m scripts.cloud platform   --connection aq       # DB, schemas, XSMALL serve WH + LARGE build WH (auto-suspend 60s)
python3 -m scripts.cloud load       --connection aq       # synthetic dims + events (50 dealers / 200 SKUs) → BRONZE
python3 -m scripts.cloud transform  --connection aq       # event lineage views; initial SILVER/GOLD tables
python3 -m scripts.cloud backbone   --connection aq --confirm-cost   # 06: TPC-DS dims, calendar, inventory extract
python3 -m scripts.cloud generate   --connection aq --confirm-cost   # 07: reps, vendors, BOM, POs, shipments, receipts
python3 -m scripts.cloud build      --connection aq --confirm-cost   # 08: two passes over 50B sales rows → SILVER/GOLD, forecast, MRP
python3 -m scripts.cloud governance --connection aq       # RAP on dealer-keyed SERVING views (re-run after every build)
python3 -m scripts.cloud semantic   --connection aq       # retail + supply semantic views
python3 -m scripts.cloud validate   --connection aq       # counts, backbone TB evidence, integrity checks
python3 -m scripts.cloud reconcile  --connection aq       # docs/evidence/reconcile.json (event subset must equal local)
```

`all` runs the whole chain. Flags: `--scale 0.1` for a cheap smoke build (200K POs), `--demo-dealers N` for the dealer×SKU scope, `--build-timeout` (default 5400 s).

### Cost expectations (LARGE = 8 credits/hour; verify against your contract rate)

| Step | Work | Expected |
| --- | --- | --- |
| backbone | dimension merges + one pass over inventory (783M rows) | ~1–2 credits |
| generate | GENERATOR tables at scale 1.0 | ~0.5–1.5 credits |
| build | scoped extract + grouping-sets pass over store/catalog/web sales (~50B rows, date-pruned to 24 of 60 months); 150M-row forecast; 10M-row MRP | ~4–8 credits |
| serving | XSMALL, auto-suspend 60 s; most metrics 1–5 s on 20M-row `SILVER.FACTS`; heavy metrics read Gold | pennies per demo session |

`cloud.py` suspends `AQ_VC_BUILD_WH` after each heavy step. Nothing in this repo creates a resource monitor; add one at the account level if you want a hard cap (`CREATE RESOURCE MONITOR ... CREDIT_QUOTA=20 ... SUSPEND_IMMEDIATE`).

## Reader access

Grant `AQ_VC_READER` to the reader principal and insert `CURRENT_USER()` → `DLR-0001` (or `*`) into `GOVERNANCE.USER_DEALERS`. Dealer-keyed views (facts, monthly, dealers, quarantine, gold channel/family, rep assignments) are row-filtered. Corporate supply-chain views (POs, inventory, MRP, BOM, vendors) are not dealer-keyed — any reader with the role sees them.

```sh
python3 -m app.server --backend snowflake --connection aq_vc_reader
```

On Snowflake the app keeps one authenticated connection, runs `/api/analytics` with a 6-way fan-out, and uses the `snowflake` SQL dialect: `inventory_trend`, `dc_inventory_health`, `forecast_accuracy`, `mrp_exceptions`, `vendor_scorecard` read Gold-backed `SERVING.GOLD_*` views (see `app/supply_chain.py: SNOWFLAKE_OVERRIDES`). Everything else runs the same governed SQL as SQLite against same-named SERVING views.

Cortex (optional): set `SNOWFLAKE_HOST` + `SNOWFLAKE_PAT`, then `python3 -m scripts.cortex "What is net sales by channel?"`.

## Status

Not yet run against a live account from this repo — see `docs/VC_Submission_Verification.md` for what has and has not been demonstrated. Evidence lands in `docs/evidence/` once `validate` and `reconcile` run.
