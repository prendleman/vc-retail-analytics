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
- Dims: territories, salespeople, vendors (+ vendor KPI rollup).
- Gold: channel × region × family aggregates.
- Quarantine: every invalid event version.

## Quality policy

Reject missing required fields, negative money/units, unknown channel/family, margin exceeding net sales, unknown dealer/SKU. Invalid newest event suppresses the published fact until a corrected higher version arrives.

## Security and AI

No real PII. Offline assistant is a verified metric + FAQ router (not an LLM). Cortex path (optional) uses the semantic view and does not auto-run arbitrary model SQL. Dealer scope comes from authenticated session, never model-selected identity.

## Chatbot improvement angle

See docs/CHATBOT_GAP.md. Production site support is phone/email/form (+ third-party chat per privacy policy). Demo Proposed assistant grounds product policy in synthetic FAQ/catalog and retail answers in warehouse metrics with tool traces.
