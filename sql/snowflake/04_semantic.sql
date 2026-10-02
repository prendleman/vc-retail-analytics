USE DATABASE VC_RETAIL_DEMO;
CREATE OR REPLACE SEMANTIC VIEW SERVING.VC_RETAIL_SEMANTICS
 TABLES(facts AS VC_RETAIL_DEMO.SERVING.SILVER_FACTS PRIMARY KEY(DEALER_ID,SKU_ID))
 DIMENSIONS(
  facts.dealer_id AS DEALER_ID COMMENT='Synthetic dealer / showroom identifier',
  facts.channel AS CHANNEL COMMENT='Consumer, Trade, or Contract',
  facts.family AS FAMILY COMMENT='Product family (Ceiling, Wall, Lamps, ...)',
  facts.region AS REGION COMMENT='Dealer operating region',
  facts.rep_id AS REP_ID COMMENT='Assigned salesperson',
  facts.lead_band AS LEAD_BAND COMMENT='Lead-time band for materials planning'
 )
 METRICS(
  facts.sku_count AS COUNT(*) COMMENT='Current valid dealer x SKU facts',
  facts.units_sold AS SUM(UNITS_SOLD) COMMENT='Trailing units sold in synthetic snapshot',
  facts.net_sales AS SUM(NET_SALES_CENTS)/100.0 COMMENT='USD net sales',
  facts.margin AS SUM(MARGIN_CENTS)/100.0 COMMENT='USD margin dollars',
  facts.margin_pct AS SUM(MARGIN_CENTS)/NULLIF(SUM(NET_SALES_CENTS),0)*100 COMMENT='Margin percent',
  facts.on_hand AS SUM(ON_HAND) COMMENT='Units on hand'
 )
 COMMENT='Synthetic Visual Comfort-flavored retail snapshot with margin, field, and supply dimensions. Dealer-scoped. Do not invent forecasts or live order status.';
GRANT SELECT ON SEMANTIC VIEW SERVING.VC_RETAIL_SEMANTICS TO ROLE AQ_VC_READER;
-- GRANT DATABASE ROLE SNOWFLAKE.CORTEX_ANALYST_USER TO ROLE AQ_VC_READER;
