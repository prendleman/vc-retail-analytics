"""Sales-org, procurement, inventory, and MRP domains (synthetic).

Shared contract between the SQLite demo and Snowflake SERVING views: identical table
names and lowercase column names so the governed metric SQL in this module runs on both.
Dates are ISO 'YYYY-MM-DD' strings. Money is cents in Silver, dollars in results.
"""
from __future__ import annotations

import random

AS_OF = "2026-09-30"  # fixed demo "today" (matches core._month_keys end month)

DC_DEFS = [
    ("DC-TX", "Dallas DC", "South", "TX"),
    ("DC-CA", "Ontario CA DC", "West", "CA"),
    ("DC-OH", "Columbus DC", "Midwest", "OH"),
    ("DC-NJ", "Edison DC", "Northeast", "NJ"),
]
COMPONENT_CATEGORIES = ["Brass casting", "Glass shade", "Alabaster", "Socket & wiring", "LED driver", "Fabric shade", "Hardware kit", "Packaging"]
SHIP_MODES = ["ocean", "air", "truck", "rail"]
PO_STATUSES = ["open", "in_transit", "received", "closed", "cancelled"]
WO_STATUSES = ["planned", "released", "in_progress", "complete", "cancelled"]
MRP_EXCEPTIONS = ["none", "expedite", "de_expedite", "cancel", "shortage", "excess"]
FORECAST_METHODS = ["seasonal_naive", "ets", "croston", "override"]

DDL = """
CREATE TABLE IF NOT EXISTS distribution_centers(
  dc_id TEXT PRIMARY KEY, name TEXT, region TEXT, state TEXT
);
CREATE TABLE IF NOT EXISTS rep_assignments(
  rep_id TEXT, dealer_id TEXT, start_month TEXT, end_month TEXT,
  PRIMARY KEY(rep_id, dealer_id, start_month)
);
CREATE TABLE IF NOT EXISTS rep_quotas(
  rep_id TEXT, quarter TEXT, quota_cents INTEGER, PRIMARY KEY(rep_id, quarter)
);
CREATE TABLE IF NOT EXISTS vendor_contracts(
  contract_id TEXT PRIMARY KEY, vendor_id TEXT, start_month TEXT, end_month TEXT,
  promised_lead_days INTEGER, incoterm TEXT, payment_terms_days INTEGER,
  otif_target_pct REAL, min_order_qty INTEGER
);
CREATE TABLE IF NOT EXISTS components(
  component_id TEXT PRIMARY KEY, name TEXT, category TEXT, vendor_id TEXT,
  unit_cost_cents INTEGER, lead_days INTEGER
);
CREATE TABLE IF NOT EXISTS bom(
  parent_sku_id TEXT, component_id TEXT, qty_per INTEGER, PRIMARY KEY(parent_sku_id, component_id)
);
CREATE TABLE IF NOT EXISTS purchase_orders(
  po_id TEXT PRIMARY KEY, vendor_id TEXT, dc_id TEXT, order_date TEXT, promised_date TEXT, status TEXT
);
CREATE INDEX IF NOT EXISTS po_vendor ON purchase_orders(vendor_id, status);
CREATE TABLE IF NOT EXISTS po_lines(
  po_id TEXT, line_no INTEGER, sku_id TEXT, qty_ordered INTEGER, unit_cost_cents INTEGER,
  qty_received INTEGER, promised_date TEXT, PRIMARY KEY(po_id, line_no)
);
CREATE INDEX IF NOT EXISTS po_lines_sku ON po_lines(sku_id);
CREATE TABLE IF NOT EXISTS shipments(
  shipment_id TEXT PRIMARY KEY, po_id TEXT, vendor_id TEXT, dc_id TEXT, ship_date TEXT,
  eta_date TEXT, arrival_date TEXT, mode TEXT, freight_cents INTEGER, cartons INTEGER
);
CREATE TABLE IF NOT EXISTS receipts(
  receipt_id TEXT PRIMARY KEY, shipment_id TEXT, po_id TEXT, line_no INTEGER, sku_id TEXT,
  qty_received INTEGER, qty_defective INTEGER, received_date TEXT
);
CREATE TABLE IF NOT EXISTS inventory_snapshots(
  snapshot_week TEXT, dc_id TEXT, sku_id TEXT, on_hand INTEGER, on_order INTEGER,
  allocated INTEGER, in_transit INTEGER, PRIMARY KEY(snapshot_week, dc_id, sku_id)
);
CREATE TABLE IF NOT EXISTS demand_forecast(
  month TEXT, dc_id TEXT, sku_id TEXT, forecast_units INTEGER, forecast_method TEXT,
  PRIMARY KEY(month, dc_id, sku_id)
);
CREATE TABLE IF NOT EXISTS mrp_plan(
  plan_id TEXT PRIMARY KEY, run_month TEXT, dc_id TEXT, sku_id TEXT, net_requirement INTEGER,
  planned_order_qty INTEGER, planned_release_date TEXT, due_date TEXT, exception_code TEXT
);
CREATE INDEX IF NOT EXISTS mrp_run ON mrp_plan(run_month, exception_code);
CREATE TABLE IF NOT EXISTS work_orders(
  wo_id TEXT PRIMARY KEY, sku_id TEXT, dc_id TEXT, qty INTEGER, start_date TEXT, due_date TEXT, status TEXT
);
"""

TABLES = [
    "distribution_centers", "rep_assignments", "rep_quotas", "vendor_contracts", "components", "bom",
    "purchase_orders", "po_lines", "shipments", "receipts", "inventory_snapshots", "demand_forecast",
    "mrp_plan", "work_orders",
]


# ----------------------------------------------------------------------------- helpers
def _add_days(iso: str, days: int) -> str:
    from datetime import date, timedelta

    y, m, d = (int(x) for x in iso.split("-"))
    return (date(y, m, d) + timedelta(days=days)).isoformat()


def _month_add(month: str, k: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + k
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def quarter_of(month: str) -> str:
    m = int(month[5:7])
    return f"{month[:4]}-Q{(m + 2) // 3}"


def _week_keys(n: int, end: str = AS_OF):
    out = []
    cur = end
    for _ in range(n):
        out.append(cur)
        cur = _add_days(cur, -7)
    out.reverse()
    return out


# ----------------------------------------------------------------------------- seed
def seed_supply_chain(c, rng: random.Random | None = None, lead_days_by_band=None):
    """Populate sales-org, procurement, inventory, and MRP tables from the current Silver layer.

    Idempotent: clears and rebuilds every table in TABLES. Volumes are derived from
    dealers/products already in the db so tests with small seeds stay fast.
    """
    rng = rng or random.Random(7)
    lead_days_by_band = lead_days_by_band or {"in_stock": 7, "2_4_weeks": 21, "4_8_weeks": 42, "custom_overseas": 180}
    c.executescript(DDL)
    for t in TABLES:
        c.execute(f"DELETE FROM {t}")

    products = [dict(r) for r in c.execute("SELECT * FROM products ORDER BY sku_id")]
    vendors = [dict(r) for r in c.execute("SELECT * FROM vendors ORDER BY vendor_id")]
    reps = [dict(r) for r in c.execute("SELECT * FROM salespeople ORDER BY rep_id")]
    dealers = [dict(r) for r in c.execute("SELECT * FROM dealers ORDER BY dealer_id")]
    months = [r[0] for r in c.execute("SELECT DISTINCT month FROM silver_monthly ORDER BY month")]
    if not months:
        months = [_month_add("2026-09", -k) for k in range(23, -1, -1)]
    latest_month = months[-1]
    sku_units = {
        r["sku_id"]: r["u"]
        for r in c.execute("SELECT sku_id, SUM(units_sold) AS u FROM silver_facts GROUP BY sku_id")
    }

    # Distribution centers
    c.executemany("INSERT INTO distribution_centers VALUES(?,?,?,?)", DC_DEFS)
    dc_by_region = {region: dc_id for dc_id, _, region, _ in DC_DEFS}
    dc_ids = [d[0] for d in DC_DEFS]

    # Rep assignments: current rep from silver_facts majority + ~20% with a prior rep history
    cur_rep = {
        r["dealer_id"]: r["rep_id"]
        for r in c.execute(
            "SELECT dealer_id, rep_id FROM (SELECT dealer_id, rep_id, COUNT(*) n FROM silver_facts "
            "GROUP BY dealer_id, rep_id) GROUP BY dealer_id HAVING n = MAX(n)"
        )
    }
    ra = []
    rep_ids = [r["rep_id"] for r in reps] or ["REP-001"]
    for d in dealers:
        rep = cur_rep.get(d["dealer_id"]) or rng.choice(rep_ids)
        start = _month_add(latest_month, -rng.randrange(6, 30))
        if rng.random() < 0.2 and len(rep_ids) > 1:
            prev = rng.choice([x for x in rep_ids if x != rep])
            ra.append((prev, d["dealer_id"], _month_add(start, -rng.randrange(12, 36)), _month_add(start, -1)))
        ra.append((rep, d["dealer_id"], start, None))
    c.executemany("INSERT OR IGNORE INTO rep_assignments VALUES(?,?,?,?)", ra)

    # Rep quotas by quarter: calibrated to each rep's average quarterly actual (so attainment lands ~80-120%),
    # with 3-6% annual growth and Q4/Q1 seasonality. Falls back to salespeople.quarterly_quota_cents.
    quarters = sorted({quarter_of(m) for m in months})
    rep_qtr_actual = {
        r["rep_id"]: r["avg_q"]
        for r in c.execute(
            "SELECT rep_id, AVG(q_cents) AS avg_q FROM (SELECT rep_id, substr(month,1,4) || ((CAST(substr(month,6,2) AS INTEGER)+2)/3) AS q, "
            "SUM(net_sales_cents) AS q_cents FROM silver_monthly GROUP BY rep_id, q) GROUP BY rep_id"
        )
    }
    rq = []
    for r in reps:
        base = rep_qtr_actual.get(r["rep_id"]) or r["quarterly_quota_cents"] or 250_000_00
        base = base * rng.uniform(0.85, 1.15)
        for i, qtr in enumerate(quarters):
            growth = (1.0 + rng.uniform(0.03, 0.06)) ** (i / 4.0)
            seasonal = 1.12 if qtr.endswith("Q4") else (0.92 if qtr.endswith("Q1") else 1.0)
            rq.append((r["rep_id"], qtr, int(base * growth * seasonal)))
    c.executemany("INSERT INTO rep_quotas VALUES(?,?,?)", rq)

    # Vendor contracts
    vc = []
    for v in vendors:
        overseas = v["country"] not in ("US", "CA")
        vc.append(
            (
                f"CTR-{v['vendor_id']}-2025",
                v["vendor_id"],
                "2025-01",
                "2026-12",
                rng.choice([60, 90, 120, 150] if overseas else [14, 21, 28, 42]),
                rng.choice(["FOB", "CIF", "DDP"]) if overseas else "FOB",
                rng.choice([30, 45, 60, 90]),
                rng.choice([92.0, 95.0, 97.0]),
                rng.choice([10, 25, 50, 100]),
            )
        )
    c.executemany("INSERT INTO vendor_contracts VALUES(?,?,?,?,?,?,?,?,?)", vc)
    contract_lead = {row[1]: row[4] for row in vc}

    # Components + BOM (3-5 components per SKU; material cost ~55-85% of standard cost)
    n_comp = max(24, min(400, len(products) // 3))
    comps = []
    for i in range(1, n_comp + 1):
        cat = COMPONENT_CATEGORIES[(i - 1) % len(COMPONENT_CATEGORIES)]
        v = vendors[(i - 1) % len(vendors)] if vendors else {"vendor_id": None, "country": "US"}
        overseas = v["country"] not in ("US", "CA")
        comps.append(
            (
                f"CMP-{i:04d}",
                f"{cat} {i:04d}",
                cat,
                v["vendor_id"],
                rng.randrange(400, 18000),
                rng.choice([45, 60, 90, 120] if overseas else [7, 14, 21, 30]),
            )
        )
    c.executemany("INSERT INTO components VALUES(?,?,?,?,?,?)", comps)
    bom = []
    comps_by_cost = sorted(comps, key=lambda cmp: cmp[4])
    for p in products:
        k = rng.randrange(3, 6)
        target = p["cost_cents"] * rng.uniform(0.55, 0.85)
        # Pick components the SKU can afford (unit cost <= ~40% of material target); cheap SKUs draw from the low end.
        affordable = [cmp for cmp in comps_by_cost if cmp[4] <= target * 0.4] or comps_by_cost[: max(3, len(comps_by_cost) // 6)]
        chosen = rng.sample(affordable, k=min(k, len(affordable)))
        weights = [rng.uniform(0.5, 1.5) for _ in chosen]
        wsum = sum(weights)
        for cmp, w in zip(chosen, weights):
            qty = max(1, int(round(target * w / wsum / max(cmp[4], 1))))
            bom.append((p["sku_id"], cmp[0], qty))
    c.executemany("INSERT OR IGNORE INTO bom VALUES(?,?,?)", bom)

    # Purchase orders / lines / shipments / receipts over the trailing 12 months
    prods_by_vendor: dict[str, list] = {}
    for p in products:
        prods_by_vendor.setdefault(p["vendor_id"], []).append(p)
    n_po = max(40, len(products) * 3 // 4)
    pos, lines, ships, recs = [], [], [], []
    po_months = months[-12:]
    for i in range(1, n_po + 1):
        v = vendors[(i - 1) % len(vendors)] if vendors else None
        if not v:
            break
        overseas = v["country"] not in ("US", "CA")
        dc = rng.choice(dc_ids)
        month = rng.choice(po_months)
        order_date = f"{month}-{rng.randrange(1, 28):02d}"
        lead = contract_lead.get(v["vendor_id"], 30)
        promised = _add_days(order_date, lead)
        # Status by promised date relative to AS_OF
        if promised > AS_OF:
            status = rng.choice(["open", "open", "in_transit"])
        else:
            status = rng.choices(["received", "closed", "open", "in_transit", "cancelled"], weights=[45, 35, 8, 8, 4])[0]
        po_id = f"PO-{i:06d}"
        pos.append((po_id, v["vendor_id"], dc, order_date, promised, status))
        vendor_prods = prods_by_vendor.get(v["vendor_id"]) or products
        po_lines_local = []
        for ln, p in enumerate(rng.sample(vendor_prods, k=min(rng.randrange(2, 7), len(vendor_prods))), start=1):
            qty = rng.choice([10, 20, 25, 40, 50, 100])
            unit_cost = int(p["cost_cents"] * rng.uniform(0.95, 1.08))
            if status in ("received", "closed"):
                qty_rcv = qty if rng.random() < 0.82 else int(qty * rng.uniform(0.6, 0.98))
            elif status == "in_transit":
                qty_rcv = 0
            elif status == "cancelled":
                qty_rcv = 0
            else:
                qty_rcv = 0 if rng.random() < 0.7 else int(qty * rng.uniform(0.2, 0.8))
            po_lines_local.append((po_id, ln, p["sku_id"], qty, unit_cost, qty_rcv, promised))
        lines.extend(po_lines_local)
        if status in ("received", "closed", "in_transit") or (status == "open" and any(l[5] > 0 for l in po_lines_local)):
            late_bias = 1.25 if overseas else 1.08
            transit = max(3, int(lead * rng.uniform(0.75, late_bias)))
            ship_date = _add_days(order_date, max(1, lead - transit))
            eta = _add_days(ship_date, transit)
            arrival = None if status == "in_transit" else _add_days(ship_date, int(transit * rng.uniform(0.9, 1.3 if overseas else 1.15)))
            mode = rng.choice(["ocean", "ocean", "air"] if overseas else ["truck", "truck", "rail"])
            value = sum(l[3] * l[4] for l in po_lines_local)
            freight_rate = {"ocean": 0.04, "air": 0.14, "truck": 0.05, "rail": 0.035}[mode]
            sid = f"SHP-{i:06d}"
            ships.append((sid, po_id, v["vendor_id"], dc, ship_date, eta, arrival, mode, int(value * freight_rate * rng.uniform(0.8, 1.3)), rng.randrange(2, 60)))
            if arrival:
                for l in [l for l in po_lines_local if l[5] > 0]:
                    defect_rate = rng.uniform(0.0, 0.06 if overseas else 0.025)
                    recs.append((f"RCT-{i:06d}-{l[1]}", sid, po_id, l[1], l[2], l[5], int(l[5] * defect_rate), arrival))
    c.executemany("INSERT INTO purchase_orders VALUES(?,?,?,?,?,?)", pos)
    c.executemany("INSERT INTO po_lines VALUES(?,?,?,?,?,?,?)", lines)
    c.executemany("INSERT INTO shipments VALUES(?,?,?,?,?,?,?,?,?,?)", ships)
    c.executemany("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)", recs)

    # Inventory snapshots: 13 weekly snapshots per DC x SKU, trending toward current dealer on-hand
    on_order_by_sku: dict[str, int] = {}
    po_status_by_id = {p[0]: p[5] for p in pos}
    for l in lines:
        if po_status_by_id[l[0]] in ("open", "in_transit"):
            on_order_by_sku[l[2]] = on_order_by_sku.get(l[2], 0) + (l[3] - l[5])
    weeks = _week_keys(13)
    inv = []
    for p in products:
        weekly_demand = max(1, sku_units.get(p["sku_id"], 4) / 13.0)
        for dc in dc_ids:
            level = int(weekly_demand * rng.uniform(2, 10))
            for w in weeks:
                level = max(0, int(level - weekly_demand * rng.uniform(0.5, 1.5) + (weekly_demand * rng.uniform(4, 9) if rng.random() < 0.18 else 0)))
                allocated = int(level * rng.uniform(0.0, 0.5)) + (rng.randrange(1, 4) if rng.random() < 0.05 else 0)
                in_transit = int(on_order_by_sku.get(p["sku_id"], 0) * rng.uniform(0.0, 0.4)) if w == weeks[-1] else rng.randrange(0, 5)
                inv.append((w, dc, p["sku_id"], level, on_order_by_sku.get(p["sku_id"], 0) // len(dc_ids) if w == weeks[-1] else rng.randrange(0, 40), allocated, in_transit))
    c.executemany("INSERT OR IGNORE INTO inventory_snapshots VALUES(?,?,?,?,?,?,?)", inv)

    # Demand forecast: calibrated to actual family-month totals from silver_monthly, split by DC, with noise + bias
    actual = {
        (r["sku_id"], r["month"]): r["u"]
        for r in c.execute("SELECT sku_id, month, SUM(units_sold) AS u FROM silver_monthly GROUP BY sku_id, month")
    }
    family_bias = {f: rng.uniform(-0.12, 0.12) for f in sorted({p["family"] for p in products})}
    fc = []
    fc_months = months[-12:] + [_month_add(latest_month, k) for k in range(1, 4)]
    for p in products:
        method = FORECAST_METHODS[sum(ord(ch) for ch in p["sku_id"]) % len(FORECAST_METHODS)]
        for m in fc_months:
            base = actual.get((p["sku_id"], m))
            if base is None:
                base = actual.get((p["sku_id"], _month_add(m, -12)), sku_units.get(p["sku_id"], 3) / 3.0)
            total = max(0.0, base * (1.0 + family_bias[p["family"]]) * rng.uniform(0.7, 1.3))
            shares = [rng.random() for _ in dc_ids]
            s = sum(shares) or 1.0
            for dc, sh in zip(dc_ids, shares):
                fc.append((m, dc, p["sku_id"], int(round(total * sh / s)), method))
    c.executemany("INSERT OR IGNORE INTO demand_forecast VALUES(?,?,?,?,?)", fc)

    # MRP plan (latest run): net requirement = forecast next 3 mo - available - on order; exceptions
    latest_inv = {(r["dc_id"], r["sku_id"]): dict(r) for r in c.execute("SELECT * FROM inventory_snapshots WHERE snapshot_week=?", (weeks[-1],))}
    fc3 = {}
    for m, dc, sku, units, _ in fc:
        if m > latest_month:
            fc3[(dc, sku)] = fc3.get((dc, sku), 0) + units
    mrp, wos = [], []
    for p in products:
        lead = lead_days_by_band.get(p["lead_band"], 30)
        for dc in dc_ids:
            snap = latest_inv.get((dc, p["sku_id"]), {"on_hand": 0, "allocated": 0, "on_order": 0, "in_transit": 0})
            demand = fc3.get((dc, p["sku_id"]), 0)
            available = snap["on_hand"] - snap["allocated"] + snap["on_order"] + snap["in_transit"]
            net_req = demand + p["safety_stock"] - available
            if net_req > 0:
                planned = max(net_req, 5)
                due = _add_days(AS_OF, rng.randrange(14, 75))
                release = _add_days(due, -lead)
                if release < AS_OF and (snap["on_hand"] - snap["allocated"]) < demand * 0.3:
                    exc = "shortage"
                elif release < AS_OF:
                    exc = "expedite"
                else:
                    exc = "none"
            else:
                planned = 0
                due = release = None
                if available > demand * 3 + p["safety_stock"] * 2 and snap["on_order"] > 0:
                    exc = rng.choice(["cancel", "de_expedite"])
                elif available > demand * 4 + p["safety_stock"] * 3:
                    exc = "excess"
                else:
                    exc = "none"
            mrp.append((f"MRP-{latest_month}-{dc}-{p['sku_id']}", latest_month, dc, p["sku_id"], int(net_req), int(planned), release, due, exc))
            if planned > 0 and p["family"] in ("Lamps", "Alabaster", "Cordless") and rng.random() < 0.5:
                start = _add_days(AS_OF, rng.randrange(-30, 20))
                wdue = _add_days(start, rng.randrange(7, 28))
                status = rng.choices(WO_STATUSES, weights=[25, 25, 25, 20, 5])[0]
                if start < AS_OF and status == "planned":
                    status = "released"
                wos.append((f"WO-{dc}-{p['sku_id']}", p["sku_id"], dc, int(planned), start, wdue, status))
    c.executemany("INSERT OR IGNORE INTO mrp_plan VALUES(?,?,?,?,?,?,?,?,?)", mrp)
    c.executemany("INSERT OR IGNORE INTO work_orders VALUES(?,?,?,?,?,?,?)", wos)
    c.commit()
    return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}


# ----------------------------------------------------------------------------- governed metrics
_QTR = (
    "substr(month,1,4) || CASE WHEN substr(month,6,2) IN ('01','02','03') THEN '-Q1' "
    "WHEN substr(month,6,2) IN ('04','05','06') THEN '-Q2' "
    "WHEN substr(month,6,2) IN ('07','08','09') THEN '-Q3' ELSE '-Q4' END"
)

SC_METRICS = {
    # ---- sales org
    "rep_attainment": {
        "description": "Quarterly quota attainment by salesperson (actual monthly sell-through vs quota history).",
        "sql": (
            "WITH q AS ("
            f"  SELECT rep_id, {_QTR} AS quarter, SUM(net_sales_cents) AS net_cents, SUM(margin_cents) AS margin_cents "
            "  FROM silver_monthly {where} GROUP BY rep_id, quarter"
            ") "
            "SELECT q.rep_id, sp.name AS rep, q.quarter, q.net_cents/100.0 AS net_sales, "
            "ROUND(100.0 * q.margin_cents / NULLIF(q.net_cents, 0), 1) AS margin_pct, "
            "rq.quota_cents/100.0 AS quota, "
            "ROUND(100.0 * q.net_cents / NULLIF(rq.quota_cents, 0), 1) AS attainment_pct "
            "FROM q JOIN salespeople sp ON sp.rep_id = q.rep_id "
            "LEFT JOIN rep_quotas rq ON rq.rep_id = q.rep_id AND rq.quarter = q.quarter "
            "WHERE q.quarter >= '2025-Q4' "
            "ORDER BY q.quarter DESC, attainment_pct DESC LIMIT 60"
        ),
    },
    "rep_coverage": {
        "description": "Dealer assignments per rep: active vs historical, and dealers with no active rep.",
        "sql": (
            "SELECT sp.rep_id, sp.name AS rep, t.name AS territory, sp.hire_month, "
            "COUNT(ra.dealer_id) AS assignments, "
            "SUM(CASE WHEN ra.end_month IS NULL THEN 1 ELSE 0 END) AS active_dealers, "
            "SUM(CASE WHEN ra.end_month IS NOT NULL THEN 1 ELSE 0 END) AS transitioned, "
            "MIN(CASE WHEN ra.end_month IS NULL THEN ra.start_month END) AS longest_tenure_since "
            "FROM salespeople sp "
            "LEFT JOIN rep_assignments ra ON ra.rep_id = sp.rep_id {and_ra} "
            "LEFT JOIN territories t ON t.territory_id = sp.territory_id "
            "GROUP BY sp.rep_id, sp.name, t.name, sp.hire_month ORDER BY active_dealers DESC, sp.rep_id"
        ),
    },
    # ---- procurement
    "po_past_due": {
        "description": "Open purchase-order lines past promised date by vendor, with open and past-due value.",
        "sql": (
            "SELECT v.vendor_id, v.name AS vendor, v.country, COUNT(*) AS open_lines, "
            f"SUM(CASE WHEN pl.promised_date < '{AS_OF}' THEN 1 ELSE 0 END) AS past_due_lines, "
            f"SUM(CASE WHEN pl.promised_date < '{AS_OF}' THEN (pl.qty_ordered - pl.qty_received) * pl.unit_cost_cents ELSE 0 END)/100.0 AS past_due_value, "
            "SUM((pl.qty_ordered - pl.qty_received) * pl.unit_cost_cents)/100.0 AS open_value, "
            f"ROUND(100.0 * SUM(CASE WHEN pl.promised_date < '{AS_OF}' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS past_due_pct "
            "FROM po_lines pl JOIN purchase_orders po ON po.po_id = pl.po_id "
            "JOIN vendors v ON v.vendor_id = po.vendor_id "
            "WHERE po.status IN ('open','in_transit') AND pl.qty_ordered > pl.qty_received "
            "GROUP BY v.vendor_id, v.name, v.country ORDER BY past_due_value DESC"
        ),
    },
    "inbound_pipeline": {
        "description": "Open on-order value and units by promised month (inbound supply pipeline).",
        "sql": (
            "SELECT substr(pl.promised_date, 1, 7) AS month, COUNT(DISTINCT po.po_id) AS pos, "
            "SUM(pl.qty_ordered - pl.qty_received) AS units_on_order, "
            "SUM((pl.qty_ordered - pl.qty_received) * pl.unit_cost_cents)/100.0 AS on_order_value, "
            "SUM(CASE WHEN po.status = 'in_transit' THEN (pl.qty_ordered - pl.qty_received) * pl.unit_cost_cents ELSE 0 END)/100.0 AS in_transit_value "
            "FROM po_lines pl JOIN purchase_orders po ON po.po_id = pl.po_id "
            "WHERE po.status IN ('open','in_transit') AND pl.qty_ordered > pl.qty_received "
            "GROUP BY substr(pl.promised_date, 1, 7) ORDER BY month"
        ),
    },
    "vendor_otif_detail": {
        "description": "Vendor OTIF from receipts: on-time (arrival <= promised) and in-full (received >= ordered) per PO, vs contract target.",
        "sql": (
            "WITH line_agg AS ("
            "  SELECT po_id, SUM(qty_ordered) AS ordered, SUM(qty_received) AS received FROM po_lines GROUP BY po_id"
            "), ship_agg AS ("
            "  SELECT po_id, MAX(arrival_date) AS arrival FROM shipments WHERE arrival_date IS NOT NULL GROUP BY po_id"
            "), perf AS ("
            "  SELECT po.po_id, po.vendor_id, "
            "  CASE WHEN s.arrival <= po.promised_date THEN 1 ELSE 0 END AS on_time, "
            "  CASE WHEN l.received >= l.ordered THEN 1 ELSE 0 END AS in_full "
            "  FROM purchase_orders po JOIN line_agg l ON l.po_id = po.po_id JOIN ship_agg s ON s.po_id = po.po_id "
            "  WHERE po.status IN ('received','closed')"
            ") "
            "SELECT v.vendor_id, v.name AS vendor, v.country, COUNT(*) AS pos_closed, "
            "ROUND(100.0 * SUM(p.on_time) / NULLIF(COUNT(*), 0), 1) AS on_time_pct, "
            "ROUND(100.0 * SUM(p.in_full) / NULLIF(COUNT(*), 0), 1) AS in_full_pct, "
            "ROUND(100.0 * SUM(p.on_time * p.in_full) / NULLIF(COUNT(*), 0), 1) AS otif_pct, "
            "vc.otif_target_pct AS target_pct, vc.promised_lead_days AS contract_lead_days, "
            "CASE WHEN 100.0 * SUM(p.on_time * p.in_full) / NULLIF(COUNT(*), 0) >= vc.otif_target_pct THEN 'Meets' ELSE 'Below target' END AS status "
            "FROM perf p JOIN vendors v ON v.vendor_id = p.vendor_id "
            "LEFT JOIN vendor_contracts vc ON vc.vendor_id = v.vendor_id "
            "GROUP BY v.vendor_id, v.name, v.country, vc.otif_target_pct, vc.promised_lead_days ORDER BY otif_pct ASC"
        ),
    },
    "vendor_defects": {
        "description": "Receiving quality by vendor: defective units per million received.",
        "sql": (
            "SELECT v.vendor_id, v.name AS vendor, v.country, COUNT(*) AS receipt_lines, "
            "SUM(r.qty_received) AS units_received, SUM(r.qty_defective) AS units_defective, "
            "ROUND(1000000.0 * SUM(r.qty_defective) / NULLIF(SUM(r.qty_received), 0), 0) AS defect_ppm "
            "FROM receipts r JOIN purchase_orders po ON po.po_id = r.po_id JOIN vendors v ON v.vendor_id = po.vendor_id "
            "GROUP BY v.vendor_id, v.name, v.country ORDER BY defect_ppm DESC"
        ),
    },
    "vendor_concentration": {
        "description": "Spend share and single-sourced SKU exposure by vendor (concentration risk).",
        "sql": (
            "WITH spend AS ("
            "  SELECT po.vendor_id, SUM(pl.qty_ordered * pl.unit_cost_cents) AS spend_cents, COUNT(DISTINCT pl.sku_id) AS skus_bought "
            "  FROM po_lines pl JOIN purchase_orders po ON po.po_id = pl.po_id WHERE po.status <> 'cancelled' GROUP BY po.vendor_id"
            "), total AS (SELECT SUM(spend_cents) AS all_cents FROM spend), "
            "sourced AS (SELECT vendor_id, COUNT(*) AS single_source_skus FROM products GROUP BY vendor_id) "
            "SELECT v.vendor_id, v.name AS vendor, v.country, s.spend_cents/100.0 AS spend, "
            "ROUND(100.0 * s.spend_cents / NULLIF(t.all_cents, 0), 1) AS share_pct, s.skus_bought, "
            "COALESCE(so.single_source_skus, 0) AS single_source_skus, "
            "CASE WHEN 100.0 * s.spend_cents / NULLIF(t.all_cents, 0) >= 20 THEN 'Concentrated' "
            "WHEN v.country NOT IN ('US','CA') AND COALESCE(so.single_source_skus, 0) >= 10 THEN 'Overseas single-source' ELSE 'Ok' END AS risk_flag "
            "FROM spend s JOIN vendors v ON v.vendor_id = s.vendor_id CROSS JOIN total t "
            "LEFT JOIN sourced so ON so.vendor_id = v.vendor_id ORDER BY share_pct DESC"
        ),
    },
    "freight_cost": {
        "description": "Inbound freight as % of PO value by mode and origin country.",
        "sql": (
            "WITH po_value AS (SELECT po_id, SUM(qty_ordered * unit_cost_cents) AS value_cents FROM po_lines GROUP BY po_id) "
            "SELECT s.mode, v.country, COUNT(*) AS shipments, SUM(s.freight_cents)/100.0 AS freight, "
            "SUM(pv.value_cents)/100.0 AS po_value, "
            "ROUND(100.0 * SUM(s.freight_cents) / NULLIF(SUM(pv.value_cents), 0), 1) AS freight_pct, "
            "SUM(CASE WHEN s.arrival_date IS NOT NULL AND s.arrival_date > s.eta_date THEN 1 ELSE 0 END) AS late_arrivals "
            "FROM shipments s JOIN purchase_orders po ON po.po_id = s.po_id JOIN vendors v ON v.vendor_id = po.vendor_id "
            "JOIN po_value pv ON pv.po_id = s.po_id "
            "GROUP BY s.mode, v.country ORDER BY freight_pct DESC"
        ),
    },
    # ---- inventory / planning
    "dc_inventory_health": {
        "description": "Latest weekly snapshot by distribution center: on-hand, allocated, available, on-order, oversold SKUs.",
        "sql": (
            "SELECT dc.dc_id, dc.name AS dc, dc.region, COUNT(*) AS skus, "
            "SUM(s.on_hand) AS on_hand, SUM(s.allocated) AS allocated, SUM(s.on_hand - s.allocated) AS available, "
            "SUM(s.on_order) AS on_order, SUM(s.in_transit) AS in_transit, "
            "SUM(CASE WHEN s.on_hand - s.allocated < 0 THEN 1 ELSE 0 END) AS oversold_skus, "
            "SUM(CASE WHEN s.on_hand = 0 THEN 1 ELSE 0 END) AS stockout_skus "
            "FROM inventory_snapshots s JOIN distribution_centers dc ON dc.dc_id = s.dc_id "
            "WHERE s.snapshot_week = (SELECT MAX(snapshot_week) FROM inventory_snapshots) "
            "GROUP BY dc.dc_id, dc.name, dc.region ORDER BY available ASC"
        ),
    },
    "inventory_trend": {
        "description": "Weekly on-hand and on-order units by DC (13-week trend).",
        "sql": (
            "SELECT s.snapshot_week, s.dc_id, SUM(s.on_hand) AS on_hand, SUM(s.on_order) AS on_order, "
            "SUM(s.allocated) AS allocated FROM inventory_snapshots s "
            "GROUP BY s.snapshot_week, s.dc_id ORDER BY s.snapshot_week, s.dc_id"
        ),
    },
    "mrp_exceptions": {
        "description": "Latest MRP run exception messages by DC (expedite / de-expedite / cancel / shortage / excess).",
        "sql": (
            "SELECT dc.dc_id, dc.name AS dc, m.exception_code, COUNT(*) AS skus, "
            "SUM(m.planned_order_qty) AS planned_units, SUM(m.net_requirement) AS net_requirement "
            "FROM mrp_plan m JOIN distribution_centers dc ON dc.dc_id = m.dc_id "
            "WHERE m.run_month = (SELECT MAX(run_month) FROM mrp_plan) AND m.exception_code <> 'none' "
            "GROUP BY dc.dc_id, dc.name, m.exception_code ORDER BY skus DESC"
        ),
    },
    "mrp_shortages": {
        "description": "Shortage / expedite SKUs from the latest MRP run with vendor and lead-time context.",
        "sql": (
            "SELECT m.dc_id, m.sku_id, p.family, p.lead_band, v.name AS vendor, m.net_requirement, "
            "m.planned_order_qty, m.planned_release_date, m.due_date, m.exception_code, "
            f"CASE WHEN m.planned_release_date < '{AS_OF}' THEN 'Release overdue' ELSE 'On plan' END AS release_status "
            "FROM mrp_plan m JOIN products p ON p.sku_id = m.sku_id LEFT JOIN vendors v ON v.vendor_id = p.vendor_id "
            "WHERE m.run_month = (SELECT MAX(run_month) FROM mrp_plan) AND m.exception_code IN ('shortage','expedite') "
            "ORDER BY m.net_requirement DESC LIMIT 40"
        ),
    },
    "forecast_accuracy": {
        "description": "Forecast vs actual units by family over trailing 12 months: weighted MAPE and bias (corporate, all DCs).",
        "sql": (
            "WITH f AS ("
            "  SELECT p.family, df.month, SUM(df.forecast_units) AS forecast_units "
            "  FROM demand_forecast df JOIN products p ON p.sku_id = df.sku_id GROUP BY p.family, df.month"
            "), a AS ("
            "  SELECT family, month, SUM(units_sold) AS actual_units FROM silver_monthly GROUP BY family, month"
            ") "
            "SELECT f.family, COUNT(*) AS months, SUM(f.forecast_units) AS forecast_units, SUM(a.actual_units) AS actual_units, "
            "ROUND(100.0 * SUM(ABS(f.forecast_units - a.actual_units)) / NULLIF(SUM(a.actual_units), 0), 1) AS wmape_pct, "
            "ROUND(100.0 * (SUM(f.forecast_units) - SUM(a.actual_units)) / NULLIF(SUM(a.actual_units), 0), 1) AS bias_pct "
            "FROM f JOIN a ON a.family = f.family AND a.month = f.month "
            "GROUP BY f.family ORDER BY wmape_pct DESC"
        ),
    },
    "bom_cost_rollup": {
        "description": "BOM material cost vs standard cost per SKU; flags over-standard roll-ups and longest component lead.",
        "sql": (
            "SELECT p.sku_id, p.name, p.family, p.cost_cents/100.0 AS standard_cost, "
            "SUM(b.qty_per * c.unit_cost_cents)/100.0 AS bom_material_cost, "
            "ROUND(100.0 * SUM(b.qty_per * c.unit_cost_cents) / NULLIF(p.cost_cents, 0), 1) AS material_pct_of_std, "
            "COUNT(*) AS components, MAX(c.lead_days) AS longest_component_lead_days, "
            "CASE WHEN SUM(b.qty_per * c.unit_cost_cents) > p.cost_cents THEN 'Over standard' ELSE 'Within' END AS flag "
            "FROM bom b JOIN products p ON p.sku_id = b.parent_sku_id JOIN components c ON c.component_id = b.component_id "
            "GROUP BY p.sku_id, p.name, p.family, p.cost_cents ORDER BY material_pct_of_std DESC LIMIT 40"
        ),
    },
    "component_risk": {
        "description": "Long-lead or overseas components by number of SKUs using them and trailing sales exposed.",
        "sql": (
            "WITH sku_sales AS (SELECT sku_id, SUM(net_sales_cents) AS net_cents FROM silver_facts {where} GROUP BY sku_id) "
            "SELECT c.component_id, c.name AS component, c.category, v.name AS vendor, v.country, c.lead_days, "
            "COUNT(DISTINCT b.parent_sku_id) AS skus_using, COALESCE(SUM(ss.net_cents), 0)/100.0 AS sales_exposed "
            "FROM components c JOIN bom b ON b.component_id = c.component_id "
            "LEFT JOIN vendors v ON v.vendor_id = c.vendor_id "
            "LEFT JOIN sku_sales ss ON ss.sku_id = b.parent_sku_id "
            "WHERE c.lead_days >= 45 OR v.country NOT IN ('US','CA') "
            "GROUP BY c.component_id, c.name, c.category, v.name, v.country, c.lead_days "
            "ORDER BY sales_exposed DESC LIMIT 40"
        ),
    },
    "work_order_status": {
        "description": "Assembly work orders by DC and status with late counts (due before as-of, not complete).",
        "sql": (
            "SELECT w.dc_id, w.status, COUNT(*) AS work_orders, SUM(w.qty) AS units, "
            f"SUM(CASE WHEN w.due_date < '{AS_OF}' AND w.status NOT IN ('complete','cancelled') THEN 1 ELSE 0 END) AS late "
            "FROM work_orders w GROUP BY w.dc_id, w.status ORDER BY w.dc_id, w.status"
        ),
    },
}

SC_PHRASES = {
    "show rep attainment": "rep_attainment",
    "show rep coverage": "rep_coverage",
    "show past due pos": "po_past_due",
    "show inbound pipeline": "inbound_pipeline",
    "show vendor otif detail": "vendor_otif_detail",
    "show vendor defects": "vendor_defects",
    "show vendor concentration": "vendor_concentration",
    "show freight cost": "freight_cost",
    "show dc inventory": "dc_inventory_health",
    "show inventory trend": "inventory_trend",
    "show mrp exceptions": "mrp_exceptions",
    "show shortages": "mrp_shortages",
    "show forecast accuracy": "forecast_accuracy",
    "show bom cost": "bom_cost_rollup",
    "show component risk": "component_risk",
    "show work orders": "work_order_status",
}

# Snowflake dialect: heavy metrics read Gold-backed SERVING views (pre-aggregated in 08_silver_gold.sql) instead of
# scanning 130M-row snapshots / 150M-row forecasts on the serving warehouse. Same output columns as the SQLite SQL.
SNOWFLAKE_OVERRIDES = {
    "inventory_trend": (
        "SELECT snapshot_week, dc_id, on_hand, on_order, allocated FROM gold_inventory_weekly_dc ORDER BY snapshot_week, dc_id"
    ),
    "dc_inventory_health": (
        "SELECT dc.dc_id, dc.name AS dc, dc.region, g.skus, g.on_hand, g.allocated, g.on_hand - g.allocated AS available, "
        "g.on_order, g.in_transit, g.oversold_skus, g.stockout_skus "
        "FROM gold_inventory_weekly_dc g JOIN distribution_centers dc ON dc.dc_id = g.dc_id "
        "WHERE g.snapshot_week = (SELECT MAX(snapshot_week) FROM gold_inventory_weekly_dc) ORDER BY available ASC"
    ),
    "forecast_accuracy": (
        "WITH f AS (SELECT family, month, forecast_units FROM gold_forecast_family_month), "
        "a AS (SELECT family, month, SUM(units_sold) AS actual_units FROM silver_monthly GROUP BY family, month) "
        "SELECT f.family, COUNT(*) AS months, SUM(f.forecast_units) AS forecast_units, SUM(a.actual_units) AS actual_units, "
        "ROUND(100.0 * SUM(ABS(f.forecast_units - a.actual_units)) / NULLIF(SUM(a.actual_units), 0), 1) AS wmape_pct, "
        "ROUND(100.0 * (SUM(f.forecast_units) - SUM(a.actual_units)) / NULLIF(SUM(a.actual_units), 0), 1) AS bias_pct "
        "FROM f JOIN a ON a.family = f.family AND a.month = f.month GROUP BY f.family ORDER BY wmape_pct DESC"
    ),
    "mrp_exceptions": (
        "SELECT dc.dc_id, dc.name AS dc, g.exception_code, g.skus, g.planned_units, g.net_requirement "
        "FROM gold_mrp_exception_summary g JOIN distribution_centers dc ON dc.dc_id = g.dc_id "
        "WHERE g.run_month = (SELECT MAX(run_month) FROM gold_mrp_exception_summary) AND g.exception_code <> 'none' ORDER BY g.skus DESC"
    ),
    "vendor_scorecard": (
        "SELECT vendor_id, name, country, otif_pct, quality_pct, lead_reliability, margin_pct, score, "
        "CASE WHEN score >= 80 THEN 'Prefer' WHEN score >= 60 THEN 'Watch' ELSE 'Exit' END AS tier "
        "FROM gold_vendor_scorecard ORDER BY score DESC"
    ),
}

# Metrics that span corporate supply chain (not dealer-keyed). Dealer sessions still see them;
# dealer scope applies only where a {where}/{and_ra} token is present.
CORPORATE_METRICS = {
    "po_past_due", "inbound_pipeline", "vendor_otif_detail", "vendor_defects", "vendor_concentration",
    "freight_cost", "dc_inventory_health", "inventory_trend", "mrp_exceptions", "mrp_shortages",
    "forecast_accuracy", "bom_cost_rollup", "work_order_status",
}
