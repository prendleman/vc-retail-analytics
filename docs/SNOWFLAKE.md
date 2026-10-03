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

**About "10 TB":** TPC-DS SF10TCL is the 10 TB *scale factor* (raw generated data, 56.9 billion rows). Snowflake stores it compressed: `INFORMATION_SCHEMA.TABLES` reports **2.63 TB** for the share, and that is the number the validation step records. Both figures are quoted in the evidence; don't present 10 TB as bytes-on-disk.

### Re-skin rules (retailer → lighting dealer)

TPC-DS is a general-merchandise retailer: ~30M units per store-month at $1–$100. A lighting dealer sells a few thousand units a month at $250–$4,450. `06_backbone.sql` therefore:

| Rule | Setting | Effect |
| --- | --- | --- |
| Channel | `store_sales`→Trade, `catalog_sales`→Contract, `web_sales`→Consumer; catalog/web dealer = `MOD(order_number,1500)+1` | three channels, every dealer sells in all three |
| Dates | +24 years (`YEAR_SHIFT`) | 2000-10..2002-09 → 2024-10..2026-09, fixed "today" 2026-09-30 |
| Volume | keep 1 ticket/order in `--sample-mod` (default 200; hash independent of the dealer residue); qty 1..100 → 1..4 (`QTY_DIV` 25) | ≈ $1.3M net per dealer-month, 1–3 units per dealer × SKU × year |
| Money | **never** the TPC-DS dollar columns; the row's own sales/list ratio is kept as a discount (clamped 0.55–1.00) and applied to the re-skinned `LIST_PRICE_CENTS` | net ≈ $420/unit, margin ≈ 22% of net (floored at 0, capped at 55% — same rule as the SQLite seed) |
| DC inventory | `INV_QUANTITY_ON_HAND` 0..1000 → 0..10 (`INV_DIV` 100) | matched to re-skinned demand; MRP produces a real mix of shortage / expedite / de-expedite / cancel |
| Dealer on-hand | derived from the dealer's trailing demand (15% stocked out, else 1–6 months of average demand) | DC stock is corporate, not apportioned to dealers |

The full 56.9B-row share is still scanned every build (date-pruned to 24 of 60 months) — sampling happens after the read, which is what keeps the "runs against 10 TB" claim honest while producing dealer-sized numbers.

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

`all` runs the whole chain. Flags: `--scale 0.1` for a cheap smoke build (200K POs), `--demo-dealers N` for the dealer×SKU scope, `--sample-mod N` for the volume re-skin (default 200), `--build-timeout` (default 5400 s).

### Cost — measured (LARGE = 8 credits/hour)

| Step | Work | Measured on AWS us-east-1, 2026-10-03 |
| --- | --- | --- |
| backbone | dimension merges + one pass over inventory (783M rows) | 0.3–0.4 min |
| generate | GENERATOR tables at scale 1.0 (2M POs, 8M lines, 1.6M BOM) | 1.1 min |
| build | scoped extract + grouping-sets pass over store/catalog/web sales (56.9B rows, date-pruned); 150M-row forecast; 5M-row MRP | 2.6–2.9 min (8.4 min before the volume sampling) |
| whole session | first run + 6 calibration rebuilds | **7.9 credits** on `AQ_VC_BUILD_WH`, 0.3 on the XSMALL serve warehouse |

A single clean `all` run is therefore ~1 credit. Serving: XSMALL, auto-suspend 60 s; `/api/analytics` (≈40 governed queries, 6-way fan-out) completes in ~10 s; single metrics 0.3–2 s.

`cloud.py` suspends `AQ_VC_BUILD_WH` after each heavy step. Nothing in this repo creates a resource monitor; add one at the account level if you want a hard cap (`CREATE RESOURCE MONITOR ... CREDIT_QUOTA=20 ... SUSPEND_IMMEDIATE`).

### Admin steps that are deliberately *not* scripted

```sql
GRANT ROLE AQ_VC_READER TO USER <reader_user>;
INSERT INTO VC_RETAIL_DEMO.GOVERNANCE.USER_DEALERS VALUES ('<reader_user>', '*');   -- or 'DLR-0001'
```

## Reader access

Grant `AQ_VC_READER` to the reader principal and insert `CURRENT_USER()` → `DLR-0001` (or `*`) into `GOVERNANCE.USER_DEALERS`. Dealer-keyed views (facts, monthly, dealers, quarantine, gold channel/family, rep assignments) are row-filtered. Corporate supply-chain views (POs, inventory, MRP, BOM, vendors) are not dealer-keyed — any reader with the role sees them.

```sh
python3 -m app.server --backend snowflake --connection aq_vc_reader       # Snowflake only
python3 -m app.server --enable-snowflake --connection aq_vc_reader        # SQLite default + header toggle
```

### Backend toggle (hosted demo)

With both backends open the header shows **SQLite | Snowflake · 10 TB**. The choice is per browser session (HttpOnly `vc_backend` cookie, 12 h), requires a demo login, and runs the same governed SQL either way — only the `Store` behind it changes. `POST /api/backend` proves the target answers (`SELECT … FROM dealers LIMIT 1`, which also resumes the warehouse) before it sets the cookie; it returns 409 if that backend is not configured on the host and 503 if it did not respond, leaving the session where it was. A forged cookie naming an unavailable backend is ignored. `/api/health` reports `backend`, `backends_available` and a `data_scale` sentence the UI shows under the badge.

On a host, credentials come from the environment instead of `connections.toml`: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PAT` (+ optional `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`). The hosted demo uses a dedicated `TYPE = SERVICE` user that holds only `AQ_VC_READER`, a PAT restricted to that role, and a `'*'` row in `GOVERNANCE.USER_DEALERS`. Setup steps are in `docs/HOSTING.md`. Dealer scoping for `dlr-0001`/`dlr-0002` sessions is still applied by the app's SQL on both backends; the RAP is defense-in-depth on the Snowflake principal.

On Snowflake the app keeps one authenticated connection, runs `/api/analytics` with a 6-way fan-out, and uses the `snowflake` SQL dialect: `inventory_trend`, `dc_inventory_health`, `forecast_accuracy`, `mrp_exceptions`, `vendor_scorecard` read Gold-backed `SERVING.GOLD_*` views (see `app/supply_chain.py: SNOWFLAKE_OVERRIDES`). Everything else runs the same governed SQL as SQLite against same-named SERVING views.

Cortex (optional): set `SNOWFLAKE_ACCOUNT` (or `SNOWFLAKE_HOST`) + `SNOWFLAKE_PAT`, then `python3 -m scripts.cortex "What is net sales by channel?"` (add `--semantic-view VC_RETAIL_DEMO.SERVING.VC_SUPPLY_SEMANTICS` for procurement questions). The client prints the interpretation and the generated `SEMANTIC_VIEW(...)` SQL and does not execute it.

## Status — built and verified (2026-10-03)

Run end-to-end against a Snowflake Enterprise account on AWS us-east-1 (a "CoCo for Developers" account created for this demo; no RELIEF_DEMO objects touched). Evidence in `docs/evidence/`:

- `snowflake_doctor.txt` — account, role, 24 TPC-DS SF10TCL tables visible.
- `snowflake_validate.txt` — layer counts (facts 1.65M, monthly 653K, POs 2M, PO lines 8M, inventory 65.3M, forecast 150.75M, MRP 5.0M, BOM 1.6M), channel totals, backbone 2.63 TB / 56.9B rows, quarantine mix, four integrity checks all 0.
- `reconcile.json` — the 396 event-sourced facts in Snowflake match the local SQLite seed exactly (`event_subset_vs_local_*` = 0.0).

Calibration verified through the app on the reader role: rep attainment median 98–102% (P10–P90 83–121%), PO past-due 20% median, vendor OTIF 38–95% across Prefer/Watch/Exit tiers, forecast bias ±12% by family, MRP exceptions in all four codes, margin ≈ 22% of net, dealer-scoped session (`dlr-0001`) row-filtered by the RAP.

Hosted toggle verified the same day on the Fly deployment: `/api/health` lists both backends; switching an operator session to Snowflake warmed in 4.3 s (XSMALL resume), `/api/summary` answered in 1.6 s with 1,645,231 SKUs / 1,500 dealers / $1.64 B net, the full `/api/analytics` overview in 4.4 s, and switching back restored the 396-SKU SQLite seed. The hosted principal is a second Snowflake user (`VC_FLY_SVC`, service type, reader role only): before its `USER_DEALERS` row existed it saw 0 dealers through the RAP, after the `'*'` row all 1,500 — the policy filters by principal as designed. Dealer-pinned principal (`rap_dual_principal.txt`): a third user `VC_DLR0001_SVC` (service type, `AQ_VC_READER` only) mapped to `DLR-0001` sees exactly 1 dealer, 49,096 facts, 518 monthly rows, 21 gold rows, 1 rep assignment, 1,328 quarantine rows where the `'*'` owner sees 1,500 / 1.65 M / 653 K / 941 / 1,799 / 37 K; a direct `WHERE DEALER_ID='DLR-0002'` returns 0 rows; `USE ROLE ACCOUNTADMIN` and reading `GOVERNANCE.USER_DEALERS` are denied. Corporate views (2 M purchase orders) are visible to both, as documented. The token used for the run was a 1-day PAT, removed at the end.

Cortex Analyst (`cortex_analyst.txt`): `POST /api/v2/cortex/analyst/message` with a PAT bearer on the dealer-pinned principal, against both semantic views. Three questions ("net sales and margin percent by channel", "five families with most units on hand", "open PO value by vendor country") each came back in 3.3–4.7 s with an interpretation and a `SEMANTIC_VIEW(...)` query. Cortex only generates SQL; the run executed each statement as both principals. Retail answers differ by principal (DLR-0001: Trade $34.6 M, 22.08 % margin; unrestricted: Trade $924 M, 22.15 %) — the RAP applies through the semantic view — while the supply answer is identical for both because procurement is corporate scope. `scripts/cortex.py` is the client (prints SQL, never executes).

What is still not demonstrated: Openflow ingestion (the loader is staged Python), and Cortex Analyst wired into the app UI (the runtime assistant remains the deterministic router by design).
