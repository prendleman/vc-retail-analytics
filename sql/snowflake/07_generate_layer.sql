-- Generated VC layer (GBs, not TBs): sales org, vendor contracts, BOM, purchase orders, shipments, receipts.
-- Sized by {{SCALE}} via cloud.py templating. Everything references the backbone dimensions built in 06.
USE DATABASE VC_RETAIL_DEMO;
USE WAREHOUSE {{BUILD_WH}};
ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS={{BUILD_TIMEOUT}};
ALTER SESSION SET QUERY_TAG='aq-vc-retail-generate';

-- ---------------------------------------------------------------- sales org
-- Salespeople: {{REP_COUNT}} generated reps, round-robin over territories so every territory has coverage.
MERGE INTO BRONZE.SALESPEOPLE t USING (
  WITH ter AS (SELECT TERRITORY_ID, ROW_NUMBER() OVER (ORDER BY TERRITORY_ID) - 1 AS RN, COUNT(*) OVER () AS N FROM BRONZE.TERRITORIES),
       g AS (SELECT SEQ4() AS I FROM TABLE(GENERATOR(ROWCOUNT => {{REP_COUNT}})))
  SELECT 'REP-' || LPAD(1000 + g.I, 4, '0') AS REP_ID,
         'Rep ' || CHR(65 + MOD(g.I, 26)) || '. ' || ARRAY_CONSTRUCT('Lighting','Fixtures','Lamps','Design','Studio')[MOD(g.I, 5)]::VARCHAR || ' ' || LPAD(1000 + g.I, 4, '0') AS NAME,
         ter.TERRITORY_ID,
         TO_VARCHAR(DATEADD(month, -UNIFORM(3, 96, RANDOM(11)), '{{AS_OF}}'::DATE), 'YYYY-MM') AS HIRE_MONTH,
         UNIFORM(18000000, 42000000, RANDOM(12)) AS QUARTERLY_QUOTA_CENTS
  FROM g JOIN ter ON ter.RN = MOD(g.I, ter.N)
) s ON t.REP_ID = s.REP_ID
WHEN NOT MATCHED THEN INSERT VALUES (s.REP_ID, s.NAME, s.TERRITORY_ID, s.HIRE_MONTH, s.QUARTERLY_QUOTA_CENTS);

-- Rep assignments: every dealer -> one active rep in its territory (fallback: any rep in region); ~20% carry a prior rep.
CREATE OR REPLACE TABLE BRONZE.REP_ASSIGNMENTS AS
WITH reps AS (
  SELECT sp.REP_ID, sp.TERRITORY_ID, t.REGION,
         ROW_NUMBER() OVER (PARTITION BY sp.TERRITORY_ID ORDER BY sp.REP_ID) - 1 AS RN_T, COUNT(*) OVER (PARTITION BY sp.TERRITORY_ID) AS N_T,
         ROW_NUMBER() OVER (PARTITION BY t.REGION ORDER BY sp.REP_ID) - 1 AS RN_R, COUNT(*) OVER (PARTITION BY t.REGION) AS N_R
  FROM BRONZE.SALESPEOPLE sp JOIN BRONZE.TERRITORIES t ON t.TERRITORY_ID = sp.TERRITORY_ID
), d AS (
  SELECT DEALER_ID, TERRITORY_ID, REGION, COALESCE(TRY_TO_NUMBER(SUBSTR(DEALER_ID, 5)), 0) AS SK FROM BRONZE.DEALERS
), cur AS (
  SELECT d.DEALER_ID, d.SK, d.REGION, COALESCE(rt.REP_ID, rr.REP_ID) AS REP_ID
  FROM d
  LEFT JOIN reps rt ON rt.TERRITORY_ID = d.TERRITORY_ID AND rt.RN_T = MOD(d.SK, rt.N_T)
  LEFT JOIN reps rr ON rr.REGION = d.REGION AND rr.RN_R = MOD(d.SK, rr.N_R)
), cur2 AS (
  SELECT DEALER_ID, SK, REGION, REP_ID, TO_VARCHAR(DATEADD(month, -UNIFORM(6, 30, RANDOM(21)), '{{AS_OF}}'::DATE), 'YYYY-MM') AS START_MONTH
  FROM cur WHERE REP_ID IS NOT NULL
), prior AS (
  SELECT c.DEALER_ID, r.REP_ID,
         TO_VARCHAR(DATEADD(month, -UNIFORM(12, 36, RANDOM(22)), TO_DATE(c.START_MONTH || '-01')), 'YYYY-MM') AS START_MONTH,
         TO_VARCHAR(DATEADD(month, -1, TO_DATE(c.START_MONTH || '-01')), 'YYYY-MM') AS END_MONTH
  FROM cur2 c
  JOIN reps r ON r.REGION = c.REGION AND r.RN_R = MOD(c.SK * 7 + 3, r.N_R)
  WHERE MOD(c.SK, 5) = 0 AND r.REP_ID <> c.REP_ID
)
SELECT REP_ID, DEALER_ID, START_MONTH, NULL::VARCHAR AS END_MONTH FROM cur2
UNION ALL
SELECT REP_ID, DEALER_ID, START_MONTH, END_MONTH FROM prior;

-- ---------------------------------------------------------------- vendors
CREATE OR REPLACE TABLE BRONZE.VENDOR_CONTRACTS AS
SELECT 'CTR-' || VENDOR_ID || '-2025' AS CONTRACT_ID, VENDOR_ID, '2025-01' AS START_MONTH, '2026-12' AS END_MONTH,
       CASE WHEN COUNTRY IN ('US','CA','MX') THEN ARRAY_CONSTRUCT(14,21,28,42)[MOD(ABS(HASH(VENDOR_ID)),4)]::NUMBER
            ELSE ARRAY_CONSTRUCT(60,90,120,150)[MOD(ABS(HASH(VENDOR_ID)),4)]::NUMBER END AS PROMISED_LEAD_DAYS,
       CASE WHEN COUNTRY IN ('US','CA','MX') THEN 'FOB' ELSE ARRAY_CONSTRUCT('FOB','CIF','DDP')[MOD(ABS(HASH(VENDOR_ID)),3)]::VARCHAR END AS INCOTERM,
       ARRAY_CONSTRUCT(30,45,60,90)[MOD(ABS(HASH(VENDOR_ID || 'p')),4)]::NUMBER AS PAYMENT_TERMS_DAYS,
       ARRAY_CONSTRUCT(92.0,95.0,97.0)[MOD(ABS(HASH(VENDOR_ID || 'o')),3)]::FLOAT AS OTIF_TARGET_PCT,
       ARRAY_CONSTRUCT(10,25,50,100)[MOD(ABS(HASH(VENDOR_ID || 'm')),4)]::NUMBER AS MIN_ORDER_QTY
FROM BRONZE.VENDORS;

-- Product index per vendor (for sampling PO lines from a vendor's own catalog).
CREATE OR REPLACE TABLE BRONZE.PRODUCT_VENDOR_IDX AS
SELECT VENDOR_ID, SKU_ID, COST_CENTS, FAMILY, LEAD_BAND, SAFETY_STOCK,
       ROW_NUMBER() OVER (PARTITION BY VENDOR_ID ORDER BY SKU_ID) - 1 AS IDX,
       COUNT(*) OVER (PARTITION BY VENDOR_ID) AS N
FROM BRONZE.PRODUCTS;

-- ---------------------------------------------------------------- BOM
CREATE OR REPLACE TABLE BRONZE.COMPONENTS AS
WITH v AS (SELECT VENDOR_ID, COUNTRY, ROW_NUMBER() OVER (ORDER BY VENDOR_ID) - 1 AS RN, COUNT(*) OVER () AS N FROM BRONZE.VENDORS),
     g AS (SELECT SEQ4() AS I FROM TABLE(GENERATOR(ROWCOUNT => {{COMPONENT_COUNT}})))
SELECT 'CMP-' || LPAD(g.I + 1, 6, '0') AS COMPONENT_ID,
       ARRAY_CONSTRUCT('Brass casting','Glass shade','Alabaster','Socket & wiring','LED driver','Fabric shade','Hardware kit','Packaging')[MOD(g.I, 8)]::VARCHAR || ' ' || LPAD(g.I + 1, 6, '0') AS NAME,
       ARRAY_CONSTRUCT('Brass casting','Glass shade','Alabaster','Socket & wiring','LED driver','Fabric shade','Hardware kit','Packaging')[MOD(g.I, 8)]::VARCHAR AS CATEGORY,
       v.VENDOR_ID,
       UNIFORM(400, 18000, RANDOM(31)) AS UNIT_COST_CENTS,
       CASE WHEN v.COUNTRY IN ('US','CA','MX') THEN ARRAY_CONSTRUCT(7,14,21,30)[MOD(g.I,4)]::NUMBER ELSE ARRAY_CONSTRUCT(45,60,90,120)[MOD(g.I,4)]::NUMBER END AS LEAD_DAYS
FROM g JOIN v ON v.RN = MOD(g.I, v.N);

-- BOM: 4 components per SKU drawn from the affordable tier (unit cost <= 40% of material target), qty sized to ~55-85% of standard cost.
CREATE OR REPLACE TABLE BRONZE.BOM AS
WITH c AS (SELECT COMPONENT_ID, UNIT_COST_CENTS,
                  ROW_NUMBER() OVER (ORDER BY UNIT_COST_CENTS, COMPONENT_ID) - 1 AS RN, COUNT(*) OVER () AS N FROM BRONZE.COMPONENTS),
     p AS (SELECT SKU_ID, COST_CENTS, COST_CENTS * UNIFORM(0.55::FLOAT, 0.85::FLOAT, RANDOM(41)) AS TARGET,
                  (TARGET * 0.4)::NUMBER(18,0) AS THRESH,
                  ABS(HASH(SKU_ID)) AS H FROM BRONZE.PRODUCTS),
     -- affordable window per SKU = number of components with unit cost <= 40% of the material target (ASOF lookup on the
     -- cost-sorted component list); cheap SKUs fall back to the cheapest sixth of the catalog.
     aff AS (
       SELECT p.SKU_ID, p.TARGET, p.H,
              GREATEST(COALESCE(c.RN + 1, 0), (SELECT CEIL(COUNT(*) / 6.0) FROM BRONZE.COMPONENTS)) AS AFFORDABLE_N
       FROM p ASOF JOIN c MATCH_CONDITION (p.THRESH >= c.UNIT_COST_CENTS)
     ),
     slots AS (SELECT SEQ4() AS SLOT FROM TABLE(GENERATOR(ROWCOUNT => 4))),
     pick AS (
       SELECT a.SKU_ID, a.TARGET, s.SLOT, c.COMPONENT_ID, c.UNIT_COST_CENTS
       FROM aff a CROSS JOIN slots s
       JOIN c ON c.RN = MOD(a.H + s.SLOT * 7919, a.AFFORDABLE_N)
     )
SELECT SKU_ID, COMPONENT_ID, GREATEST(1, ROUND(TARGET / 4.0 * UNIFORM(0.5::FLOAT, 1.5::FLOAT, RANDOM(42)) / NULLIF(UNIT_COST_CENTS, 0)))::NUMBER AS QTY_PER
FROM pick QUALIFY ROW_NUMBER() OVER (PARTITION BY SKU_ID, COMPONENT_ID ORDER BY SLOT) = 1;

-- ---------------------------------------------------------------- purchase orders
CREATE OR REPLACE TABLE BRONZE.PURCHASE_ORDERS CLUSTER BY (STATUS, VENDOR_ID) AS
WITH v AS (SELECT vc.VENDOR_ID, vc.PROMISED_LEAD_DAYS, ve.COUNTRY, ROW_NUMBER() OVER (ORDER BY vc.VENDOR_ID) - 1 AS RN, COUNT(*) OVER () AS N
           FROM BRONZE.VENDOR_CONTRACTS vc JOIN BRONZE.VENDORS ve ON ve.VENDOR_ID = vc.VENDOR_ID),
     dc AS (SELECT DC_ID, ROW_NUMBER() OVER (ORDER BY DC_ID) - 1 AS RN, COUNT(*) OVER () AS N FROM BRONZE.DISTRIBUTION_CENTERS),
     g AS (SELECT SEQ4() AS I, UNIFORM(0, 364, RANDOM(51)) AS AGE, UNIFORM(0::FLOAT, 1::FLOAT, RANDOM(52)) AS R FROM TABLE(GENERATOR(ROWCOUNT => {{PO_ROWS}}))),
     base AS (
       SELECT 'PO-' || LPAD(g.I + 1, 8, '0') AS PO_ID, v.VENDOR_ID, v.COUNTRY, dc.DC_ID,
              DATEADD(day, -g.AGE, '{{AS_OF}}'::DATE) AS ORDER_DATE,
              DATEADD(day, v.PROMISED_LEAD_DAYS - g.AGE, '{{AS_OF}}'::DATE) AS PROMISED_DATE,
              v.PROMISED_LEAD_DAYS AS LEAD_DAYS, g.R
       FROM g JOIN v ON v.RN = MOD(g.I, v.N) JOIN dc ON dc.RN = MOD(g.I * 13, dc.N)
     )
SELECT PO_ID, VENDOR_ID, DC_ID, ORDER_DATE, PROMISED_DATE,
       -- past-promised POs are mostly received/closed; ~5% linger open/in-transit (past due), ~4% cancelled
       CASE WHEN PROMISED_DATE > '{{AS_OF}}'::DATE THEN (CASE WHEN R < 0.66 THEN 'open' ELSE 'in_transit' END)
            WHEN R < 0.45 THEN 'received' WHEN R < 0.91 THEN 'closed' WHEN R < 0.935 THEN 'open'
            WHEN R < 0.96 THEN 'in_transit' ELSE 'cancelled' END AS STATUS,
       COUNTRY, LEAD_DAYS
FROM base;

CREATE OR REPLACE TABLE BRONZE.PO_LINES CLUSTER BY (PO_ID) AS
WITH lines AS (SELECT SEQ4() AS L FROM TABLE(GENERATOR(ROWCOUNT => 6))),
     -- short-ship is decided per PO (2% for the most reliable vendor .. ~19% for the least; same reliability as shipments), not per line,
     -- so multi-line POs can still count as in-full for OTIF.
     po AS (SELECT PO_ID, VENDOR_ID, STATUS, PROMISED_DATE, ABS(HASH(PO_ID)) AS H, 2 + MOD(ABS(HASH(PO_ID || 'n')), 5) AS N_LINES,
                   MOD(ABS(HASH(PO_ID || 'f')), 100) < (2 + ROUND((1.0 - (0.45 + MOD(ABS(HASH(VENDOR_ID)), 56) / 100.0)) * 30)) AS SHORT
            FROM BRONZE.PURCHASE_ORDERS)
SELECT po.PO_ID, l.L + 1 AS LINE_NO, pv.SKU_ID,
       ARRAY_CONSTRUCT(10,20,25,40,50,100)[MOD(po.H + l.L, 6)]::NUMBER AS QTY_ORDERED,
       ROUND(pv.COST_CENTS * UNIFORM(0.95::FLOAT, 1.08::FLOAT, RANDOM(61)))::NUMBER AS UNIT_COST_CENTS,
       CASE po.STATUS
         WHEN 'received' THEN (CASE WHEN NOT po.SHORT OR l.L > 0 THEN ARRAY_CONSTRUCT(10,20,25,40,50,100)[MOD(po.H + l.L, 6)]::NUMBER
                                    ELSE ROUND(ARRAY_CONSTRUCT(10,20,25,40,50,100)[MOD(po.H + l.L, 6)]::NUMBER * UNIFORM(0.6::FLOAT, 0.98::FLOAT, RANDOM(63))) END)
         WHEN 'closed'   THEN (CASE WHEN NOT po.SHORT OR l.L > 0 THEN ARRAY_CONSTRUCT(10,20,25,40,50,100)[MOD(po.H + l.L, 6)]::NUMBER
                                    ELSE ROUND(ARRAY_CONSTRUCT(10,20,25,40,50,100)[MOD(po.H + l.L, 6)]::NUMBER * UNIFORM(0.6::FLOAT, 0.98::FLOAT, RANDOM(65))) END)
         WHEN 'open'     THEN (CASE WHEN UNIFORM(0::FLOAT, 1::FLOAT, RANDOM(66)) < 0.7 THEN 0
                                    ELSE ROUND(ARRAY_CONSTRUCT(10,20,25,40,50,100)[MOD(po.H + l.L, 6)]::NUMBER * UNIFORM(0.2::FLOAT, 0.8::FLOAT, RANDOM(67))) END)
         ELSE 0 END::NUMBER AS QTY_RECEIVED,
       po.PROMISED_DATE
FROM po JOIN lines l ON l.L < po.N_LINES
JOIN BRONZE.PRODUCT_VENDOR_IDX pv ON pv.VENDOR_ID = po.VENDOR_ID AND pv.IDX = MOD(po.H + l.L * 104729, pv.N);

-- Shipments: one per PO that has moved (received/closed/in_transit, or open with partial receipt).
CREATE OR REPLACE TABLE BRONZE.SHIPMENTS CLUSTER BY (PO_ID) AS
WITH val AS (SELECT PO_ID, SUM(QTY_ORDERED * UNIT_COST_CENTS) AS VALUE_CENTS, SUM(QTY_RECEIVED) AS RCV FROM BRONZE.PO_LINES GROUP BY PO_ID),
     po AS (
       SELECT po.*, val.VALUE_CENTS, val.RCV,
              CASE WHEN po.COUNTRY IN ('US','CA','MX') THEN FALSE ELSE TRUE END AS OVERSEAS,
              -- transit is a fraction of lead time (the rest is vendor make/pick time)
              GREATEST(3, ROUND(po.LEAD_DAYS * UNIFORM(0.25::FLOAT, 0.6::FLOAT, RANDOM(71))))::NUMBER AS TRANSIT,
              -- vendor on-time reliability 0.45..1.00, stable per vendor (wide enough to populate Prefer / Watch / Exit tiers)
              0.45 + MOD(ABS(HASH(po.VENDOR_ID)), 56) / 100.0 AS RELIABILITY
       FROM BRONZE.PURCHASE_ORDERS po JOIN val ON val.PO_ID = po.PO_ID
       WHERE po.STATUS IN ('received','closed','in_transit') OR (po.STATUS = 'open' AND val.RCV > 0)
     ),
     s AS (
       SELECT po.*, DATEADD(day, GREATEST(1, LEAD_DAYS - TRANSIT), ORDER_DATE) AS SHIP_DATE,
              CASE WHEN OVERSEAS THEN ARRAY_CONSTRUCT('ocean','ocean','air')[MOD(ABS(HASH(PO_ID)),3)]::VARCHAR
                   ELSE ARRAY_CONSTRUCT('truck','truck','rail')[MOD(ABS(HASH(PO_ID)),3)]::VARCHAR END AS MODE,
              -- arrival vs promise: on time (0-4 days early) with probability RELIABILITY, else 1-14 days late (2-30 overseas)
              CASE WHEN UNIFORM(0::FLOAT, 1::FLOAT, RANDOM(72)) < RELIABILITY THEN -UNIFORM(0, 4, RANDOM(75))
                   ELSE IFF(OVERSEAS, UNIFORM(2, 30, RANDOM(76)), UNIFORM(1, 14, RANDOM(77))) END AS DELAY_DAYS
       FROM po
     )
SELECT 'SHP-' || SUBSTR(PO_ID, 4) AS SHIPMENT_ID, PO_ID, VENDOR_ID, DC_ID, SHIP_DATE,
       DATEADD(day, TRANSIT, SHIP_DATE) AS ETA_DATE,
       CASE WHEN STATUS = 'in_transit' THEN NULL
            ELSE GREATEST(DATEADD(day, 1, SHIP_DATE), DATEADD(day, DELAY_DAYS, PROMISED_DATE)) END AS ARRIVAL_DATE,
       MODE,
       ROUND(VALUE_CENTS * CASE MODE WHEN 'ocean' THEN 0.04 WHEN 'air' THEN 0.14 WHEN 'truck' THEN 0.05 ELSE 0.035 END
             * UNIFORM(0.8::FLOAT, 1.3::FLOAT, RANDOM(73)))::NUMBER AS FREIGHT_CENTS,
       UNIFORM(2, 60, RANDOM(74)) AS CARTONS
FROM s;

-- Receipts: per received line on arrived shipments; defect rate higher overseas.
CREATE OR REPLACE TABLE BRONZE.RECEIPTS CLUSTER BY (PO_ID) AS
SELECT 'RCT-' || SUBSTR(pl.PO_ID, 4) || '-' || pl.LINE_NO AS RECEIPT_ID, s.SHIPMENT_ID, pl.PO_ID, pl.LINE_NO, pl.SKU_ID,
       pl.QTY_RECEIVED,
       ROUND(pl.QTY_RECEIVED * UNIFORM(0::FLOAT, 1::FLOAT, RANDOM(81)) * IFF(po.COUNTRY IN ('US','CA','MX'), 0.025, 0.06))::NUMBER AS QTY_DEFECTIVE,
       s.ARRIVAL_DATE AS RECEIVED_DATE
FROM BRONZE.PO_LINES pl
JOIN BRONZE.PURCHASE_ORDERS po ON po.PO_ID = pl.PO_ID
JOIN BRONZE.SHIPMENTS s ON s.PO_ID = pl.PO_ID
WHERE pl.QTY_RECEIVED > 0 AND s.ARRIVAL_DATE IS NOT NULL;

SELECT 'salespeople' AS K, COUNT(*) AS N FROM BRONZE.SALESPEOPLE
UNION ALL SELECT 'rep_assignments', COUNT(*) FROM BRONZE.REP_ASSIGNMENTS
UNION ALL SELECT 'vendor_contracts', COUNT(*) FROM BRONZE.VENDOR_CONTRACTS
UNION ALL SELECT 'components', COUNT(*) FROM BRONZE.COMPONENTS
UNION ALL SELECT 'bom', COUNT(*) FROM BRONZE.BOM
UNION ALL SELECT 'purchase_orders', COUNT(*) FROM BRONZE.PURCHASE_ORDERS
UNION ALL SELECT 'po_lines', COUNT(*) FROM BRONZE.PO_LINES
UNION ALL SELECT 'shipments', COUNT(*) FROM BRONZE.SHIPMENTS
UNION ALL SELECT 'receipts', COUNT(*) FROM BRONZE.RECEIPTS;
