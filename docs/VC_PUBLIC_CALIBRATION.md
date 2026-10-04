# Calibrating the synthetic data to Visual Comfort's public scale

The Snowflake build re-skins Snowflake's shared TPC-DS 10 TB retail dataset into a lighting business. Until 2026-10-03 the
re-skin was sized to "a lighting dealer" and summed to a company ~57× larger than Visual Comfort & Co. This note records
the public figures the build is now calibrated to, how each knob was derived, and what the build measures after the
rebuild. **Everything in the data remains synthetic.** No Visual Comfort data, systems or people were used; the only
inputs are the third-party public figures below, and they are estimates about a private company.

## Public anchors

| Anchor | Public figure | Source (accessed 2026-10-03) | Used for |
| --- | --- | --- | --- |
| Revenue | Estimates range from **$284M** (Kona Equity) and **$458M** (Growjo) to **~$750M** (Decorstly). The 2021 recapitalization valued the company at **~$2.2B** with $1.17B of term debt; at typical leverage that implies EBITDA near $180M and revenue in the high hundreds of millions. | Kona Equity; Growjo; Decorstly; S&P Global Ratings research update 2021-06-17; Leonard Green & Partners press release 2021-06-08 | Target net revenue **≈ $750M / yr** |
| Outbound volume | **12,000–15,000 cartons/day** company-wide; Houston DC **3,500–4,000/day**; **four US DCs**, main in Houston | Peak Technologies case study ("Visual Comfort – Managed Mobility Services") | **3.0M units/yr** (≈ 1.3 cartons/unit); **4 DCs**, Houston **~30%** |
| Locations | **75 locations** listed (72+ US showrooms incl. trade-market showrooms and a Houston outlet, 2 in England, 1 in China); 7 in Florida, 3 in Massachusetts; 2025–26 openings | Lighting News Now 2026-08-17; PR Newswire showroom announcements | **75 company-showroom accounts** |
| Dealer network | Sold through authorized dealer showrooms, national e-tailers (Lumens, 1-800-Lighting, Capitol Lighting, LuxeDecor named), electrical distributors for the popular-priced Generation Lighting lines | Decorstly comparison article; Generation Brands company profile | Tiers: **25 e-tailers, 200 distributors, 1,200 independent dealers** |
| Headcount | **~1,540 employees** (Q4 2025), **+26 % 2023→2026**; 87 % North America | Revelio Labs | **120 account reps** (~8 %); **8 %/yr** growth trend for quotas |
| Catalog | One dealer lists **9,880 items in 2,834 groups** for the Signature collection alone; six collections (Signature, Modern, Studio, Architectural, Fan, Generation Lighting) | LUCE Lighting dealer listing; visualcomfort.com | **~31K SKUs** (1 in 13 TPC-DS items) |
| Sourcing | Fans imported from Taiwan (2024 recall notice names Visual Comfort & Co., Skokie IL as importer); staff in China, Vietnam, India, Brazil; Italian glass; Houston finish workshop | CPSC recall notice via whomakethis.com; Revelio/LinkedIn workforce geography | Vendor countries **CN 30 / VN 15 / US 15 / IN 10 / IT 10 / TW 10 / PH 5 / MX 5 %** |
| Price points | Dealer listings show list prices from a few hundred dollars (Generation Lighting from ~$80) to $1,000+ sconces and multi-thousand-dollar chandeliers; dealers discount ~30 % | visualcomfortlightingstore.com listings (e.g. list $990 → $693) | List price p50 ≈ $200 unit-weighted, tail to ~$3K; realization bands below |

Not public, therefore **assumed** (and labelled as such in the data): the other three DC locations (the SQLite seed's
Ontario CA / Columbus OH / Edison NJ), gross margin (45–50 %, consistent with the leverage above), channel realization
bands, the Trade / Contract / Consumer mix, vendor count (72), and PO cadence.

## Derivation of the knobs (`scripts/cloud.py: VC_PUBLIC`)

| Knob | Value | Derivation |
| --- | --- | --- |
| `ITEM_MOD` | 13 | 402,200 TPC-DS items / 13 ≈ 30.9K SKUs |
| List price | `70 + 32 × I_CURRENT_PRICE` | TPC-DS price p50 ≈ 4.2 → list p10/50/90/99 ≈ $99 / $203 / $442 / $2,978. Unit-weighted: the popular-priced lines carry the units |
| Cost | 26–40 % of list | wholesale realization 50–65 % of list ⇒ gross margin ≈ 47 % |
| Realization (`DISC_RATIO`) | Trade 0.50–0.65, Contract 0.55–0.75, Consumer 0.80–1.00 of list | dealer wholesale, project pricing, company showroom / web near list; the row's TPC-DS sales/list ratio picks the point in the band |
| `KEEP_PPM_*` | showroom 17,100 · e-tailer 7,600 · distributor 1,900 · dealer 570 | a TPC-DS store carries ~1.05M raw units/yr after the item filter; keep-rates give ~18K / 8K / 2K / ~600 units per account-year (≈ $4.5M / $2M / $0.5M / $150K), independents log-uniform ×0.2–×5 for the long tail, other tiers ×0.4–×2.5 |
| `W_TRADE / W_CONTRACT / W_CONSUMER` | per tier | e-tailers skew Consumer (web), distributors Contract, showrooms Consumer+Trade, independents Trade |
| `INV_DIV` | 250 | 25 TPC-DS warehouses rolled up 8/6/6/5 into 4 DCs, divided so total DC stock ≈ 90 days of cover |
| DC `WEIGHT` | TX 0.32 · CA 0.24 · OH 0.24 · NJ 0.20 | Houston ~28–33 % of cartons; weights drive forecast and on-order allocation |
| `REP_COUNT` | 100 (+20 seed = 120) | ~8 % of ~1,540 staff; ~10 accounts per rep median |
| `PO_ROWS` | 18,000 | ≈ $390M/yr purchases (COGS ≈ 52 % of net) at ~$21K per PO; ~250 POs per vendor-year |
| `GROWTH` | 1.08 | headcount +26 % over three years; applied to quotas centred on the trailing-4-quarter midpoint |
| `--volume-scale` | 1.0 | multiplies every `KEEP_PPM` and `PO_ROWS`; 2.0 ≈ a $1.5B company |

## Measured after rebuild (2026-10-03, `docs/evidence/vc_calibration.txt`)

| Metric | Target | Measured |
| --- | --- | --- |
| Net revenue, trailing 12 months | ≈ $750M | **$753.0M** (+$16M event-sourced seed facts in `SILVER.FACTS` → $769M) |
| Units / yr | ≈ 3.0M | **3.04M** ($248 / unit) |
| Gross margin | 45–50 % | **47.4 %** |
| Company showrooms | 75, ~$4–5M each | 75 · **$346M** total · median $3.6M (range $1.1M–$16.7M) |
| E-tailers / distributors / independents | 25 / 200 / 1,200 | $66M (median $2.1M) / $100M (median $384K) / $240M (median $96K, $2K–$1.2M) |
| Channel mix | Trade-led | Trade 49 % · Consumer 32 % · Contract 19 % |
| SKUs | tens of thousands | **30,923** backbone SKUs, 20,615 sold in the last 12 months |
| DCs | 4, Houston ~30 % | 4 · on-hand share **TX 32.0 / OH 24.1 / CA 23.9 / NJ 20.0 %**; forecast split identical; **88 days of cover** |
| Purchasing | ≈ COGS | **$389M** ordered / yr · 18,000 POs · inbound **8.3K cartons/day** · 14 % of open POs past due |
| Vendors | overseas-weighted | 72 · CN 19, US 13, VN 9, IT 7, TW 7, IN 6, PH 3 … · OTIF p10/50/90 = 38 / 59 / 87 % |
| Sales org | ~120 reps | 120 · 3 / 10 / 38 accounts per rep · book p10/50/90 = $0.6M / $4.4M / $16.3M · attainment Q3 p10/50/90 = 88 / 99 / 127 %, Q2 = 91 / 106 / 127 % |
| Forecast | unbiased in total, ±12 % by family | bias by family −9.3 … +9.2 %, centred |
| MRP | all codes present | none 31.0K · expedite 19.2K · shortage 4.2K · cancel 3.3K · de-expedite 3.2K · excess 0.9K |
| Integrity | 0 | PO lines without PO 0 · facts with unknown dealer 0 · margin > sales 0 · dealers without rep 0 · forecast split drift 0 |
| Parity | exact | event-sourced subset = local SQLite seed (0.0 / 0.0) |
| Cost | — | three full rebuilds ≈ 3.0 credits on the LARGE build warehouse (≈ 1 credit per build) |

## What changed structurally

- `SILVER.FACTS` now keeps dealer × SKU grain for **all 1,500 accounts** (1.21M rows), not 50 demo dealers — the
  calibrated volume is small enough. `GOLD.CHANNEL_FAMILY` and `GOLD.CHANNEL_FAMILY_ALL` therefore agree.
- `BRONZE.DEALER_TIER` (and `SERVING.DEALER_TIERS`, row-access-policied) carries the tier, keep-rate and channel weights.
- `BRONZE.DISTRIBUTION_CENTERS` is a fixed 4-row table with `WEIGHT`; `BRONZE.WAREHOUSE_DC` maps the 25 TPC-DS
  warehouses onto it.
- The trailing-12-month window is now exactly 12 calendar months (it was 13: `-12 months` from a month-end).
- The full 56.9B-row share is still scanned on every build (date-pruned to 24 months); sampling happens after the read.

## Caveats

- These are third-party estimates about a private company; the revenue band alone spans $284M–$750M. The build sits at
  the top of that band because the 2021 transaction value supports it. `--volume-scale 0.5` reproduces the low end.
- Seasonality is TPC-DS's (Q3/Q4-heavy), not Visual Comfort's.
- The SQLite seed (50 dealers × 200 SKUs, $16M) is unchanged; it proves behaviour, not scale.
