# Known limitations

- Synthetic dealers/SKUs only; no Visual Comfort production data or credentials.
- Offline assistant is a verified FAQ + metric router, not an LLM.
- Today panel reconstructs the **public support pattern** (FAQ / form / phone). It is not a clone of VC’s third-party chat vendor UI.
- Public URL uses Cloudflare Access (email OTP allowlist). Invite guests with `scripts/cf_access_guests.py`.
- Hard-refresh after Access login if the Analytics UI looks like plain TSV (cached assets).
- Snowflake RAP on PRODUCTS is view-grant only (no dealer key on catalog).
- Staged `scripts.cloud load` is not Openflow.
- Cortex Analyst is demonstrated as a CLI/REST path (`scripts/cortex.py`, evidence `docs/evidence/cortex_analyst.txt`), not wired into the app UI; the runtime assistant stays a deterministic router. Cortex generates SQL only — execution and the row access policy happen in the caller's session.
- Default SQLite seed (~50 dealers × 200 SKUs) proves behavior, not enterprise throughput. Scale lives in Snowflake: the "10 TB" is the TPC-DS SF10TCL *scale factor* (56.9B rows; 2.63 TB as Snowflake stores it compressed), shared and zero-copy, not generated VC data. The generated sales-org / procurement / MRP layer is ~1.5 GB.
- The Snowflake backbone is a re-skin of a general-merchandise retailer, sized to Visual Comfort's *public* scale (~$750M/yr, 3M units, 75 showrooms + dealer network, ~31K SKUs, 4 DCs — `docs/VC_PUBLIC_CALIBRATION.md`). Those anchors are third-party estimates about a private company (revenue estimates alone span $284M–$750M); gross margin, channel mix, realization bands and three of the four DC locations are assumptions. Money is derived from the re-skinned list price × a channel realization band, never from TPC-DS dollar columns. Seasonality (strong Q4/Q3 peaks) is TPC-DS's, not Visual Comfort's.
- Snowflake build verified on one account (AWS us-east-1, Enterprise). RAP is demonstrated on three principals (owner `'*'`, hosted service user `'*'`, and a service user pinned to `DLR-0001`); Openflow ingestion is not demonstrated.
- Hosted toggle: Snowflake is opt-in per browser session (header switch, login required); the default stays SQLite. The first switch resumes the XSMALL warehouse (~4–5 s); it auto-suspends after 60 s idle, so a reviewer who flips, waits, and returns pays that again. One shared reader connection per host; many concurrent Snowflake sessions queue on it.
- On Snowflake, `SILVER.MONTHLY` is dealer × family × channel × month grain, so `silver_monthly.sku_id` is NULL there (dealer × SKU grain lives in `SILVER.FACTS`, trailing 12 months, all 1,500 accounts).
- Corporate supply-chain views (POs, inventory, MRP, BOM, vendors) are not dealer-keyed; dealer sessions see corporate supply data. `vendor_scorecard` on Snowflake ignores dealer scope (Gold is global).
- Snowflake-mode `/api/analytics` runs ~40 governed queries (6-way fan-out); expect 10–30 s on XSMALL, not the sub-second SQLite experience.
- Always-on host is Fly.io + named tunnel; local `share_private.sh` is fallback only.
