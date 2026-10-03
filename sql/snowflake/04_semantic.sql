USE DATABASE VC_RETAIL_DEMO;
CREATE OR REPLACE SEMANTIC VIEW SERVING.VC_RETAIL_SEMANTICS
 TABLES(facts AS VC_RETAIL_DEMO.SERVING.SILVER_FACTS PRIMARY KEY(DEALER_ID,SKU_ID))
 DIMENSIONS(
  facts.dealer_id AS DEALER_ID COMMENT='Synthetic dealer / showroom identifier (TPC-DS store re-skinned)',
  facts.channel AS CHANNEL COMMENT='Consumer (web), Trade (store), or Contract (catalog)',
  facts.family AS FAMILY COMMENT='Product family (Ceiling, Wall, Lamps, ...)',
  facts.region AS REGION COMMENT='Dealer operating region',
  facts.rep_id AS REP_ID COMMENT='Assigned salesperson (active rep assignment)',
  facts.lead_band AS LEAD_BAND COMMENT='Lead-time band for materials planning'
 )
 METRICS(
  facts.sku_count AS COUNT(*) COMMENT='Current valid dealer x SKU facts (trailing 12 months)',
  facts.units_sold AS SUM(UNITS_SOLD) COMMENT='Trailing units sold',
  facts.net_sales AS SUM(NET_SALES_CENTS)/100.0 COMMENT='USD net sales',
  facts.margin AS SUM(MARGIN_CENTS)/100.0 COMMENT='USD margin dollars',
  facts.margin_pct AS SUM(MARGIN_CENTS)/NULLIF(SUM(NET_SALES_CENTS),0)*100 COMMENT='Margin percent',
  facts.on_hand AS SUM(ON_HAND) COMMENT='Units on hand (apportioned from DC inventory)'
 )
 COMMENT='Synthetic Visual Comfort-flavored retail snapshot over a 10 TB TPC-DS backbone. Dealer-scoped. Do not invent forecasts or live order status.';
GRANT SELECT ON SEMANTIC VIEW SERVING.VC_RETAIL_SEMANTICS TO ROLE AQ_VC_READER;

CREATE OR REPLACE SEMANTIC VIEW SERVING.VC_SUPPLY_SEMANTICS
 TABLES(
  lines AS VC_RETAIL_DEMO.SERVING.PO_LINES PRIMARY KEY(PO_ID, LINE_NO),
  pos AS VC_RETAIL_DEMO.SERVING.PURCHASE_ORDERS PRIMARY KEY(PO_ID),
  vendors AS VC_RETAIL_DEMO.SERVING.VENDORS PRIMARY KEY(VENDOR_ID)
 )
 RELATIONSHIPS(
  lines(PO_ID) REFERENCES pos,
  pos(VENDOR_ID) REFERENCES vendors
 )
 DIMENSIONS(
  pos.status AS STATUS COMMENT='open, in_transit, received, closed, cancelled',
  pos.dc_id AS DC_ID COMMENT='Receiving distribution center',
  pos.promised_month AS SUBSTR(PROMISED_DATE,1,7) COMMENT='Promised month YYYY-MM',
  vendors.vendor_name AS NAME COMMENT='Vendor name',
  vendors.country AS COUNTRY COMMENT='Vendor country'
 )
 METRICS(
  lines.open_units AS SUM(QTY_ORDERED - QTY_RECEIVED) COMMENT='Units not yet received',
  lines.open_value AS SUM((QTY_ORDERED - QTY_RECEIVED) * UNIT_COST_CENTS)/100.0 COMMENT='USD open PO value',
  lines.ordered_value AS SUM(QTY_ORDERED * UNIT_COST_CENTS)/100.0 COMMENT='USD ordered value',
  lines.line_count AS COUNT(*) COMMENT='PO lines'
 )
 COMMENT='Synthetic procurement layer: purchase orders and lines by vendor and DC. Corporate scope (not dealer-keyed).';
GRANT SELECT ON SEMANTIC VIEW SERVING.VC_SUPPLY_SEMANTICS TO ROLE AQ_VC_READER;
-- GRANT DATABASE ROLE SNOWFLAKE.CORTEX_ANALYST_USER TO ROLE AQ_VC_READER;
