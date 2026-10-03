# Known limitations

- Synthetic dealers/SKUs only; no Visual Comfort production data or credentials.
- Offline assistant is a verified FAQ + metric router, not an LLM.
- Today panel reconstructs the **public support pattern** (FAQ / form / phone). It is not a clone of VC’s third-party chat vendor UI.
- Public URL uses Cloudflare Access (email OTP allowlist). Invite guests with `scripts/cf_access_guests.py`.
- Hard-refresh after Access login if the Analytics UI looks like plain TSV (cached assets).
- Snowflake RAP on PRODUCTS is view-grant only (no dealer key on catalog).
- Staged `scripts.cloud load` is not Openflow.
- Cortex path requires account features + PAT; untested until live evidence is captured under `docs/evidence/`.
- Default SQLite seed (~50 dealers × 200 SKUs) proves behavior, not enterprise throughput. Scale lives in Snowflake: the "10 TB" is the TPC-DS SF10TCL *scale factor* (56.9B rows; 2.63 TB as Snowflake stores it compressed), shared and zero-copy, not generated VC data. The generated sales-org / procurement / MRP layer is ~1.5 GB.
- The Snowflake backbone is a re-skin of a general-merchandise retailer: volume is sampled 1-in-200 and quantities rescaled so a dealer looks like a lighting dealer, and money is derived from the re-skinned list price × the row's own discount, not from TPC-DS dollar columns. Seasonality (strong Q4/Q3 peaks) is TPC-DS's, not Visual Comfort's.
- Snowflake build verified on one account (AWS us-east-1, Enterprise). Cortex Analyst and dual-principal RAP isolation are not yet demonstrated there.
- On Snowflake, `SILVER.FACTS` keeps dealer × SKU grain only for the 50 demo dealers; the other 1,450 dealers exist at monthly family/channel grain (`SILVER.MONTHLY`, `GOLD.CHANNEL_FAMILY_ALL`). `silver_monthly.sku_id` is NULL on Snowflake.
- Corporate supply-chain views (POs, inventory, MRP, BOM, vendors) are not dealer-keyed; dealer sessions see corporate supply data. `vendor_scorecard` on Snowflake ignores dealer scope (Gold is global).
- Snowflake-mode `/api/analytics` runs ~40 governed queries (6-way fan-out); expect 10–30 s on XSMALL, not the sub-second SQLite experience.
- Always-on host is Fly.io + named tunnel; local `share_private.sh` is fallback only.
