"""Public-estimate calibrated competitor landscape (synthetic).

Not Visual Comfort production data. Third-party public scraps (Growjo, LinkedIn,
Grand View, Mordor named peers, Accio) plus explicit assumptions — see
docs/VC_PUBLIC_CALIBRATION.md and docs/KNOWN_LIMITATIONS.md.

Frame: US decorative / designer lighting competitive set (~$5.0B synthetic TAM).
Visual Comfort placed at ~$750M (~15% of that set) to match the portfolio
calibration. Competitor revenues are estimates / midpoints of public ranges.
"""
from __future__ import annotations

# US decorative+designer competitive set (synthetic TAM, $ millions)
TAM_M = 5000.0
OUR_REVENUE_M = 750.0  # matches VC_PUBLIC_CALIBRATION upper-band target

# National competitors. is_us=1 is our synthetic brand row.
# revenue_m: public scrap or midpoint of published range; long_tail fills TAM.
COMPETITORS = [
    # id, name, tier, revenue_m, ownership, hq, source_note
    ("VC", "Visual Comfort (synthetic us)", "premium_designer", OUR_REVENUE_M, "PE-backed (public)", "Houston, TX", "Calibration target ~$750M; not a filed figure"),
    ("KIC", "Kichler Lighting", "mid_decorative", 450.0, "Private", "Solon, OH", "LinkedIn est. ~$550M — modeled mid-decorative at $450M"),
    ("HIN", "Hinkley Lighting", "premium_designer", 80.0, "Family-owned", "Avon Lake, OH", "IncFact band $10–100M — midpoint used"),
    ("HVL", "Hudson Valley Lighting Group", "premium_designer", 50.0, "Family-owned", "Wappingers Falls, NY", "Growjo ~$44M / LinkedIn lower — use $50M"),
    ("CUR", "Currey & Company", "premium_designer", 55.0, "Private", "Atlanta, GA", "Assumption — public peer in designer showrooms"),
    ("SAV", "Savoy House", "mid_decorative", 40.0, "Private", "US", "Named peer in residential fixture reports — assumption"),
    ("SCH", "Schonbek", "luxury_crystal", 35.0, "Private", "US", "Crystal/luxury peer — assumption"),
    ("EUR", "Eurofase", "mid_decorative", 55.0, "Private", "Canada / US", "CB Insights listed alternative — assumption"),
    ("WAC", "WAC Lighting", "architectural_mid", 120.0, "Private", "Port Washington, NY", "IncFact-adjacent peer list — assumption"),
    ("MIN", "Minka Group", "mid_decorative", 95.0, "Ferguson (public parent)", "US", "Named in Grand View residential fixtures — assumption"),
    ("MAX", "Maxim / Livex / Golden cluster", "value_mid", 160.0, "Fragmented", "US", "Bundled mid/value peers often listed with VC — assumption"),
    ("IMP", "EU design imports (FLOS / Artemide set)", "luxury_import", 70.0, "Various", "EU / US showrooms", "Mordor named set — synthetic US presence"),
    ("OTH", "Long-tail / other decorative", "long_tail", 3040.0, "Fragmented", "US", "Residual to fill $5.0B synthetic TAM"),
]

# Family × competitor strength weights (relative, sum≈1 per family across named peers).
# Higher = competitor is stronger in that family vs our brand. Used to allocate their
# national revenue into family pools and surface expansion targets.
FAMILY_STRENGTH = {
    # Ceiling / chandeliers: VC strong; crystal & imports compete; HVL/Hinkley strong
    "Ceiling": {"VC": 0.22, "KIC": 0.10, "HIN": 0.12, "HVL": 0.14, "CUR": 0.08, "SAV": 0.05, "SCH": 0.10, "EUR": 0.06, "WAC": 0.03, "MIN": 0.04, "MAX": 0.04, "IMP": 0.02},
    "Wall": {"VC": 0.18, "KIC": 0.12, "HIN": 0.14, "HVL": 0.12, "CUR": 0.08, "SAV": 0.06, "SCH": 0.04, "EUR": 0.08, "WAC": 0.06, "MIN": 0.05, "MAX": 0.05, "IMP": 0.02},
    "Lamps": {"VC": 0.16, "KIC": 0.14, "HIN": 0.08, "HVL": 0.08, "CUR": 0.12, "SAV": 0.08, "SCH": 0.03, "EUR": 0.08, "WAC": 0.04, "MIN": 0.06, "MAX": 0.10, "IMP": 0.03},
    "Outdoor": {"VC": 0.12, "KIC": 0.18, "HIN": 0.16, "HVL": 0.06, "CUR": 0.04, "SAV": 0.06, "SCH": 0.01, "EUR": 0.04, "WAC": 0.10, "MIN": 0.08, "MAX": 0.12, "IMP": 0.03},
    "Fans": {"VC": 0.14, "KIC": 0.10, "HIN": 0.06, "HVL": 0.03, "CUR": 0.02, "SAV": 0.03, "SCH": 0.01, "EUR": 0.03, "WAC": 0.08, "MIN": 0.28, "MAX": 0.18, "IMP": 0.04},
    "Alabaster": {"VC": 0.28, "KIC": 0.04, "HIN": 0.08, "HVL": 0.12, "CUR": 0.14, "SAV": 0.04, "SCH": 0.06, "EUR": 0.06, "WAC": 0.02, "MIN": 0.02, "MAX": 0.04, "IMP": 0.10},
    "Cordless": {"VC": 0.20, "KIC": 0.08, "HIN": 0.06, "HVL": 0.05, "CUR": 0.08, "SAV": 0.05, "SCH": 0.02, "EUR": 0.10, "WAC": 0.12, "MIN": 0.04, "MAX": 0.10, "IMP": 0.10},
}

# Region tilt: competitor over/under-index vs national (multiply family $).
REGION_TILT = {
    "South": {"VC": 1.15, "KIC": 1.05, "HIN": 0.95, "HVL": 0.85, "CUR": 1.10, "OTH": 1.0},
    "Northeast": {"VC": 0.95, "KIC": 0.90, "HIN": 0.85, "HVL": 1.25, "CUR": 0.95, "IMP": 1.20, "OTH": 1.0},
    "West": {"VC": 1.05, "KIC": 1.00, "HIN": 1.00, "HVL": 0.90, "WAC": 1.15, "EUR": 1.10, "OTH": 1.0},
    "Midwest": {"VC": 0.90, "KIC": 1.15, "HIN": 1.25, "HVL": 0.80, "MIN": 1.10, "MAX": 1.10, "OTH": 1.0},
}

CAPTURE_RATE = 0.08  # demo assumption: win 8% of addressable competitor $ in a soft/contested cell


def _sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def competitors_cte() -> str:
    """UNION ALL SELECT literals — works on SQLite and Snowflake."""
    parts = []
    for cid, name, tier, rev, ownership, hq, note in COMPETITORS:
        parts.append(
            "SELECT "
            f"{_sql_str(cid)} AS competitor_id, {_sql_str(name)} AS name, {_sql_str(tier)} AS tier, "
            f"{rev} AS revenue_m, {_sql_str(ownership)} AS ownership, {_sql_str(hq)} AS hq, "
            f"{_sql_str(note)} AS source_note, "
            f"{1 if cid == 'VC' else 0} AS is_us"
        )
    return " UNION ALL ".join(parts)


def family_strength_cte() -> str:
    parts = []
    for family, weights in FAMILY_STRENGTH.items():
        for cid, w in weights.items():
            parts.append(
                f"SELECT {_sql_str(family)} AS family, {_sql_str(cid)} AS competitor_id, {w} AS strength_w"
            )
    return " UNION ALL ".join(parts)


def region_tilt_cte() -> str:
    parts = []
    for region, tilts in REGION_TILT.items():
        for cid, t in tilts.items():
            parts.append(
                f"SELECT {_sql_str(region)} AS region, {_sql_str(cid)} AS competitor_id, {t} AS tilt"
            )
    # Default tilt 1.0 for any competitor not listed per region is handled in SQL via COALESCE
    return " UNION ALL ".join(parts)


DDL = """
CREATE TABLE IF NOT EXISTS competitors(
  competitor_id TEXT PRIMARY KEY, name TEXT, tier TEXT, revenue_m REAL,
  ownership TEXT, hq TEXT, source_note TEXT, is_us INTEGER
);
CREATE TABLE IF NOT EXISTS competitor_family_strength(
  family TEXT, competitor_id TEXT, strength_w REAL,
  PRIMARY KEY(family, competitor_id)
);
CREATE TABLE IF NOT EXISTS competitor_region_tilt(
  region TEXT, competitor_id TEXT, tilt REAL,
  PRIMARY KEY(region, competitor_id)
);
CREATE TABLE IF NOT EXISTS market_tam(
  market TEXT PRIMARY KEY, tam_m REAL, note TEXT
);
"""


def ensure_competitors(c) -> None:
    """Idempotent seed for SQLite (and any dialect that accepts this DDL)."""
    c.executescript(DDL)
    c.execute("DELETE FROM competitors")
    c.execute("DELETE FROM competitor_family_strength")
    c.execute("DELETE FROM competitor_region_tilt")
    c.execute("DELETE FROM market_tam")
    c.executemany(
        "INSERT INTO competitors VALUES(?,?,?,?,?,?,?,?)",
        [(a, b, c_, d, e, f, g, 1 if a == "VC" else 0) for a, b, c_, d, e, f, g in COMPETITORS],
    )
    fam_rows = [(fam, cid, w) for fam, weights in FAMILY_STRENGTH.items() for cid, w in weights.items()]
    c.executemany("INSERT INTO competitor_family_strength VALUES(?,?,?)", fam_rows)
    tilt_rows = [(reg, cid, t) for reg, tilts in REGION_TILT.items() for cid, t in tilts.items()]
    c.executemany("INSERT INTO competitor_region_tilt VALUES(?,?,?)", tilt_rows)
    c.execute(
        "INSERT INTO market_tam VALUES(?,?,?)",
        (
            "us_decorative_designer",
            TAM_M,
            "Synthetic US decorative/designer competitive set; VC ~$750M ≈ 15% share",
        ),
    )
    c.commit()


# Governed metrics — CTE literals so Snowflake path works without a cloud rebuild.
COMP_METRICS = {
    "competitor_landscape": {
        "description": "Public-estimate competitor landscape for US decorative/designer lighting (synthetic TAM).",
        "sql": (
            "WITH c AS ({competitors_cte}), "
            f"tot AS (SELECT {TAM_M} AS tam_m) "
            "SELECT c.competitor_id, c.name, c.tier, c.revenue_m, "
            "ROUND(100.0 * c.revenue_m / tot.tam_m, 1) AS share_pct, "
            "c.ownership, c.hq, c.is_us, c.source_note "
            "FROM c CROSS JOIN tot ORDER BY c.revenue_m DESC"
        ),
    },
    "competitive_position": {
        "description": "Our synthetic brand vs named competitors — revenue and share of the decorative/designer set.",
        "sql": (
            "WITH c AS ({competitors_cte}), "
            f"tot AS (SELECT {TAM_M} AS tam_m), "
            "us AS (SELECT revenue_m AS our_m FROM c WHERE is_us = 1) "
            "SELECT c.name, c.tier, c.revenue_m, "
            "ROUND(100.0 * c.revenue_m / tot.tam_m, 1) AS share_pct, "
            "ROUND(c.revenue_m / NULLIF(us.our_m, 0), 2) AS vs_us, "
            "CASE WHEN c.is_us = 1 THEN 'Us' "
            "WHEN c.revenue_m >= us.our_m * 0.5 THEN 'Scale peer' "
            "WHEN c.tier IN ('premium_designer','luxury_crystal','luxury_import') THEN 'Designer peer' "
            "ELSE 'Share target' END AS position "
            "FROM c CROSS JOIN tot CROSS JOIN us "
            "WHERE c.competitor_id <> 'OTH' "
            "ORDER BY c.revenue_m DESC"
        ),
    },
    "competitor_family_share": {
        "description": "Estimated competitor $ by product family (strength-weighted allocation of national revenue).",
        "sql": (
            "WITH c AS ({competitors_cte}), "
            "fs AS ({family_strength_cte}), "
            "norm AS (SELECT family, SUM(strength_w) AS wsum FROM fs GROUP BY family), "
            "alloc AS ("
            "  SELECT fs.family, c.competitor_id, c.name, c.tier, c.is_us, "
            "  ROUND(c.revenue_m * fs.strength_w / NULLIF(n.wsum, 0), 1) AS family_revenue_m "
            "  FROM fs JOIN c ON c.competitor_id = fs.competitor_id "
            "  JOIN norm n ON n.family = fs.family "
            "  WHERE c.competitor_id <> 'OTH'"
            "), "
            "fam_tot AS (SELECT family, SUM(family_revenue_m) AS pool_m FROM alloc GROUP BY family) "
            "SELECT a.family, a.name, a.tier, a.family_revenue_m, "
            "ROUND(100.0 * a.family_revenue_m / NULLIF(f.pool_m, 0), 1) AS family_share_pct, a.is_us "
            "FROM alloc a JOIN fam_tot f ON f.family = a.family "
            "ORDER BY a.family, a.family_revenue_m DESC"
        ),
    },
    "share_expansion": {
        "description": "Expansion into competitor share: family × competitor $ we under-index, × assumed capture rate.",
        "sql": (
            "WITH c AS ({competitors_cte}), "
            "fs AS ({family_strength_cte}), "
            "norm AS (SELECT family, SUM(strength_w) AS wsum FROM fs GROUP BY family), "
            "alloc AS ("
            "  SELECT fs.family, c.competitor_id, c.name, c.tier, "
            "  c.revenue_m * fs.strength_w / NULLIF(n.wsum, 0) AS family_revenue_m, "
            "  fs.strength_w AS their_strength, "
            "  (SELECT strength_w FROM fs x WHERE x.family = fs.family AND x.competitor_id = 'VC') AS our_strength "
            "  FROM fs JOIN c ON c.competitor_id = fs.competitor_id "
            "  JOIN norm n ON n.family = fs.family "
            "  WHERE c.is_us = 0 AND c.competitor_id <> 'OTH'"
            "), "
            "our_mix AS ("
            "  SELECT family, SUM(net_sales_cents) AS net_cents FROM silver_facts {where} GROUP BY family"
            "), "
            "our_tot AS (SELECT SUM(net_cents) AS all_cents FROM our_mix), "
            "mix AS ("
            "  SELECT o.family, ROUND(100.0 * o.net_cents / NULLIF(t.all_cents, 0), 1) AS our_mix_pct "
            "  FROM our_mix o CROSS JOIN our_tot t"
            ") "
            "SELECT a.family, a.name AS competitor, a.tier, "
            "ROUND(a.family_revenue_m, 1) AS competitor_family_m, "
            "ROUND(a.their_strength, 3) AS their_strength, "
            "ROUND(a.our_strength, 3) AS our_strength, "
            "COALESCE(m.our_mix_pct, 0) AS our_portfolio_mix_pct, "
            "ROUND(CASE WHEN a.their_strength > a.our_strength "
            f"  THEN a.family_revenue_m * (a.their_strength - a.our_strength) / NULLIF(a.their_strength, 0) * {CAPTURE_RATE} "
            "  ELSE 0 END, 2) AS expansion_m, "
            "CASE WHEN a.their_strength > a.our_strength * 1.25 THEN 'Priority take-share' "
            "WHEN a.their_strength > a.our_strength THEN 'Contested' ELSE 'Defend' END AS play "
            "FROM alloc a LEFT JOIN mix m ON m.family = a.family "
            "WHERE a.their_strength > a.our_strength "
            "ORDER BY expansion_m DESC LIMIT 40"
        ),
    },
    "region_expansion": {
        "description": "Regional expansion: competitor tilt × underweight vs our regional mix (synthetic).",
        "sql": (
            "WITH c AS ({competitors_cte}), "
            "rt AS ({region_tilt_cte}), "
            "reg_sales AS ("
            "  SELECT region, SUM(net_sales_cents)/100.0 AS net_sales FROM silver_facts {where} GROUP BY region"
            "), "
            "reg_tot AS (SELECT SUM(net_sales) AS all_sales FROM reg_sales), "
            "reg_mix AS ("
            "  SELECT r.region, r.net_sales, ROUND(100.0 * r.net_sales / NULLIF(t.all_sales, 0), 1) AS our_region_pct "
            "  FROM reg_sales r CROSS JOIN reg_tot t"
            ") "
            "SELECT rt.region, c.name AS competitor, c.tier, "
            "ROUND(c.revenue_m, 1) AS competitor_national_m, "
            "ROUND(rt.tilt, 2) AS region_tilt, "
            "COALESCE(m.our_region_pct, 0) AS our_region_mix_pct, "
            "ROUND(c.revenue_m * rt.tilt * "
            f"CASE WHEN rt.tilt > 1.05 THEN {CAPTURE_RATE} ELSE {CAPTURE_RATE * 0.5} END, 2) AS expansion_m, "
            "CASE WHEN rt.tilt >= 1.15 THEN 'Competitor stronghold' "
            "WHEN rt.tilt >= 1.05 THEN 'Contested region' ELSE 'Parity' END AS play "
            "FROM c JOIN rt ON rt.competitor_id = c.competitor_id "
            "LEFT JOIN reg_mix m ON m.region = rt.region "
            "WHERE c.is_us = 0 AND c.competitor_id NOT IN ('OTH') AND rt.tilt >= 1.05 "
            "ORDER BY expansion_m DESC LIMIT 40"
        ),
    },
}

COMP_PHRASES = {
    "show competitor landscape": "competitor_landscape",
    "show competitors": "competitor_landscape",
    "show competitive position": "competitive_position",
    "show competitor family share": "competitor_family_share",
    "show share expansion": "share_expansion",
    "show expansion opportunity": "share_expansion",
    "show region expansion": "region_expansion",
}

CORPORATE_COMP_METRICS = {
    "competitor_landscape",
    "competitive_position",
    "competitor_family_share",
    # share_expansion / region_expansion use silver_facts — dealer-scoped where clause applies
}
