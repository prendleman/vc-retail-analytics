# Architecture

## Two execution paths

Local: synthetic dealer + catalog + sale/inventory events → immutable SQLite Bronze → validation → Silver current facts → Gold aggregates → browser + governed metric API + FAQ/catalog assistant.

AQ cloud: staged Python loader (not Openflow) → VARIANT Bronze → Snowflake normalization views → Silver/Gold → secure serving views with dealer row policy → external app / semantic view / Cortex.

## Grain and keys

- Dealer (tenant): one row per synthetic dealer/showroom (`DLR-####`).
- Product: one row per SKU in `products`.
- Event: globally unique `event_id`; immutable `(dealer_id, source_id, version)`.
- Silver fact: one latest valid row per `(dealer_id, sku_id)` for current inventory + trailing sell-through (includes `rep_id`, `cost_cents`).
- Monthly facts: 24-month synthetic series per dealer×SKU for seasonality.
- Dims: territories, salespeople, vendors (+ vendor KPI rollup), distribution centers.
- Sales org: `rep_assignments` (dealer → rep with start/end month history), `rep_quotas` (rep × quarter, calibrated to actuals).
- Procurement: `vendor_contracts`, `purchase_orders` → `po_lines`, `shipments` (mode, ETA, arrival, freight), `receipts` (qty received / defective). OTIF is computed from receipts vs promised dates, not stored.
- Inventory: `inventory_snapshots` weekly by DC × SKU (on-hand, on-order, allocated, in-transit).
- MRP: `components` + `bom` (parent SKU → component × qty), `demand_forecast` (month × DC × SKU), `mrp_plan` (latest run: net requirement, planned order, release/due, exception code), `work_orders` for assembled families.
- Gold: channel × region × family aggregates; on Snowflake also weekly DC inventory, forecast by family-month, MRP exception summary, vendor scorecard.
- Quarantine: every invalid event version (and, on Snowflake, invalid backbone source rows for the scoped dealers).

## Same schema, two scales

The SQLite seed and the Snowflake SERVING schema share table names and lowercase column names, so one set of governed metric SQL (`app/core.py`, `app/supply_chain.py`) runs on both. SQLite holds ~50 dealers × 200 SKUs; Snowflake re-skins the shared 10 TB TPC-DS dataset as the sales/inventory backbone and generates the sales-org / procurement / MRP layer on top (`sql/snowflake/06–08`). Heavy metrics switch to Gold-backed views via the `snowflake` dialect in `metric_sql`. See `docs/SNOWFLAKE.md`.

## Quality policy

Reject missing required fields, negative money/units, unknown channel/family, margin exceeding net sales, unknown dealer/SKU. Invalid newest event suppresses the published fact until a corrected higher version arrives.

## Security and AI

No real PII. Offline assistant is a verified metric + FAQ router (not an LLM). Cortex path (optional) uses the semantic view and does not auto-run arbitrary model SQL. Dealer scope comes from authenticated session, never model-selected identity.

## Chatbot improvement angle

See docs/CHATBOT_GAP.md. Production site support is phone/email/form (+ third-party chat per privacy policy). Demo Proposed assistant grounds product policy in synthetic FAQ/catalog and retail answers in warehouse metrics with tool traces.
