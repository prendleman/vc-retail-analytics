-- 10 TB backbone: re-skin SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL (shared, zero storage cost) as the
-- VC lighting-retail universe. Nothing is copied here except small dimension tables; sales and
-- inventory stay in the share and are read by 08_silver_gold.sql.
--
-- Mapping (documented in docs/SNOWFLAKE.md):
--   store (1,500)            -> dealers           DLR-0001..DLR-1500 (first 50 = loaded synthetic dealers)
--   item (402,000)           -> products          SKU-000001..  (family/designer/finish/lead band re-skinned)
--   warehouse (25)           -> distribution_centers DC-01..
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

-- Distribution centers: warehouse -> DC.
CREATE TABLE IF NOT EXISTS BRONZE.DISTRIBUTION_CENTERS(DC_ID VARCHAR, NAME VARCHAR, REGION VARCHAR, STATE VARCHAR, WAREHOUSE_SK NUMBER);
MERGE INTO BRONZE.DISTRIBUTION_CENTERS t USING (
  SELECT 'DC-' || LPAD(W_WAREHOUSE_SK, 2, '0') AS DC_ID,
         COALESCE(INITCAP(W_CITY), 'DC') || ' DC' AS NAME,
         BRONZE.REGION_OF(W_STATE) AS REGION, W_STATE AS STATE, W_WAREHOUSE_SK AS WAREHOUSE_SK
  FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.WAREHOUSE
) s ON t.DC_ID = s.DC_ID
WHEN NOT MATCHED THEN INSERT VALUES (s.DC_ID, s.NAME, s.REGION, s.STATE, s.WAREHOUSE_SK);

-- Vendors: {{VENDOR_COUNT}} generated suppliers with a US / overseas mix. Loaded VND-01..12 remain.
MERGE INTO BRONZE.VENDORS t USING (
  SELECT 'VND-' || LPAD(SEQ4() + 100, 3, '0') AS VENDOR_ID,
         ARRAY_CONSTRUCT('Foundry','Metals','Atelier','Glassworks','Diffusers','Brass Works','Coil & Wire','Timber Shade','Crystal','Optics','Lacquer Co','Castings')[MOD(SEQ4(), 12)]::VARCHAR
           || ' ' || ARRAY_CONSTRUCT('Pearl River','Hudson','Tuscan','Gulf Coast','Nordic','Pacific','Prairie','Andes','Levant','Ontario','Kyoto','Savannah','Delta','Cascade','Baltic')[MOD(SEQ4() * 7, 15)]::VARCHAR
           || ' ' || LPAD(SEQ4() + 100, 3, '0') AS NAME,
         ARRAY_CONSTRUCT('US','US','US','US','US','CN','CN','IT','TW','TR','SE','PE','CA','JP','MX','IN')[MOD(SEQ4() * 5, 16)]::VARCHAR AS COUNTRY
  FROM TABLE(GENERATOR(ROWCOUNT => {{VENDOR_COUNT}}))
) s ON t.VENDOR_ID = s.VENDOR_ID
WHEN NOT MATCHED THEN INSERT VALUES (s.VENDOR_ID, s.NAME, s.COUNTRY);

-- Products: item -> SKU. Price re-scaled into a lighting range ($250-$4,450 list); cost ratio clamped 0.42-0.62.
CREATE OR REPLACE TABLE BRONZE.PRODUCTS_BACKBONE AS
WITH v AS (SELECT VENDOR_ID, ROW_NUMBER() OVER (ORDER BY VENDOR_ID) - 1 AS RN, COUNT(*) OVER () AS N FROM BRONZE.VENDORS)
SELECT 'SKU-' || LPAD(i.I_ITEM_SK, 6, '0') AS SKU_ID,
       ARRAY_CONSTRUCT('Marie Flanigan','Ralph Lauren','Julie Neill','Studio VC','Generation Lighting')[MOD(i.I_BRAND_ID, 5)]::VARCHAR
         || ' ' || ARRAY_CONSTRUCT('Ceiling','Wall','Lamps','Outdoor','Fans','Alabaster','Cordless')[MOD(i.I_ITEM_SK, 7)]::VARCHAR
         || ' ' || LPAD(i.I_ITEM_SK, 6, '0') AS NAME,
       ARRAY_CONSTRUCT('Ceiling','Wall','Lamps','Outdoor','Fans','Alabaster','Cordless')[MOD(i.I_ITEM_SK, 7)]::VARCHAR AS FAMILY,
       ARRAY_CONSTRUCT('Marie Flanigan','Ralph Lauren','Julie Neill','Studio VC','Generation Lighting')[MOD(i.I_BRAND_ID, 5)]::VARCHAR AS DESIGNER,
       ARRAY_CONSTRUCT('Antique Brass','Polished Nickel','Soft Brass','Alabaster','Matte Black')[MOD(ABS(HASH(i.I_COLOR)), 5)]::VARCHAR AS FINISH,
       (ROUND(250 + COALESCE(i.I_CURRENT_PRICE, 50) * 42) * 100)::NUMBER AS LIST_PRICE_CENTS,
       ARRAY_CONSTRUCT('in_stock','2_4_weeks','4_8_weeks','custom_overseas')[MOD(i.I_ITEM_SK, 4)]::VARCHAR AS LEAD_BAND,
       ROUND((ROUND(250 + COALESCE(i.I_CURRENT_PRICE, 50) * 42) * 100)
             * LEAST(0.62, GREATEST(0.42, COALESCE(i.I_WHOLESALE_COST / NULLIF(i.I_CURRENT_PRICE, 0), 0.5))))::NUMBER AS COST_CENTS,
       v.VENDOR_ID,
       CASE MOD(i.I_ITEM_SK, 4) WHEN 0 THEN 4 WHEN 1 THEN 8 WHEN 2 THEN 12 ELSE 20 END AS SAFETY_STOCK,
       i.I_ITEM_SK AS ITEM_SK,
       -- price factor: converts TPC-DS dollars for this item into re-skinned dollars
       (ROUND(250 + COALESCE(i.I_CURRENT_PRICE, 50) * 42)) / NULLIF(COALESCE(i.I_CURRENT_PRICE, 50), 0) AS PRICE_FACTOR
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.ITEM i
JOIN v ON v.RN = MOD(COALESCE(i.I_MANUFACT_ID, i.I_ITEM_SK), v.N);

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

-- Unified sales view over the three TPC-DS channels, re-skinned and windowed (read in 08; not materialized here).
-- Re-skin rules (TPC-DS is a general-merchandise retailer; a lighting dealer sells far fewer, pricier units):
--   * keep 1 ticket/order in {{SAMPLE_MOD}} (hash on a value independent of the dealer residue so every dealer keeps sales);
--   * QTY 1..100 -> 1..4 (divide by {{QTY_DIV}});
--   * money is NOT taken from the TPC-DS dollar columns. The row's own sales/list ratio is kept as a discount
--     (clamped 0.55..1.00) and applied to the re-skinned LIST_PRICE_CENTS downstream. NET_PAID is kept only
--     so NULL-field quarantine mirrors the source.
CREATE OR REPLACE VIEW BRONZE.BACKBONE_SALES AS
SELECT 'Trade' AS CHANNEL, 'DLR-' || LPAD(ss.SS_STORE_SK, 4, '0') AS DEALER_ID, ss.SS_ITEM_SK AS ITEM_SK,
       c.MONTH, c.CAL_DATE,
       CASE WHEN ss.SS_QUANTITY IS NULL THEN NULL ELSE GREATEST(1, ROUND(ss.SS_QUANTITY / {{QTY_DIV}})) END AS QTY,
       ss.SS_NET_PAID AS NET_PAID,
       LEAST(1.0, GREATEST(0.55, COALESCE(ss.SS_SALES_PRICE / NULLIF(ss.SS_LIST_PRICE, 0), 0.85))) AS DISC_RATIO,
       ss.SS_TICKET_NUMBER AS DOC_NO
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.STORE_SALES ss
JOIN BRONZE.CALENDAR c ON c.DATE_SK = ss.SS_SOLD_DATE_SK
WHERE MOD(ss.SS_TICKET_NUMBER, {{SAMPLE_MOD}}) = 0
UNION ALL
SELECT 'Contract', 'DLR-' || LPAD(MOD(cs.CS_ORDER_NUMBER, 1500) + 1, 4, '0'), cs.CS_ITEM_SK,
       c.MONTH, c.CAL_DATE,
       CASE WHEN cs.CS_QUANTITY IS NULL THEN NULL ELSE GREATEST(1, ROUND(cs.CS_QUANTITY / {{QTY_DIV}})) END,
       cs.CS_NET_PAID,
       LEAST(1.0, GREATEST(0.55, COALESCE(cs.CS_SALES_PRICE / NULLIF(cs.CS_LIST_PRICE, 0), 0.85))),
       cs.CS_ORDER_NUMBER
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.CATALOG_SALES cs
JOIN BRONZE.CALENDAR c ON c.DATE_SK = cs.CS_SOLD_DATE_SK
WHERE MOD(FLOOR(cs.CS_ORDER_NUMBER / 1500), {{SAMPLE_MOD}}) = 0
UNION ALL
SELECT 'Consumer', 'DLR-' || LPAD(MOD(ws.WS_ORDER_NUMBER, 1500) + 1, 4, '0'), ws.WS_ITEM_SK,
       c.MONTH, c.CAL_DATE,
       CASE WHEN ws.WS_QUANTITY IS NULL THEN NULL ELSE GREATEST(1, ROUND(ws.WS_QUANTITY / {{QTY_DIV}})) END,
       ws.WS_NET_PAID,
       LEAST(1.0, GREATEST(0.55, COALESCE(ws.WS_SALES_PRICE / NULLIF(ws.WS_LIST_PRICE, 0), 0.85))),
       ws.WS_ORDER_NUMBER
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.WEB_SALES ws
JOIN BRONZE.CALENDAR c ON c.DATE_SK = ws.WS_SOLD_DATE_SK
WHERE MOD(FLOOR(ws.WS_ORDER_NUMBER / 1500), {{SAMPLE_MOD}}) = 0;

-- Weekly inventory snapshots (TPC-DS inventory is weekly) for the last {{INV_WEEKS}} weeks: DC x SKU x week.
CREATE OR REPLACE TABLE BRONZE.INVENTORY_BACKBONE CLUSTER BY (SNAPSHOT_WEEK, DC_ID) AS
WITH weeks AS (
  SELECT DISTINCT DATE_SK, ISO_DATE FROM BRONZE.CALENDAR
  WHERE DATE_SK IN (SELECT DISTINCT INV_DATE_SK FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.INVENTORY)
  ORDER BY ISO_DATE DESC LIMIT {{INV_WEEKS}}
)
SELECT w.ISO_DATE AS SNAPSHOT_WEEK, dc.DC_ID, 'SKU-' || LPAD(i.INV_ITEM_SK, 6, '0') AS SKU_ID,
       ROUND(COALESCE(i.INV_QUANTITY_ON_HAND, 0) / {{INV_DIV}})::NUMBER AS ON_HAND  -- 0..1000 -> 0..10 per DC x SKU, matched to re-skinned demand
FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.INVENTORY i
JOIN weeks w ON w.DATE_SK = i.INV_DATE_SK
JOIN BRONZE.DISTRIBUTION_CENTERS dc ON dc.WAREHOUSE_SK = i.INV_WAREHOUSE_SK;

SELECT 'calendar_days' AS K, COUNT(*) AS N FROM BRONZE.CALENDAR
UNION ALL SELECT 'dealers', COUNT(*) FROM BRONZE.DEALERS
UNION ALL SELECT 'products', COUNT(*) FROM BRONZE.PRODUCTS
UNION ALL SELECT 'distribution_centers', COUNT(*) FROM BRONZE.DISTRIBUTION_CENTERS
UNION ALL SELECT 'vendors', COUNT(*) FROM BRONZE.VENDORS
UNION ALL SELECT 'inventory_backbone_rows', COUNT(*) FROM BRONZE.INVENTORY_BACKBONE;
