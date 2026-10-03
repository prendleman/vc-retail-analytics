"""Synthetic lighting-retail ingestion, medallion transforms, and governed metric tools."""
from __future__ import annotations

import json
import random
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import supply_chain

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "demo.db"

CHANNELS = ["Consumer", "Trade", "Contract"]
FAMILIES = ["Ceiling", "Wall", "Lamps", "Outdoor", "Fans", "Alabaster", "Cordless"]
REGIONS = ["South", "West", "Midwest", "Northeast"]
LEAD_BANDS = ["in_stock", "2_4_weeks", "4_8_weeks", "custom_overseas"]

LEAD_MIDPOINT_DAYS = {
    "in_stock": 7,
    "2_4_weeks": 21,
    "4_8_weeks": 42,
    "custom_overseas": 180,
}
SAFETY_BY_LEAD = {
    "in_stock": 4,
    "2_4_weeks": 8,
    "4_8_weeks": 12,
    "custom_overseas": 20,
}

DESIGNERS = [
    "Marie Flanigan",
    "Ralph Lauren",
    "Julie Neill",
    "Studio VC",
    "Generation Lighting",
]

VENDOR_NAMES = [
    ("VND-01", "Pearl River Foundry", "CN"),
    ("VND-02", "Hudson Valley Metals", "US"),
    ("VND-03", "Alabaster Atelier", "IT"),
    ("VND-04", "Gulf Coast Glass", "US"),
    ("VND-05", "Nordic Diffusers", "SE"),
    ("VND-06", "Pacific Brass Works", "TW"),
    ("VND-07", "Midwest Coil & Wire", "US"),
    ("VND-08", "Andes Timber Shade", "PE"),
    ("VND-09", "Levant Crystal", "TR"),
    ("VND-10", "Ontario Optics", "CA"),
    ("VND-11", "Kyoto Lacquer Co", "JP"),
    ("VND-12", "Savannah Castings", "US"),
]

TERRITORY_DEFS = [
    ("TER-S-TX", "TX-Gulf", "South"),
    ("TER-S-FL", "FL-Coast", "South"),
    ("TER-W-CA", "CA-Coast", "West"),
    ("TER-W-PNW", "Pacific Northwest", "West"),
    ("TER-M-CHI", "Great Lakes", "Midwest"),
    ("TER-M-PLN", "Plains", "Midwest"),
    ("TER-N-NY", "Metro Northeast", "Northeast"),
    ("TER-N-NE", "New England", "Northeast"),
]

# Month (1-12) seasonal multipliers by family — synthetic lighting retail curves.
_SEASON_BASE = {m: 1.0 for m in range(1, 13)}
SEASONAL_BY_FAMILY = {
    "Outdoor": {**_SEASON_BASE, 3: 1.2, 4: 1.6, 5: 1.85, 6: 1.9, 7: 1.7, 8: 1.35, 9: 1.1, 10: 0.85, 11: 0.7, 12: 0.65, 1: 0.7, 2: 0.85},
    "Fans": {**_SEASON_BASE, 3: 1.15, 4: 1.45, 5: 1.7, 6: 1.8, 7: 1.75, 8: 1.4, 9: 1.05, 10: 0.8, 11: 0.7, 12: 0.65},
    "Lamps": {**_SEASON_BASE, 9: 1.15, 10: 1.35, 11: 1.7, 12: 1.85, 1: 1.2, 2: 0.95, 6: 0.85, 7: 0.8},
    "Ceiling": {**_SEASON_BASE, 3: 1.1, 4: 1.15, 9: 1.1, 10: 1.2},
    "Wall": {**_SEASON_BASE, 3: 1.1, 10: 1.15, 11: 1.2},
    "Alabaster": {**_SEASON_BASE, 10: 1.25, 11: 1.4, 12: 1.35},
    "Cordless": {**_SEASON_BASE, 5: 1.2, 6: 1.35, 7: 1.3, 11: 1.25, 12: 1.4},
}


def _lead_case(col="lead_band"):
    parts = " ".join(f"WHEN '{k}' THEN {v}" for k, v in LEAD_MIDPOINT_DAYS.items())
    return f"CASE {col} {parts} ELSE 30 END"


METRICS = {
    "portfolio": {
        "description": "Current dealer facts: units sold (trailing), net sales, margin, on-hand.",
        "sql": (
            "SELECT dealer_id, COUNT(*) AS skus, SUM(units_sold) AS units_sold, "
            "SUM(net_sales_cents)/100.0 AS net_sales, SUM(margin_cents)/100.0 AS margin, "
            "SUM(on_hand) AS on_hand FROM silver_facts {where} "
            "GROUP BY dealer_id ORDER BY net_sales DESC LIMIT 40"
        ),
    },
    "by_channel": {
        "description": "Sell-through and margin by sales channel (Consumer / Trade / Contract).",
        "sql": (
            "SELECT channel, SUM(units_sold) AS units_sold, SUM(net_sales_cents)/100.0 AS net_sales, "
            "SUM(margin_cents)/100.0 AS margin FROM silver_facts {where} "
            "GROUP BY channel ORDER BY net_sales DESC"
        ),
    },
    "by_family": {
        "description": "Sell-through and margin by product family.",
        "sql": (
            "SELECT family, SUM(units_sold) AS units_sold, SUM(net_sales_cents)/100.0 AS net_sales, "
            "SUM(margin_cents)/100.0 AS margin, SUM(on_hand) AS on_hand FROM silver_facts {where} "
            "GROUP BY family ORDER BY net_sales DESC"
        ),
    },
    "by_region": {
        "description": "Sell-through by dealer region.",
        "sql": (
            "SELECT region, SUM(units_sold) AS units_sold, SUM(net_sales_cents)/100.0 AS net_sales, "
            "SUM(margin_cents)/100.0 AS margin FROM silver_facts {where} "
            "GROUP BY region ORDER BY net_sales DESC"
        ),
    },
    "stock_risk": {
        "description": "SKUs with low on-hand relative to trailing units (synthetic stock-risk flag).",
        "sql": (
            "SELECT dealer_id, sku_id, family, channel, on_hand, units_sold, "
            "net_sales_cents/100.0 AS net_sales FROM silver_facts {where} {and_} "
            "on_hand > 0 AND units_sold >= on_hand * 2 "
            "ORDER BY units_sold DESC LIMIT 40"
        ),
    },
    "quality": {
        "description": "Invalid event reasons in quarantine (includes superseded invalid versions).",
        "sql": "SELECT reason, COUNT(*) AS events FROM quarantine {where} GROUP BY reason ORDER BY events DESC",
    },
    "margin_pct": {
        "description": "Margin percent by channel (margin $ / net sales).",
        "sql": (
            "SELECT channel, SUM(units_sold) AS units_sold, SUM(net_sales_cents)/100.0 AS net_sales, "
            "SUM(margin_cents)/100.0 AS margin, "
            "ROUND(100.0 * SUM(margin_cents) / NULLIF(SUM(net_sales_cents), 0), 1) AS margin_pct "
            "FROM silver_facts {where} GROUP BY channel ORDER BY margin_pct ASC"
        ),
    },
    "price_realization": {
        "description": "Net ASP vs list price (discount depth / price realization).",
        "sql": (
            "SELECT sf.family, "
            "ROUND(AVG(1.0 * sf.net_sales_cents / NULLIF(sf.units_sold, 0) / NULLIF(p.list_price_cents, 0)), 3) AS realization, "
            "SUM(sf.net_sales_cents)/100.0 AS net_sales, SUM(sf.units_sold) AS units_sold "
            "FROM silver_facts sf JOIN products p ON p.sku_id = sf.sku_id "
            "{where_sf} GROUP BY sf.family ORDER BY realization ASC"
        ),
    },
    "low_margin_skus": {
        "description": "SKUs below portfolio average margin % (synthetic margin leakage).",
        "sql": (
            "SELECT sf.dealer_id, sf.sku_id, sf.family, sf.channel, "
            "sf.net_sales_cents/100.0 AS net_sales, sf.margin_cents/100.0 AS margin, "
            "ROUND(100.0 * sf.margin_cents / NULLIF(sf.net_sales_cents, 0), 1) AS margin_pct "
            "FROM silver_facts sf {where_sf} {and_sf} sf.net_sales_cents > 0 "
            "AND 100.0 * sf.margin_cents / sf.net_sales_cents < ("
            "  SELECT 100.0 * SUM(margin_cents) / NULLIF(SUM(net_sales_cents), 0) FROM silver_facts {where}"
            ") ORDER BY margin_pct ASC LIMIT 40"
        ),
    },
    "margin_waterfall": {
        "description": "Family mix contribution: sales share × margin gap vs portfolio (margin leakage map).",
        "sql": (
            "WITH port AS ("
            "  SELECT SUM(net_sales_cents) AS net_all, "
            "  100.0 * SUM(margin_cents) / NULLIF(SUM(net_sales_cents), 0) AS port_margin_pct "
            "  FROM silver_facts {where}"
            "), fam AS ("
            "  SELECT family, SUM(net_sales_cents) AS net_cents, SUM(margin_cents) AS margin_cents, "
            "  100.0 * SUM(margin_cents) / NULLIF(SUM(net_sales_cents), 0) AS margin_pct "
            "  FROM silver_facts {where} GROUP BY family"
            ") "
            "SELECT f.family, ROUND(f.net_cents/100.0, 0) AS net_sales, ROUND(f.margin_pct, 1) AS margin_pct, "
            "ROUND(p.port_margin_pct, 1) AS portfolio_margin_pct, "
            "ROUND(f.margin_pct - p.port_margin_pct, 1) AS margin_gap_pts, "
            "ROUND(100.0 * f.net_cents / NULLIF(p.net_all, 0), 1) AS sales_share_pct, "
            "ROUND((f.margin_pct - p.port_margin_pct) * f.net_cents / NULLIF(p.net_all, 0), 2) AS mix_contribution "
            "FROM fam f CROSS JOIN port p ORDER BY mix_contribution ASC"
        ),
    },
    "reorder_candidates": {
        "description": "SKUs below safety stock or days-of-cover under lead midpoint.",
        "sql": (
            "SELECT sf.dealer_id, sf.sku_id, sf.family, sf.lead_band, sf.on_hand, p.safety_stock, "
            "sf.units_sold, "
            "ROUND(CASE WHEN sf.units_sold > 0 THEN sf.on_hand * 90.0 / sf.units_sold ELSE 999 END, 1) AS days_of_cover, "
            f"{_lead_case('sf.lead_band')} AS lead_days "
            "FROM silver_facts sf JOIN products p ON p.sku_id = sf.sku_id "
            "{where_sf} {and_sf} ("
            "  sf.on_hand < p.safety_stock OR "
            "  (sf.units_sold > 0 AND sf.on_hand * 90.0 / sf.units_sold < "
            f"   {_lead_case('sf.lead_band')})"
            ") ORDER BY days_of_cover ASC LIMIT 40"
        ),
    },
    "days_of_cover": {
        "description": "Days of cover by family (on-hand / trailing daily run-rate).",
        "sql": (
            "SELECT family, SUM(on_hand) AS on_hand, SUM(units_sold) AS units_sold, "
            "ROUND(CASE WHEN SUM(units_sold) > 0 THEN SUM(on_hand) * 90.0 / SUM(units_sold) ELSE 999 END, 1) AS days_of_cover "
            "FROM silver_facts {where} GROUP BY family ORDER BY days_of_cover ASC"
        ),
    },
    "units_by_month": {
        "description": "24-month synthetic units by family (seasonality series).",
        "sql": (
            "SELECT month, family, SUM(units_sold) AS units_sold, "
            "SUM(net_sales_cents)/100.0 AS net_sales "
            "FROM silver_monthly {where} GROUP BY month, family ORDER BY month, family"
        ),
    },
    "seasonal_index": {
        "description": "Seasonal index by family-month vs family 12-mo average.",
        "sql": (
            "WITH monthly AS ("
            "  SELECT substr(month, 6, 2) AS mon, family, SUM(units_sold) AS units "
            "  FROM silver_monthly {where} GROUP BY substr(month, 6, 2), family"
            "), avg_f AS ("
            "  SELECT family, AVG(units) AS avg_units FROM monthly GROUP BY family"
            ") "
            "SELECT m.family, m.mon AS month_num, m.units, "
            "ROUND(m.units / NULLIF(a.avg_units, 0), 2) AS seasonal_index "
            "FROM monthly m JOIN avg_f a ON a.family = m.family "
            "ORDER BY m.family, m.mon"
        ),
    },
    "yoy_family": {
        "description": "Same-month year-over-year units by family (latest year vs prior).",
        "sql": (
            "WITH by_ym AS ("
            "  SELECT substr(month, 1, 4) AS yr, substr(month, 6, 2) AS mon, family, SUM(units_sold) AS units "
            "  FROM silver_monthly {where} GROUP BY substr(month, 1, 4), substr(month, 6, 2), family"
            "), latest AS (SELECT MAX(yr) AS yr FROM by_ym), "
            "cur AS (SELECT b.* FROM by_ym b JOIN latest l ON b.yr = l.yr), "
            "prv AS (SELECT b.* FROM by_ym b JOIN latest l ON b.yr = CAST(CAST(l.yr AS INTEGER) - 1 AS TEXT)) "
            "SELECT c.family, c.mon AS month_num, c.units AS units_this_year, COALESCE(p.units, 0) AS units_prior_year, "
            "ROUND(100.0 * (c.units - COALESCE(p.units, 0)) / NULLIF(COALESCE(p.units, 0), 0), 1) AS yoy_pct "
            "FROM cur c LEFT JOIN prv p ON p.family = c.family AND p.mon = c.mon "
            "ORDER BY c.family, c.mon"
        ),
    },
    "lead_vs_peak": {
        "description": "Families where peak seasonal month conflicts with long lead bands (buy-ahead risk).",
        "sql": (
            "WITH monthly AS ("
            "  SELECT family, substr(month, 6, 2) AS month_num, SUM(units_sold) AS units "
            "  FROM silver_monthly {where} GROUP BY family, substr(month, 6, 2)"
            "), avg_f AS ("
            "  SELECT family, AVG(units) AS avg_units FROM monthly GROUP BY family"
            "), indexed AS ("
            "  SELECT m.family, m.month_num, ROUND(m.units / NULLIF(a.avg_units, 0), 2) AS peak_index "
            "  FROM monthly m JOIN avg_f a ON a.family = m.family"
            "), tops AS ("
            "  SELECT i.family, i.month_num, i.peak_index FROM indexed i "
            "  WHERE i.peak_index = (SELECT MAX(i2.peak_index) FROM indexed i2 WHERE i2.family = i.family)"
            "), leads AS ("
            "  SELECT family, "
            "  SUM(CASE WHEN lead_band = 'custom_overseas' THEN 1 ELSE 0 END) AS overseas_skus, "
            "  SUM(CASE WHEN lead_band IN ('4_8_weeks','custom_overseas') THEN 1 ELSE 0 END) AS long_lead_skus, "
            "  COUNT(*) AS skus "
            "  FROM silver_facts {where} GROUP BY family"
            ") "
            "SELECT t.family, t.month_num AS peak_month, t.peak_index, l.overseas_skus, l.long_lead_skus, l.skus, "
            "CASE WHEN l.long_lead_skus * 1.0 / NULLIF(l.skus, 0) >= 0.35 AND t.peak_index >= 1.3 "
            "THEN 'Buy ahead' ELSE 'Ok' END AS risk_flag "
            "FROM tops t JOIN leads l ON l.family = t.family ORDER BY t.peak_index DESC"
        ),
    },
    "territory_coverage": {
        "description": "Dealers per territory vs capacity target (coverage pressure).",
        "sql": (
            "SELECT t.territory_id, t.name AS territory, t.region, t.capacity_dealers, "
            "COUNT(DISTINCT d.dealer_id) AS dealers_active, "
            "ROUND(100.0 * COUNT(DISTINCT d.dealer_id) / NULLIF(t.capacity_dealers, 0), 1) AS capacity_pct "
            "FROM territories t "
            "LEFT JOIN dealers d ON d.territory_id = t.territory_id "
            "{where_ter} "
            "GROUP BY t.territory_id, t.name, t.region, t.capacity_dealers "
            "ORDER BY capacity_pct ASC"
        ),
    },
    "plan_vs_season": {
        "description": "Reorder SKU counts by family with peak seasonal month (pull-forward plan).",
        "sql": (
            "WITH peak AS ("
            "  SELECT family, month_num, peak_index FROM ("
            "    SELECT m.family, m.month_num, "
            "    ROUND(m.units / NULLIF(a.avg_units, 0), 2) AS peak_index, "
            "    ROW_NUMBER() OVER (PARTITION BY m.family ORDER BY m.units DESC) AS rn "
            "    FROM ("
            "      SELECT family, substr(month, 6, 2) AS month_num, SUM(units_sold) AS units "
            "      FROM silver_monthly {where} GROUP BY family, substr(month, 6, 2)"
            "    ) m "
            "    JOIN ("
            "      SELECT family, AVG(units) AS avg_units FROM ("
            "        SELECT family, substr(month, 6, 2) AS month_num, SUM(units_sold) AS units "
            "        FROM silver_monthly {where} GROUP BY family, substr(month, 6, 2)"
            "      ) GROUP BY family"
            "    ) a ON a.family = m.family"
            "  ) WHERE rn = 1"
            "), risk AS ("
            "  SELECT sf.family, COUNT(*) AS reorder_skus, "
            "  ROUND(AVG(CASE WHEN sf.units_sold > 0 THEN sf.on_hand * 90.0 / sf.units_sold END), 1) AS avg_days_cover "
            "  FROM silver_facts sf JOIN products p ON p.sku_id = sf.sku_id "
            "  {where_sf} {and_sf} ("
            "    sf.on_hand < p.safety_stock OR "
            "    (sf.units_sold > 0 AND sf.on_hand * 90.0 / sf.units_sold < "
            f"     {_lead_case('sf.lead_band')})"
            "  ) GROUP BY sf.family"
            ") "
            "SELECT r.family, r.reorder_skus, r.avg_days_cover, p.month_num AS peak_month, p.peak_index, "
            "CASE WHEN p.peak_index >= 1.3 AND r.reorder_skus > 0 THEN 'Pull forward' ELSE 'Monitor' END AS plan_action "
            "FROM risk r JOIN peak p ON p.family = r.family ORDER BY p.peak_index DESC, r.reorder_skus DESC"
        ),
    },
    "territory_perf": {
        "description": "Territory sell-through, margin %, active dealers and SKUs.",
        "sql": (
            "SELECT t.territory_id, t.name AS territory, t.region, "
            "COUNT(DISTINCT sf.dealer_id) AS dealers, COUNT(*) AS skus, "
            "SUM(sf.units_sold) AS units_sold, SUM(sf.net_sales_cents)/100.0 AS net_sales, "
            "ROUND(100.0 * SUM(sf.margin_cents) / NULLIF(SUM(sf.net_sales_cents), 0), 1) AS margin_pct "
            "FROM silver_facts sf "
            "JOIN dealers d ON d.dealer_id = sf.dealer_id "
            "JOIN territories t ON t.territory_id = d.territory_id "
            "{where_sf} GROUP BY t.territory_id, t.name, t.region ORDER BY net_sales DESC"
        ),
    },
    "whitespace": {
        "description": "Dealers below region peer average sell-through (coverage whitespace).",
        "sql": (
            "WITH dealer_sales AS ("
            "  SELECT sf.dealer_id, d.name, d.city, d.region, d.territory_id, "
            "  SUM(sf.net_sales_cents)/100.0 AS net_sales "
            "  FROM silver_facts sf JOIN dealers d ON d.dealer_id = sf.dealer_id "
            "  {where_sf} GROUP BY sf.dealer_id, d.name, d.city, d.region, d.territory_id"
            "), region_avg AS ("
            "  SELECT region, AVG(net_sales) AS avg_sales FROM dealer_sales GROUP BY region"
            ") "
            "SELECT ds.dealer_id, ds.name, ds.city, ds.region, ds.territory_id, "
            "ROUND(ds.net_sales, 0) AS net_sales, ROUND(ra.avg_sales, 0) AS region_avg, "
            "ROUND(ds.net_sales / NULLIF(ra.avg_sales, 0), 2) AS vs_peer "
            "FROM dealer_sales ds JOIN region_avg ra ON ra.region = ds.region "
            "WHERE ds.net_sales < ra.avg_sales * 0.7 "
            "ORDER BY vs_peer ASC LIMIT 40"
        ),
    },
    "rep_leaderboard": {
        "description": "Salesperson net sales, margin %, units, and dealer coverage.",
        "sql": (
            "SELECT sp.rep_id, sp.name AS rep, t.name AS territory, "
            "COUNT(DISTINCT sf.dealer_id) AS dealers, SUM(sf.units_sold) AS units_sold, "
            "SUM(sf.net_sales_cents)/100.0 AS net_sales, "
            "ROUND(100.0 * SUM(sf.margin_cents) / NULLIF(SUM(sf.net_sales_cents), 0), 1) AS margin_pct, "
            "sp.quarterly_quota_cents/100.0 AS quarterly_quota, "
            "ROUND(100.0 * SUM(sf.net_sales_cents) / NULLIF(sp.quarterly_quota_cents, 0), 1) AS attainment_pct "
            "FROM silver_facts sf "
            "JOIN salespeople sp ON sp.rep_id = sf.rep_id "
            "LEFT JOIN territories t ON t.territory_id = sp.territory_id "
            "{where_sf} GROUP BY sp.rep_id, sp.name, t.name, sp.quarterly_quota_cents "
            "ORDER BY net_sales DESC LIMIT 40"
        ),
    },
    "rep_grade": {
        "description": "Composite A–D grade: attainment, margin vs peer, mix quality, stock discipline.",
        "sql": (
            "WITH rep_base AS ("
            "  SELECT sf.rep_id, sp.name AS rep, sp.quarterly_quota_cents, "
            "  SUM(sf.net_sales_cents) AS net_cents, SUM(sf.margin_cents) AS margin_cents, "
            "  SUM(CASE WHEN sf.channel IN ('Trade','Contract') THEN sf.net_sales_cents ELSE 0 END) AS mix_cents, "
            "  SUM(CASE WHEN sf.on_hand > 0 AND sf.units_sold >= sf.on_hand * 2 THEN 1 ELSE 0 END) AS risk_skus, "
            "  COUNT(*) AS skus "
            "  FROM silver_facts sf JOIN salespeople sp ON sp.rep_id = sf.rep_id "
            "  {where_sf} GROUP BY sf.rep_id, sp.name, sp.quarterly_quota_cents"
            "), scored AS ("
            "  SELECT *, "
            "  ROUND(100.0 * net_cents / NULLIF(quarterly_quota_cents, 0), 1) AS attainment_pct, "
            "  ROUND(100.0 * margin_cents / NULLIF(net_cents, 0), 1) AS margin_pct, "
            "  ROUND(100.0 * mix_cents / NULLIF(net_cents, 0), 1) AS mix_pct, "
            "  ROUND(100.0 * (skus - risk_skus) / NULLIF(skus, 0), 1) AS stock_discipline "
            "  FROM rep_base"
            "), peer AS ("
            "  SELECT AVG(margin_pct) AS peer_margin FROM scored"
            ") "
            "SELECT s.rep_id, s.rep, s.attainment_pct, s.margin_pct, s.mix_pct, s.stock_discipline, "
            "ROUND("
            "  0.40 * CASE WHEN s.attainment_pct > 100 THEN 100 ELSE s.attainment_pct END + "
            "  0.30 * CASE WHEN 100.0 * s.margin_pct / NULLIF(p.peer_margin, 0) > 100 THEN 100 ELSE 100.0 * s.margin_pct / NULLIF(p.peer_margin, 0) END + "
            "  0.20 * s.mix_pct + "
            "  0.10 * s.stock_discipline"
            ", 1) AS composite, "
            "CASE "
            "  WHEN (0.40 * CASE WHEN s.attainment_pct > 100 THEN 100 ELSE s.attainment_pct END + 0.30 * CASE WHEN 100.0 * s.margin_pct / NULLIF(p.peer_margin, 0) > 100 THEN 100 ELSE 100.0 * s.margin_pct / NULLIF(p.peer_margin, 0) END + 0.20 * s.mix_pct + 0.10 * s.stock_discipline) >= 85 THEN 'A' "
            "  WHEN (0.40 * CASE WHEN s.attainment_pct > 100 THEN 100 ELSE s.attainment_pct END + 0.30 * CASE WHEN 100.0 * s.margin_pct / NULLIF(p.peer_margin, 0) > 100 THEN 100 ELSE 100.0 * s.margin_pct / NULLIF(p.peer_margin, 0) END + 0.20 * s.mix_pct + 0.10 * s.stock_discipline) >= 70 THEN 'B' "
            "  WHEN (0.40 * CASE WHEN s.attainment_pct > 100 THEN 100 ELSE s.attainment_pct END + 0.30 * CASE WHEN 100.0 * s.margin_pct / NULLIF(p.peer_margin, 0) > 100 THEN 100 ELSE 100.0 * s.margin_pct / NULLIF(p.peer_margin, 0) END + 0.20 * s.mix_pct + 0.10 * s.stock_discipline) >= 55 THEN 'C' "
            "  ELSE 'D' END AS grade "
            "FROM scored s CROSS JOIN peer p ORDER BY composite DESC"
        ),
    },
    "vendor_otif": {
        "description": "Vendor on-time-in-full % and shipment volume.",
        "sql": (
            "SELECT v.vendor_id, v.name, v.country, vk.otif_pct, vk.shipments, vk.avg_lead_days, vk.promised_lead_days "
            "FROM silver_vendor_kpi vk JOIN vendors v ON v.vendor_id = vk.vendor_id "
            "WHERE v.vendor_id IN ("
            "  SELECT DISTINCT p.vendor_id FROM products p "
            "  JOIN silver_facts sf ON sf.sku_id = p.sku_id {where_sf}"
            ") ORDER BY vk.otif_pct ASC"
        ),
    },
    "vendor_scorecard": {
        "description": "Vendor Prefer/Watch/Exit score from OTIF, quality, lead reliability, margin impact.",
        "sql": (
            "WITH v_margin AS ("
            "  SELECT p.vendor_id, "
            "  ROUND(100.0 * SUM(sf.margin_cents) / NULLIF(SUM(sf.net_sales_cents), 0), 1) AS margin_pct "
            "  FROM silver_facts sf JOIN products p ON p.sku_id = sf.sku_id "
            "  {where_sf} GROUP BY p.vendor_id"
            ") "
            "SELECT v.vendor_id, v.name, v.country, vk.otif_pct, "
            "ROUND(100.0 - vk.defect_pct, 1) AS quality_pct, "
            "ROUND(100.0 * CASE WHEN vk.promised_lead_days / NULLIF(vk.avg_lead_days, 0) > 1.0 THEN 1.0 ELSE vk.promised_lead_days / NULLIF(vk.avg_lead_days, 0) END, 1) AS lead_reliability, "
            "COALESCE(vm.margin_pct, 0) AS margin_pct, "
            "ROUND("
            "  0.35 * vk.otif_pct + "
            "  0.25 * (100.0 - vk.defect_pct) + "
            "  0.20 * (100.0 * CASE WHEN vk.promised_lead_days / NULLIF(vk.avg_lead_days, 0) > 1.0 THEN 1.0 ELSE vk.promised_lead_days / NULLIF(vk.avg_lead_days, 0) END) + "
            "  0.20 * COALESCE(vm.margin_pct, 0)"
            ", 1) AS score, "
            "CASE "
            "  WHEN (0.35 * vk.otif_pct + 0.25 * (100.0 - vk.defect_pct) + 0.20 * (100.0 * CASE WHEN vk.promised_lead_days / NULLIF(vk.avg_lead_days, 0) > 1.0 THEN 1.0 ELSE vk.promised_lead_days / NULLIF(vk.avg_lead_days, 0) END) + 0.20 * COALESCE(vm.margin_pct, 0)) >= 80 THEN 'Prefer' "
            "  WHEN (0.35 * vk.otif_pct + 0.25 * (100.0 - vk.defect_pct) + 0.20 * (100.0 * CASE WHEN vk.promised_lead_days / NULLIF(vk.avg_lead_days, 0) > 1.0 THEN 1.0 ELSE vk.promised_lead_days / NULLIF(vk.avg_lead_days, 0) END) + 0.20 * COALESCE(vm.margin_pct, 0)) >= 60 THEN 'Watch' "
            "  ELSE 'Exit' END AS tier "
            "FROM silver_vendor_kpi vk "
            "JOIN vendors v ON v.vendor_id = vk.vendor_id "
            "LEFT JOIN v_margin vm ON vm.vendor_id = v.vendor_id "
            "WHERE v.vendor_id IN ("
            "  SELECT DISTINCT p.vendor_id FROM products p "
            "  JOIN silver_facts sf ON sf.sku_id = p.sku_id {where_sf}"
            ") ORDER BY score DESC"
        ),
    },
}

FAQ = [
    {
        "id": "ship_instock",
        "q": "when will in-stock items ship",
        "a": "In-stock items typically ship within 7 business days (synthetic policy aligned to public FAQ language).",
        "tags": ["shipping", "lead_time"],
    },
    {
        "id": "custom_lead",
        "q": "custom order lead time",
        "a": "Typical customization is about 3–4 weeks from in-stock status; overseas customization can run 24–30 weeks. Custom orders are final sale.",
        "tags": ["custom", "lead_time"],
    },
    {
        "id": "open_box",
        "q": "what is open box",
        "a": "Open Box items were previously shipped and returned, inspected and recertified as-new except packaging. Final sale except defect/transit damage.",
        "tags": ["open_box", "returns"],
    },
    {
        "id": "trade_savings",
        "q": "trade discount",
        "a": "Trade professionals may qualify for trade pricing programs. This demo routes Trade-channel questions to the Trade lane and does not invent discount percentages.",
        "tags": ["trade", "pricing"],
    },
    {
        "id": "clean",
        "q": "how do I clean fixtures",
        "a": "Clean with a soft, dry cloth only. Avoid abrasives, vinegar, ammonia, or metal silicates (synthetic copy of public care guidance).",
        "tags": ["care", "product"],
    },
    {
        "id": "channels",
        "q": "who do I contact",
        "a": "Public lanes: B2B Partners, Consumer|Trade customer service, Contract|Hospitality. This demo escalates with a structured packet instead of inventing order status.",
        "tags": ["support", "escalation"],
    },
]

METRIC_PHRASES = {
    "show portfolio": "portfolio",
    "show sales by channel": "by_channel",
    "show sales by family": "by_family",
    "show sales by region": "by_region",
    "show stock risk": "stock_risk",
    "show data quality": "quality",
    "show margin percent": "margin_pct",
    "show price realization": "price_realization",
    "show low margin skus": "low_margin_skus",
    "show margin waterfall": "margin_waterfall",
    "show reorder candidates": "reorder_candidates",
    "show days of cover": "days_of_cover",
    "show seasonality": "seasonal_index",
    "show units by month": "units_by_month",
    "show yoy by family": "yoy_family",
    "show lead vs peak": "lead_vs_peak",
    "show territory performance": "territory_perf",
    "show territory coverage": "territory_coverage",
    "show whitespace": "whitespace",
    "show plan vs season": "plan_vs_season",
    "show rep leaderboard": "rep_leaderboard",
    "show rep grades": "rep_grade",
    "show vendor scorecard": "vendor_scorecard",
    "show vendor otif": "vendor_otif",
}

# Sales-org, procurement, inventory, and MRP metrics share the same governed contract.
METRICS.update(supply_chain.SC_METRICS)
METRIC_PHRASES.update(supply_chain.SC_PHRASES)


def connect(path=DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def initialize(c):
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS territories(
          territory_id TEXT PRIMARY KEY, name TEXT, region TEXT, capacity_dealers INTEGER
        );
        CREATE TABLE IF NOT EXISTS salespeople(
          rep_id TEXT PRIMARY KEY, name TEXT, territory_id TEXT,
          hire_month TEXT, quarterly_quota_cents INTEGER
        );
        CREATE TABLE IF NOT EXISTS vendors(
          vendor_id TEXT PRIMARY KEY, name TEXT, country TEXT
        );
        CREATE TABLE IF NOT EXISTS dealers(
          dealer_id TEXT PRIMARY KEY, name TEXT, region TEXT, channel_focus TEXT,
          city TEXT, territory_id TEXT
        );
        CREATE TABLE IF NOT EXISTS products(
          sku_id TEXT PRIMARY KEY, name TEXT, family TEXT, designer TEXT,
          finish TEXT, list_price_cents INTEGER, lead_band TEXT,
          cost_cents INTEGER, vendor_id TEXT, safety_stock INTEGER
        );
        CREATE TABLE IF NOT EXISTS bronze(
          event_id TEXT PRIMARY KEY, dealer_id TEXT, source_id TEXT, version INTEGER,
          op TEXT, payload TEXT, received_at TEXT
        );
        CREATE INDEX IF NOT EXISTS bronze_fact ON bronze(dealer_id, source_id, version);
        CREATE TABLE IF NOT EXISTS silver_facts(
          dealer_id TEXT, sku_id TEXT, version INTEGER, channel TEXT, family TEXT, region TEXT,
          units_sold INTEGER, net_sales_cents INTEGER, margin_cents INTEGER, on_hand INTEGER,
          lead_band TEXT, rep_id TEXT, cost_cents INTEGER,
          PRIMARY KEY(dealer_id, sku_id)
        );
        CREATE INDEX IF NOT EXISTS silver_scope ON silver_facts(dealer_id, channel, family);
        CREATE INDEX IF NOT EXISTS silver_rep ON silver_facts(rep_id);
        CREATE TABLE IF NOT EXISTS silver_monthly(
          dealer_id TEXT, sku_id TEXT, month TEXT, units_sold INTEGER,
          net_sales_cents INTEGER, margin_cents INTEGER, family TEXT, channel TEXT,
          region TEXT, rep_id TEXT,
          PRIMARY KEY(dealer_id, sku_id, month)
        );
        CREATE INDEX IF NOT EXISTS monthly_scope ON silver_monthly(dealer_id, month, family);
        CREATE TABLE IF NOT EXISTS silver_vendor_kpi(
          vendor_id TEXT PRIMARY KEY, otif_pct REAL, defect_pct REAL,
          avg_lead_days REAL, promised_lead_days REAL, shipments INTEGER
        );
        CREATE TABLE IF NOT EXISTS quarantine(
          event_id TEXT PRIMARY KEY, dealer_id TEXT, source_id TEXT, reason TEXT
        );
        CREATE TABLE IF NOT EXISTS runs(
          run_id TEXT PRIMARY KEY, finished_at TEXT, accepted INTEGER, duplicates INTEGER,
          quarantined INTEGER, current_facts INTEGER, duration_ms REAL
        );
        CREATE TABLE IF NOT EXISTS audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, dealer_id TEXT, metric TEXT, rows_returned INTEGER
        );
        DROP VIEW IF EXISTS gold_channel_family;
        CREATE VIEW gold_channel_family AS
          SELECT dealer_id, channel, region, family,
            SUM(units_sold) AS units_sold,
            SUM(net_sales_cents)/100.0 AS net_sales,
            SUM(margin_cents)/100.0 AS margin,
            SUM(on_hand) AS on_hand
          FROM silver_facts
          GROUP BY dealer_id, channel, region, family;
        """
    )
    c.executescript(supply_chain.DDL)
    c.commit()


def now():
    return datetime.now(timezone.utc).isoformat()


def _month_keys(n=24):
    """Return last n YYYY-MM keys ending at a fixed demo month (2026-09)."""
    end_y, end_m = 2026, 9
    out = []
    y, m = end_y, end_m
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    out.reverse()
    return out


def seed_dims(rng, dealers=50):
    territories = [
        (tid, name, region, 8)
        for tid, name, region in TERRITORY_DEFS
    ]
    vendors = list(VENDOR_NAMES)
    reps = []
    for i in range(1, 21):
        ter = TERRITORY_DEFS[(i - 1) % len(TERRITORY_DEFS)]
        reps.append(
            (
                f"REP-{i:03d}",
                f"Rep {chr(64 + ((i - 1) % 26) + 1)}. Lighting {i:03d}",
                ter[0],
                f"202{1 + (i % 4)}-{(i % 12) + 1:02d}",
                rng.randrange(180_000_00, 420_000_00),  # quarterly quota cents
            )
        )
    ds = []
    for i in range(1, dealers + 1):
        did = f"DLR-{i:04d}"
        region = REGIONS[(i - 1) % len(REGIONS)]
        focus = CHANNELS[(i - 1) % len(CHANNELS)]
        region_ters = [t for t in TERRITORY_DEFS if t[2] == region]
        ter = region_ters[(i - 1) % len(region_ters)]
        ds.append(
            (
                did,
                f"{region} Lighting Studio {i:04d}",
                region,
                focus,
                f"City {i}",
                ter[0],
            )
        )
    return territories, vendors, reps, ds


def seed_catalog(dealers=50, skus=200):
    rng = random.Random(42)
    territories, vendors, reps, ds = seed_dims(rng, dealers)
    ps, es = [], []
    for i in range(1, skus + 1):
        sid = f"SKU-{i:04d}"
        family = FAMILIES[(i - 1) % len(FAMILIES)]
        designer = DESIGNERS[(i - 1) % len(DESIGNERS)]
        price = rng.randrange(25000, 450000)
        band = LEAD_BANDS[(i - 1) % len(LEAD_BANDS)]
        finish = rng.choice(["Antique Brass", "Polished Nickel", "Soft Brass", "Alabaster", "Matte Black"])
        vendor_id = VENDOR_NAMES[(i - 1) % len(VENDOR_NAMES)][0]
        cost = int(price * rng.uniform(0.42, 0.62))
        safety = SAFETY_BY_LEAD[band]
        ps.append(
            (sid, f"{designer} {family} {i:04d}", family, designer, finish, price, band, cost, vendor_id, safety)
        )

    reps_by_ter = {}
    for r in reps:
        reps_by_ter.setdefault(r[2], []).append(r[0])

    for d in ds:
        did, _, region, _, _, territory_id = d
        ter_reps = reps_by_ter.get(territory_id) or [reps[0][0]]
        chosen = rng.sample(ps, k=min(8, len(ps)))
        for n, p in enumerate(chosen, start=1):
            sku_id, _, family, _, _, list_price, lead_band, cost_cents, _, _ = p
            channel = CHANNELS[(hash(did + sku_id) % 3)]
            # Channel mix tilts margin: Contract richer, Consumer thinner
            if channel == "Contract":
                disc = rng.uniform(0.72, 0.95)
                mrate = rng.uniform(0.38, 0.48)
            elif channel == "Trade":
                disc = rng.uniform(0.62, 0.88)
                mrate = rng.uniform(0.32, 0.42)
            else:
                disc = rng.uniform(0.55, 0.82)
                mrate = rng.uniform(0.26, 0.36)
            units = rng.randrange(1, 40)
            net = int(list_price * units * disc)
            # Prefer cost-consistent margin when possible
            cost_total = cost_cents * units
            margin = max(0, net - cost_total)
            if margin > net * 0.55:
                margin = int(net * mrate)
            on_hand = rng.randrange(0, 25)
            rep_id = ter_reps[(hash(did + sku_id)) % len(ter_reps)]
            payload = {
                "sku_id": sku_id,
                "channel": channel,
                "family": family,
                "region": region,
                "units_sold": units,
                "net_sales_cents": net,
                "margin_cents": margin,
                "on_hand": on_hand,
                "lead_band": lead_band,
                "rep_id": rep_id,
                "cost_cents": cost_cents,
                "currency": "USD",
                "amount_unit": "cents",
            }
            if n == 1 and int(did[-4:]) % 17 == 0:
                payload["net_sales_cents"] = -100
            if n == 2 and int(did[-4:]) % 19 == 0:
                payload["channel"] = "Mystery"
            source = sku_id
            e = {
                "event_id": f"{did}-{source}-v1",
                "dealer_id": did,
                "source_id": source,
                "version": 1,
                "op": "upsert",
                "payload": payload,
            }
            es.append(e)
            if n == 3 and int(did[-4:]) % 11 == 0:
                es.append(dict(e))
    return territories, vendors, reps, ds, ps, es


def canonical(event, dealer):
    if event["op"] == "delete":
        return None
    p = event["payload"]
    required = [
        "sku_id",
        "channel",
        "family",
        "region",
        "units_sold",
        "net_sales_cents",
        "margin_cents",
        "on_hand",
        "lead_band",
        "rep_id",
        "cost_cents",
        "currency",
        "amount_unit",
    ]
    if any(k not in p for k in required):
        raise ValueError("missing_field")
    if p["sku_id"] != event["source_id"]:
        raise ValueError("identity_mismatch")
    if p["currency"] != "USD" or p["amount_unit"] != "cents":
        raise ValueError("unsupported_currency_or_unit")
    if p["channel"] not in CHANNELS:
        raise ValueError("unknown_channel")
    if p["family"] not in FAMILIES:
        raise ValueError("unknown_family")
    for key in ("units_sold", "net_sales_cents", "margin_cents", "on_hand", "cost_cents"):
        if type(p[key]) is not int or p[key] < 0:
            raise ValueError("invalid_amount")
    if p["margin_cents"] > p["net_sales_cents"]:
        raise ValueError("margin_exceeds_sales")
    if p["lead_band"] not in LEAD_BANDS:
        raise ValueError("unknown_lead_band")
    if not isinstance(p["rep_id"], str) or not p["rep_id"]:
        raise ValueError("unknown_rep")
    return (
        event["dealer_id"],
        p["sku_id"],
        event["version"],
        p["channel"],
        p["family"],
        dealer["region"],
        p["units_sold"],
        p["net_sales_cents"],
        p["margin_cents"],
        p["on_hand"],
        p["lead_band"],
        p["rep_id"],
        p["cost_cents"],
    )


def _seed_monthly(c, rng):
    """Build 24 months of synthetic sell-through from current silver_facts + seasonal curves."""
    months = _month_keys(24)
    c.execute("DELETE FROM silver_monthly")
    rows = []
    facts = list(c.execute("SELECT * FROM silver_facts"))
    for f in facts:
        curve = SEASONAL_BY_FAMILY.get(f["family"], _SEASON_BASE)
        base_units = max(1, f["units_sold"])
        # Snapshot units ≈ last-quarter run-rate; distribute with seasonality
        for month in months:
            mon = int(month[5:7])
            mult = curve.get(mon, 1.0) * rng.uniform(0.85, 1.15)
            units = max(0, int(round(base_units / 3.0 * mult / 4.0)))
            if units == 0 and rng.random() < 0.3:
                units = 1
            share = units / max(base_units, 1)
            net = int(f["net_sales_cents"] * share)
            margin = int(f["margin_cents"] * share)
            rows.append(
                (
                    f["dealer_id"],
                    f["sku_id"],
                    month,
                    units,
                    net,
                    margin,
                    f["family"],
                    f["channel"],
                    f["region"],
                    f["rep_id"],
                )
            )
    c.executemany(
        "INSERT INTO silver_monthly VALUES(?,?,?,?,?,?,?,?,?,?)",
        rows,
    )


def _seed_vendor_kpi(c, rng):
    c.execute("DELETE FROM silver_vendor_kpi")
    rows = []
    for vendor_id, _, country in VENDOR_NAMES:
        # Overseas vendors slightly worse OTIF / longer lead
        overseas = country not in ("US", "CA")
        otif = rng.uniform(72, 98) if not overseas else rng.uniform(55, 92)
        defect = rng.uniform(0.5, 4.5) if not overseas else rng.uniform(1.5, 8.0)
        promised = rng.choice([14, 21, 28, 42, 90, 150])
        avg_lead = promised * rng.uniform(0.85, 1.45 if overseas else 1.25)
        shipments = rng.randrange(40, 400)
        rows.append((vendor_id, round(otif, 1), round(defect, 2), round(avg_lead, 1), float(promised), shipments))
    c.executemany("INSERT INTO silver_vendor_kpi VALUES(?,?,?,?,?,?)", rows)


def ingest(c, events):
    started = time.perf_counter()
    accepted = duplicates = 0
    try:
        for e in events:
            if e.get("op") not in ("upsert", "delete") or type(e.get("version")) is not int or e["version"] < 1:
                raise ValueError("Invalid envelope")
            if not c.execute("SELECT 1 FROM dealers WHERE dealer_id=?", (e["dealer_id"],)).fetchone():
                raise ValueError("Unknown dealer")
            payload = json.dumps(e["payload"], sort_keys=True)
            old = c.execute("SELECT * FROM bronze WHERE event_id=?", (e["event_id"],)).fetchone()
            if old:
                tup = (old["dealer_id"], old["source_id"], old["version"], old["op"], old["payload"])
                if tup != (e["dealer_id"], e["source_id"], e["version"], e["op"], payload):
                    raise ValueError("Conflicting event_id")
                duplicates += 1
                continue
            if c.execute(
                "SELECT 1 FROM bronze WHERE dealer_id=? AND source_id=? AND version=?",
                (e["dealer_id"], e["source_id"], e["version"]),
            ).fetchone():
                raise ValueError("Conflicting source version")
            c.execute(
                "INSERT INTO bronze VALUES(?,?,?,?,?,?,?)",
                (e["event_id"], e["dealer_id"], e["source_id"], e["version"], e["op"], payload, now()),
            )
            accepted += 1

        dealer_map = {r["dealer_id"]: dict(r) for r in c.execute("SELECT * FROM dealers")}
        c.execute("DELETE FROM silver_facts")
        c.execute("DELETE FROM quarantine")
        valid = {}
        for row in c.execute("SELECT * FROM bronze ORDER BY dealer_id, source_id, version"):
            e = dict(row)
            e["payload"] = json.loads(e["payload"])
            key = (e["dealer_id"], e["source_id"])
            try:
                valid[key] = canonical(e, dealer_map[e["dealer_id"]])
            except ValueError as err:
                valid[key] = None
                c.execute(
                    "INSERT INTO quarantine VALUES(?,?,?,?)",
                    (e["event_id"], e["dealer_id"], e["source_id"], str(err)),
                )
        c.executemany(
            "INSERT INTO silver_facts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [r for r in valid.values() if r],
        )
        rng = random.Random(99)
        _seed_monthly(c, rng)
        _seed_vendor_kpi(c, rng)
        q = c.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        count = c.execute("SELECT COUNT(*) FROM silver_facts").fetchone()[0]
        result = {
            "run_id": str(uuid.uuid4()),
            "finished_at": now(),
            "accepted": accepted,
            "duplicates": duplicates,
            "quarantined": q,
            "current_facts": count,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        c.execute(
            "INSERT INTO runs VALUES(:run_id,:finished_at,:accepted,:duplicates,:quarantined,:current_facts,:duration_ms)",
            result,
        )
        c.commit()
        return result
    except Exception:
        c.rollback()
        raise


def seed(path=DB, dealers=50, skus=200):
    c = connect(path)
    initialize(c)
    territories, vendors, reps, ds, ps, es = seed_catalog(dealers, skus)
    c.executemany("INSERT OR IGNORE INTO territories VALUES(?,?,?,?)", territories)
    c.executemany("INSERT OR IGNORE INTO vendors VALUES(?,?,?)", vendors)
    c.executemany("INSERT OR IGNORE INTO salespeople VALUES(?,?,?,?,?)", reps)
    c.executemany("INSERT OR IGNORE INTO dealers VALUES(?,?,?,?,?,?)", ds)
    c.executemany("INSERT OR IGNORE INTO products VALUES(?,?,?,?,?,?,?,?,?,?)", ps)
    c.commit()
    result = ingest(c, es)
    result["supply_chain"] = supply_chain.seed_supply_chain(c, random.Random(7), LEAD_MIDPOINT_DAYS)
    c.close()
    return result


def metric_sql(metric, dealer=None, dialect="sqlite"):
    """Governed SQL for a metric. dialect='snowflake' swaps in Gold-backed statements for heavy metrics."""
    if metric not in METRICS:
        raise ValueError("Unknown governed metric")
    spec = METRICS[metric]
    sql = spec["sql"]
    if dialect == "snowflake" and metric in supply_chain.SNOWFLAKE_OVERRIDES:
        sql = supply_chain.SNOWFLAKE_OVERRIDES[metric]
    replacements = {
        "{where}": "WHERE dealer_id=?" if dealer else "",
        "{and_}": "AND" if dealer else "WHERE",
        "{where_sf}": "WHERE sf.dealer_id=?" if dealer else "",
        "{and_sf}": "AND" if dealer else "WHERE",
        "{where_sm}": "WHERE sm.dealer_id=?" if dealer else "",
        "{and_ra}": "AND ra.dealer_id=?" if dealer else "",
        "{where_ter}": (
            "WHERE t.territory_id = (SELECT territory_id FROM dealers WHERE dealer_id=? LIMIT 1)"
            if dealer
            else ""
        ),
    }
    for key, val in replacements.items():
        sql = sql.replace(key, val)
    params = [dealer] * sql.count("?") if dealer else []
    return sql, params


def interpret_metric(question: str) -> str:
    """Closed vocabulary offline metric router — deliberately not an LLM."""
    q = question.strip().lower()
    if q not in METRIC_PHRASES:
        raise ValueError("Offline metrics support: " + ", ".join(METRIC_PHRASES))
    return METRIC_PHRASES[q]


def match_faq(question: str):
    q = question.strip().lower()
    for item in FAQ:
        keys = item["q"].split()
        if item["q"] in q or sum(1 for k in keys if k in q) >= max(2, len(keys) // 2):
            return item
    for item in FAQ:
        if any(t in q for t in item["tags"]):
            return item
    return None


def product_lookup(c, query: str, limit=8):
    q = f"%{query.strip()}%"
    return [
        dict(r)
        for r in c.execute(
            "SELECT * FROM products WHERE name LIKE ? OR family LIKE ? OR designer LIKE ? OR finish LIKE ? LIMIT ?",
            (q, q, q, q, limit),
        )
    ]
