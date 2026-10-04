-- 10 TB backbone: re-skin SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL (shared, zero storage cost) as the
-- VC lighting-retail universe. Nothing is copied here except small dimension tables; sales and
-- inventory stay in the share and are read by 08_silver_gold.sql.
--
-- Mapping (documented in docs/SNOWFLAKE.md; scale targets in docs/VC_PUBLIC_CALIBRATION.md):
--   store (1,500)            -> dealers           DLR-0001..DLR-1500 (first 50 = loaded synthetic dealers), tiered
--                               showroom / etailer / distributor / dealer with per-dealer volume (BRONZE.DEALER_TIER)
--   item (402,200)           -> products          1 in {{ITEM_MOD}} kept -> ~31K SKUs (family/designer/finish/lead band re-skinned)
--   warehouse (25)           -> 4 distribution centers (Houston main) via BRONZE.WAREHOUSE_DC
--   store_sales              -> Trade channel     catalog_sales -> Contract     web_sales -> Consumer
--   inventory (weekly)       -> inventory_snapshots (DC x SKU x week)
--   date_dim                 -> shifted +{{YEAR_SHIFT}} years so 2000-10..2002-09 lands on the demo window
USE DATABASE VC_RETAIL_DEMO;
USE WAREHOUSE {{BUILD_WH}};
ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS={{BUILD_TIMEOUT}};
ALTER SESSION SET QUERY_TAG='aq-vc-retail-backbone';

-- Guard: the share must exist in this account.
SELECT COUNT(*) AS TPCDS_TABLES FROM SNOWFLAKE_SAMPLE_DATA.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='TPCDS_SF10TCL';

-- Calendar: TPC-DS dates shifted into the demo window. Demo "today" = {{AS_OF}}.
CREATE OR REPLACE TABLE BRONZE.CALENDAR AS
SELECT D_DATE_SK AS DATE_SK,
       DATEADD(year, {{YEAR_SHIFT}}, D_DATE) AS CAL_DATE,
       TO_VARCHAR(DATEADD(year, {{YEAR_SHIFT}}, D_DATE), 'YYYY-MM') AS MONTH,
       TO_VARCHAR(DATEADD(year, {{YEAR_SHIFT}}, D_DATE), 'YYYY-MM-DD') AS ISO_DATE
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.DATE_DIM
WHERE DATEADD(year, {{YEAR_SHIFT}}, D_DATE) BETWEEN DATEADD(month, -24, '{{AS_OF}}'::DATE) AND '{{AS_OF}}'::DATE;

-- Region from state (synthetic rollup).
CREATE OR REPLACE FUNCTION BRONZE.REGION_OF(STATE VARCHAR) RETURNS VARCHAR AS
$$
CASE
  WHEN STATE IN ('CA','WA','OR','NV','AZ','CO','UT','ID','MT','WY','NM','AK','HI') THEN 'West'
  WHEN STATE IN ('IL','OH','MI','IN','WI','MN','IA','MO','KS','NE','SD','ND') THEN 'Midwest'
  WHEN STATE IN ('NY','NJ','PA','MA','CT','RI','VT','NH','ME','MD','DE','DC') THEN 'Northeast'
  ELSE 'South'
END
$$;

-- Territories: one per state present in the store dimension (plus loaded synthetic territories remain).
MERGE INTO BRONZE.TERRITORIES t USING (
  SELECT 'TER-' || COALESCE(S_STATE,'XX') AS TERRITORY_ID,
         COALESCE(S_STATE,'Unassigned') || ' territory' AS NAME,
         BRONZE.REGION_OF(S_STATE) AS REGION,
         CEIL(COUNT(*) * 1.15) AS CAPACITY_DEALERS
  FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.STORE GROUP BY S_STATE
) s ON t.TERRITORY_ID = s.TERRITORY_ID
WHEN NOT MATCHED THEN INSERT (TERRITORY_ID, NAME, REGION, CAPACITY_DEALERS) VALUES (s.TERRITORY_ID, s.NAME, s.REGION, s.CAPACITY_DEALERS);

-- Dealers: store -> dealer. Loaded synthetic dealers (DLR-0001..0050) keep their rows; the rest are inserted.
MERGE INTO BRONZE.DEALERS t USING (
  SELECT 'DLR-' || LPAD(S_STORE_SK, 4, '0') AS DEALER_ID,
         COALESCE(INITCAP(S_STORE_NAME), 'Store') || ' Lighting Studio ' || LPAD(S_STORE_SK, 4, '0') AS NAME,
         BRONZE.REGION_OF(S_STATE) AS REGION,
         CASE MOD(S_STORE_SK, 3) WHEN 0 THEN 'Consumer' WHEN 1 THEN 'Trade' ELSE 'Contract' END AS CHANNEL_FOCUS,
         COALESCE(S_CITY, 'Unknown') AS CITY,
         'TER-' || COALESCE(S_STATE,'XX') AS TERRITORY_ID
  FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.STORE
) s ON t.DEALER_ID = s.DEALER_ID
WHEN NOT MATCHED THEN INSERT (DEALER_ID, NAME, REGION, CHANNEL_FOCUS, CITY, TERRITORY_ID)
  VALUES (s.DEALER_ID, s.NAME, s.REGION, s.CHANNEL_FOCUS, s.CITY, s.TERRITORY_ID);

-- Distribution centers: four US DCs with Houston as the main site (public: Peak Technologies case study — 4 DCs,
-- Houston ships 3.5-4K of the company's 12-15K cartons/day, ~28%). The other three are the SQLite seed's regional
-- DCs (assumed locations). WEIGHT drives forecast / on-order allocation; the 25 TPC-DS warehouses are mapped 8/6/6/5
-- so Houston carries ~32% of backbone inventory.
CREATE OR REPLACE TABLE BRONZE.DISTRIBUTION_CENTERS AS
SELECT * FROM VALUES
  ('DC-TX', 'Houston DC (main)', 'South',     'TX', 0.32),
  ('DC-CA', 'Ontario CA DC',     'West',      'CA', 0.24),
  ('DC-OH', 'Columbus DC',       'Midwest',   'OH', 0.24),
  ('DC-NJ', 'Edison DC',         'Northeast', 'NJ', 0.20) AS v(DC_ID, NAME, REGION, STATE, WEIGHT);
CREATE OR REPLACE TABLE BRONZE.WAREHOUSE_DC AS
SELECT W_WAREHOUSE_SK AS WAREHOUSE_SK,
       CASE WHEN MOD(W_WAREHOUSE_SK, 25) < 8 THEN 'DC-TX' WHEN MOD(W_WAREHOUSE_SK, 25) < 14 THEN 'DC-CA'
            WHEN MOD(W_WAREHOUSE_SK, 25) < 20 THEN 'DC-OH' ELSE 'DC-NJ' END AS DC_ID
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.WAREHOUSE;

-- Vendors: {{VENDOR_COUNT}} generated suppliers. Country mix is overseas-weighted to match what is public about the
-- sourcing base (fans imported from Taiwan per a 2024 recall notice; staff in China / Vietnam / India; Italian glass;
-- a US finish workshop): CN 30%, VN 15%, US 15%, IN 10%, IT 10%, TW 10%, PH 5%, MX 5%. Loaded VND-01..12 remain.
MERGE INTO BRONZE.VENDORS t USING (
  SELECT 'VND-' || LPAD(SEQ4() + 100, 3, '0') AS VENDOR_ID,
         ARRAY_CONSTRUCT('Foundry','Metals','Atelier','Glassworks','Diffusers','Brass Works','Coil & Wire','Timber Shade','Crystal','Optics','Lacquer Co','Castings')[MOD(SEQ4(), 12)]::VARCHAR
           || ' ' || ARRAY_CONSTRUCT('Pearl River','Hudson','Tuscan','Gulf Coast','Nordic','Pacific','Prairie','Andes','Levant','Ontario','Kyoto','Savannah','Delta','Cascade','Baltic')[MOD(SEQ4() * 7, 15)]::VARCHAR
           || ' ' || LPAD(SEQ4() + 100, 3, '0') AS NAME,
         ARRAY_CONSTRUCT('CN','CN','CN','CN','CN','CN','VN','VN','VN','US','US','US','IN','IN','IT','IT','TW','TW','PH','MX')[MOD(SEQ4() * 7, 20)]::VARCHAR AS COUNTRY
  FROM TABLE(GENERATOR(ROWCOUNT => {{VENDOR_COUNT}}))
) s ON t.VENDOR_ID = s.VENDOR_ID
WHEN MATCHED THEN UPDATE SET NAME = s.NAME, COUNTRY = s.COUNTRY
WHEN NOT MATCHED THEN INSERT VALUES (s.VENDOR_ID, s.NAME, s.COUNTRY);

-- Products: item -> SKU, keeping 1 in {{ITEM_MOD}} TPC-DS items (~31K SKUs; the public catalog is tens of thousands of
-- items across Signature / Modern / Studio / Architectural / Fan / Generation Lighting). List price re-scaled to a
-- unit-weighted lighting range (p10 ~$100, p50 ~$205, p90 ~$450, tail to ~$3K: the popular-priced lines carry the
-- unit volume; see docs/VC_PUBLIC_CALIBRATION.md). COST_CENTS is landed cost, 26-40% of list, so
-- gross margin on wholesale net (50-65% of list) lands at 45-50%.
-- Drop previous backbone SKUs (SKU-nnnnnn) so the item sample is idempotent; loaded seed SKUs (SKU-nnnn) stay.
DELETE FROM BRONZE.PRODUCTS WHERE LENGTH(SKU_ID) = 10;
CREATE OR REPLACE TABLE BRONZE.PRODUCTS_BACKBONE AS
WITH v AS (SELECT VENDOR_ID, ROW_NUMBER() OVER (ORDER BY VENDOR_ID) - 1 AS RN, COUNT(*) OVER () AS N FROM BRONZE.VENDORS)
SELECT 'SKU-' || LPAD(i.I_ITEM_SK, 6, '0') AS SKU_ID,
       ARRAY_CONSTRUCT('Marie Flanigan','Ralph Lauren','Julie Neill','Studio VC','Generation Lighting')[MOD(i.I_BRAND_ID, 5)]::VARCHAR
         || ' ' || ARRAY_CONSTRUCT('Ceiling','Wall','Lamps','Outdoor','Fans','Alabaster','Cordless')[MOD(i.I_ITEM_SK, 7)]::VARCHAR
         || ' ' || LPAD(i.I_ITEM_SK, 6, '0') AS NAME,
       ARRAY_CONSTRUCT('Ceiling','Wall','Lamps','Outdoor','Fans','Alabaster','Cordless')[MOD(i.I_ITEM_SK, 7)]::VARCHAR AS FAMILY,
       ARRAY_CONSTRUCT('Marie Flanigan','Ralph Lauren','Julie Neill','Studio VC','Generation Lighting')[MOD(i.I_BRAND_ID, 5)]::VARCHAR AS DESIGNER,
       ARRAY_CONSTRUCT('Antique Brass','Polished Nickel','Soft Brass','Alabaster','Matte Black')[MOD(ABS(HASH(i.I_COLOR)), 5)]::VARCHAR AS FINISH,
       (ROUND(70 + COALESCE(i.I_CURRENT_PRICE, 4) * 32) * 100)::NUMBER AS LIST_PRICE_CENTS,
       ARRAY_CONSTRUCT('in_stock','2_4_weeks','4_8_weeks','custom_overseas')[MOD(i.I_ITEM_SK, 4)]::VARCHAR AS LEAD_BAND,
       ROUND((ROUND(70 + COALESCE(i.I_CURRENT_PRICE, 4) * 32) * 100)
             * (0.26 + 0.14 * LEAST(1.0, GREATEST(0.0, COALESCE(i.I_WHOLESALE_COST / NULLIF(i.I_CURRENT_PRICE, 0), 0.5)))))::NUMBER AS COST_CENTS,
       v.VENDOR_ID,
       CASE MOD(i.I_ITEM_SK, 4) WHEN 0 THEN 4 WHEN 1 THEN 8 WHEN 2 THEN 12 ELSE 20 END AS SAFETY_STOCK,
       i.I_ITEM_SK AS ITEM_SK,
       -- price factor: converts TPC-DS dollars for this item into re-skinned dollars
       (ROUND(70 + COALESCE(i.I_CURRENT_PRICE, 4) * 32)) / NULLIF(COALESCE(i.I_CURRENT_PRICE, 4), 0) AS PRICE_FACTOR
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.ITEM i
JOIN v ON v.RN = MOD(COALESCE(i.I_MANUFACT_ID, i.I_ITEM_SK), v.N)
WHERE MOD(i.I_ITEM_SK, {{ITEM_MOD}}) = 0;

MERGE INTO BRONZE.PRODUCTS t USING (
  SELECT SKU_ID, NAME, FAMILY, DESIGNER, FINISH, LIST_PRICE_CENTS, LEAD_BAND, COST_CENTS, VENDOR_ID, SAFETY_STOCK FROM BRONZE.PRODUCTS_BACKBONE
) s ON t.SKU_ID = s.SKU_ID
WHEN NOT MATCHED THEN INSERT (SKU_ID, NAME, FAMILY, DESIGNER, FINISH, LIST_PRICE_CENTS, LEAD_BAND, COST_CENTS, VENDOR_ID, SAFETY_STOCK)
  VALUES (s.SKU_ID, s.NAME, s.FAMILY, s.DESIGNER, s.FINISH, s.LIST_PRICE_CENTS, s.LEAD_BAND, s.COST_CENTS, s.VENDOR_ID, s.SAFETY_STOCK);

-- Dealer -> DC assignment (same region, round-robin) used for dealer on-hand and inventory joins.
CREATE OR REPLACE TABLE BRONZE.DEALER_DC AS
WITH dc AS (SELECT DC_ID, REGION, ROW_NUMBER() OVER (PARTITION BY REGION ORDER BY DC_ID) - 1 AS RN, COUNT(*) OVER (PARTITION BY REGION) AS N FROM BRONZE.DISTRIBUTION_CENTERS),
     d AS (SELECT DEALER_ID, REGION, TRY_TO_NUMBER(SUBSTR(DEALER_ID, 5)) AS STORE_SK FROM BRONZE.DEALERS)
SELECT d.DEALER_ID, d.STORE_SK, dc.DC_ID,
       COUNT(*) OVER (PARTITION BY dc.DC_ID) AS DEALERS_IN_DC
FROM d JOIN dc ON dc.REGION = d.REGION AND dc.RN = MOD(COALESCE(d.STORE_SK, 0), dc.N);

-- Dealer tiers. Public shape of the account base: ~75 company locations (72 US showrooms + 2 England + 1 China,
-- incl. trade-market showrooms and an outlet), a handful of national e-tailers (Lumens, 1-800-Lighting, Capitol
-- Lighting, LuxeDecor are named publicly), electrical distributors for the popular-priced lines, and a long tail of
-- independent lighting showrooms. KEEP_PPM = parts-per-million of the raw TPC-DS ticket lines kept for the dealer,
-- which sets the dealer's annual volume (see docs/VC_PUBLIC_CALIBRATION.md for the derivation). Size within a tier
-- is log-uniform (x0.4..x2.5; independents x0.2..x5 for the long tail). W_* skew the channel mix per tier.
CREATE OR REPLACE TABLE BRONZE.DEALER_TIER AS
WITH d AS (
  SELECT DEALER_ID, ROW_NUMBER() OVER (ORDER BY DEALER_ID) AS RN, MOD(ABS(HASH(DEALER_ID || 'tier')), 1000) / 1000.0 AS U
  FROM BRONZE.DEALERS
), t AS (
  SELECT DEALER_ID, U,
         CASE WHEN RN <= {{SHOWROOM_COUNT}} THEN 'showroom'
              WHEN RN <= {{SHOWROOM_COUNT}} + {{ETAILER_COUNT}} THEN 'etailer'
              WHEN RN <= {{SHOWROOM_COUNT}} + {{ETAILER_COUNT}} + {{DISTRIBUTOR_COUNT}} THEN 'distributor'
              ELSE 'dealer' END AS TIER
  FROM d
)
SELECT DEALER_ID, TIER,
       ROUND({{VOLUME_SCALE}} * CASE TIER WHEN 'showroom' THEN {{KEEP_PPM_SHOWROOM}} WHEN 'etailer' THEN {{KEEP_PPM_ETAILER}}
                                          WHEN 'distributor' THEN {{KEEP_PPM_DISTRIBUTOR}} ELSE {{KEEP_PPM_DEALER}} END
             * IFF(TIER = 'dealer', POWER(10, -0.7 + 1.4 * U), POWER(10, -0.4 + 0.8 * U)))::NUMBER AS KEEP_PPM,
       CASE TIER WHEN 'showroom' THEN 0.96 WHEN 'etailer' THEN 0.44 WHEN 'distributor' THEN 0.90 ELSE 1.32 END AS W_TRADE,
       CASE TIER WHEN 'showroom' THEN 0.44 WHEN 'etailer' THEN 0.33 WHEN 'distributor' THEN 1.63 ELSE 0.61 END AS W_CONTRACT,
       CASE TIER WHEN 'showroom' THEN 2.27 WHEN 'etailer' THEN 4.40 WHEN 'distributor' THEN 0.09 ELSE 0.61 END AS W_CONSUMER
FROM t;

-- Channel focus follows the tier for the backbone dealers (loaded seed dealers DLR-0001..0050 keep theirs).
UPDATE BRONZE.DEALERS d
SET CHANNEL_FOCUS = CASE t.TIER WHEN 'showroom' THEN 'Consumer' WHEN 'etailer' THEN 'Consumer' WHEN 'distributor' THEN 'Contract' ELSE 'Trade' END
FROM BRONZE.DEALER_TIER t
WHERE t.DEALER_ID = d.DEALER_ID AND COALESCE(TRY_TO_NUMBER(SUBSTR(d.DEALER_ID, 5)), 0) > 50;

-- Unified sales view over the three TPC-DS channels, re-skinned and windowed (read in 08; not materialized here).
-- Re-skin rules (TPC-DS is a general-merchandise retailer; a lighting brand sells far fewer, pricier units):
--   * keep 1 in {{ITEM_MOD}} items, and per dealer keep KEEP_PPM x channel-weight parts-per-million of ticket lines
--     (hash of document + item, independent of the dealer residue so every dealer keeps sales);
--   * QTY 1..100 -> 1..4 (divide by {{QTY_DIV}});
--   * money is NOT taken from the TPC-DS dollar columns. The row's own sales/list ratio (0..1) is mapped into the
--     channel's realization band of the re-skinned list price — Trade (dealer wholesale) 0.50..0.65, Contract
--     (hospitality / designer projects) 0.55..0.75, Consumer (company showroom & web, near list) 0.80..1.00 — and
--     applied to LIST_PRICE_CENTS downstream. NET_PAID is kept only so NULL-field quarantine mirrors the source.
CREATE OR REPLACE VIEW BRONZE.BACKBONE_SALES AS
SELECT 'Trade' AS CHANNEL, dt.DEALER_ID, ss.SS_ITEM_SK AS ITEM_SK,
       c.MONTH, c.CAL_DATE,
       CASE WHEN ss.SS_QUANTITY IS NULL THEN NULL ELSE GREATEST(1, ROUND(ss.SS_QUANTITY / {{QTY_DIV}})) END AS QTY,
       ss.SS_NET_PAID AS NET_PAID,
       0.50 + 0.15 * LEAST(1.0, GREATEST(0.0, COALESCE(ss.SS_SALES_PRICE / NULLIF(ss.SS_LIST_PRICE, 0), 0.5))) AS DISC_RATIO,
       ss.SS_TICKET_NUMBER AS DOC_NO
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.STORE_SALES ss
JOIN BRONZE.CALENDAR c ON c.DATE_SK = ss.SS_SOLD_DATE_SK
JOIN BRONZE.DEALER_TIER dt ON dt.DEALER_ID = 'DLR-' || LPAD(ss.SS_STORE_SK, 4, '0')
WHERE MOD(ss.SS_ITEM_SK, {{ITEM_MOD}}) = 0
  AND MOD(ABS(HASH(ss.SS_TICKET_NUMBER, ss.SS_ITEM_SK)), 1000000) < dt.KEEP_PPM * dt.W_TRADE
UNION ALL
SELECT 'Contract', dt.DEALER_ID, cs.CS_ITEM_SK,
       c.MONTH, c.CAL_DATE,
       CASE WHEN cs.CS_QUANTITY IS NULL THEN NULL ELSE GREATEST(1, ROUND(cs.CS_QUANTITY / {{QTY_DIV}})) END,
       cs.CS_NET_PAID,
       0.55 + 0.20 * LEAST(1.0, GREATEST(0.0, COALESCE(cs.CS_SALES_PRICE / NULLIF(cs.CS_LIST_PRICE, 0), 0.5))),
       cs.CS_ORDER_NUMBER
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.CATALOG_SALES cs
JOIN BRONZE.CALENDAR c ON c.DATE_SK = cs.CS_SOLD_DATE_SK
JOIN BRONZE.DEALER_TIER dt ON dt.DEALER_ID = 'DLR-' || LPAD(MOD(cs.CS_ORDER_NUMBER, 1500) + 1, 4, '0')
WHERE MOD(cs.CS_ITEM_SK, {{ITEM_MOD}}) = 0
  AND MOD(ABS(HASH(cs.CS_ORDER_NUMBER, cs.CS_ITEM_SK)), 1000000) < dt.KEEP_PPM * dt.W_CONTRACT
UNION ALL
SELECT 'Consumer', dt.DEALER_ID, ws.WS_ITEM_SK,
       c.MONTH, c.CAL_DATE,
       CASE WHEN ws.WS_QUANTITY IS NULL THEN NULL ELSE GREATEST(1, ROUND(ws.WS_QUANTITY / {{QTY_DIV}})) END,
       ws.WS_NET_PAID,
       0.80 + 0.20 * LEAST(1.0, GREATEST(0.0, COALESCE(ws.WS_SALES_PRICE / NULLIF(ws.WS_LIST_PRICE, 0), 0.5))),
       ws.WS_ORDER_NUMBER
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.WEB_SALES ws
JOIN BRONZE.CALENDAR c ON c.DATE_SK = ws.WS_SOLD_DATE_SK
JOIN BRONZE.DEALER_TIER dt ON dt.DEALER_ID = 'DLR-' || LPAD(MOD(ws.WS_ORDER_NUMBER, 1500) + 1, 4, '0')
WHERE MOD(ws.WS_ITEM_SK, {{ITEM_MOD}}) = 0
  AND MOD(ABS(HASH(ws.WS_ORDER_NUMBER, ws.WS_ITEM_SK)), 1000000) < dt.KEEP_PPM * dt.W_CONSUMER;

-- Weekly inventory snapshots (TPC-DS inventory is weekly) for the last {{INV_WEEKS}} weeks: DC x SKU x week.
-- The 25 TPC-DS warehouses roll up to the 4 DCs; on-hand is divided by {{INV_DIV}} so total stock lands near
-- ~90 days of cover against the re-skinned demand.
CREATE OR REPLACE TABLE BRONZE.INVENTORY_BACKBONE CLUSTER BY (SNAPSHOT_WEEK, DC_ID) AS
WITH weeks AS (
  SELECT DISTINCT DATE_SK, ISO_DATE FROM BRONZE.CALENDAR
  WHERE DATE_SK IN (SELECT DISTINCT INV_DATE_SK FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.INVENTORY)
  ORDER BY ISO_DATE DESC LIMIT {{INV_WEEKS}}
)
SELECT w.ISO_DATE AS SNAPSHOT_WEEK, m.DC_ID, 'SKU-' || LPAD(i.INV_ITEM_SK, 6, '0') AS SKU_ID,
       ROUND(SUM(COALESCE(i.INV_QUANTITY_ON_HAND, 0)) / {{INV_DIV}})::NUMBER AS ON_HAND
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.INVENTORY i
JOIN weeks w ON w.DATE_SK = i.INV_DATE_SK
JOIN BRONZE.WAREHOUSE_DC m ON m.WAREHOUSE_SK = i.INV_WAREHOUSE_SK
WHERE MOD(i.INV_ITEM_SK, {{ITEM_MOD}}) = 0
GROUP BY w.ISO_DATE, m.DC_ID, i.INV_ITEM_SK;

SELECT 'calendar_days' AS K, COUNT(*) AS N FROM BRONZE.CALENDAR
UNION ALL SELECT 'dealers', COUNT(*) FROM BRONZE.DEALERS
UNION ALL SELECT 'dealer_tiers', COUNT(*) FROM BRONZE.DEALER_TIER
UNION ALL SELECT 'products', COUNT(*) FROM BRONZE.PRODUCTS
UNION ALL SELECT 'distribution_centers', COUNT(*) FROM BRONZE.DISTRIBUTION_CENTERS
UNION ALL SELECT 'vendors', COUNT(*) FROM BRONZE.VENDORS
UNION ALL SELECT 'inventory_backbone_rows', COUNT(*) FROM BRONZE.INVENTORY_BACKBONE;
