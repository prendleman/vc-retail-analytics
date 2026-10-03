"""Explicit AQ Snowflake setup, staged ingestion, 10 TB backbone build, and validation. No embedded credentials.

Order (see docs/SNOWFLAKE.md):
  doctor -> platform -> load -> transform -> backbone -> generate -> build -> governance -> semantic -> validate -> reconcile
`backbone`, `generate`, `build` run on AQ_VC_BUILD_WH (LARGE) and are gated behind --confirm-cost.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import tempfile
import time
from pathlib import Path

from app.core import DB, ROOT, connect
from app.supply_chain import AS_OF

SQL_DIR = ROOT / "sql" / "snowflake"
BUILD_WH = "AQ_VC_BUILD_WH"
SERVE_WH = "AQ_VC_RETAIL_WH"

# Rough credit expectations per heavy step on a LARGE warehouse (8 credits/hour). Printed, not enforced.
COST_HINTS = {
    "backbone": "~1-2 credits (dimension merges + one pass over TPC-DS inventory, 783M rows)",
    "generate": "~0.5-1.5 credits at scale 1.0 (2M POs / ~8M lines / 1.6M BOM rows)",
    "build": "~4-8 credits (two passes over TPC-DS store/catalog/web sales, ~50B rows; 150M-row forecast)",
}


def _template_vars(a) -> dict:
    scale = max(0.01, a.scale)
    return {
        "BUILD_WH": BUILD_WH,
        "BUILD_TIMEOUT": str(a.build_timeout),
        "AS_OF": AS_OF,
        "YEAR_SHIFT": "24",  # TPC-DS 2000-10..2002-09 -> 2024-10..2026-09
        "INV_WEEKS": "13",
        "SAMPLE_MOD": str(a.sample_mod),  # keep 1 in N tickets/orders of the TPC-DS retailer volume
        "QTY_DIV": "25",  # TPC-DS qty 1..100 -> 1..4 units per line
        "INV_DIV": "100",  # TPC-DS on-hand 0..1000 -> 0..10 per DC x SKU
        "VENDOR_COUNT": str(max(12, int(60 * min(scale, 1.0)) or 12)),
        "REP_COUNT": str(max(40, int(600 * min(scale, 1.0)))),
        "COMPONENT_COUNT": str(max(500, int(50_000 * scale))),
        "PO_ROWS": str(max(1_000, int(2_000_000 * scale))),
        "DEMO_DEALER_COUNT": str(a.demo_dealers),
        "SCALE": str(scale),
    }


def _render(path: Path, variables: dict) -> str:
    sql = path.read_text(encoding="utf-8")
    missing = set(re.findall(r"\{\{(\w+)\}\}", sql)) - set(variables)
    if missing:
        raise SystemExit(f"{path.name}: unresolved template vars {sorted(missing)}")
    for k, v in variables.items():
        sql = sql.replace("{{" + k + "}}", v)
    return sql


def _split(sql: str) -> list[str]:
    """Split on ';' outside $$...$$ bodies; drop comment-only lines."""
    chunks, buf, in_dollar = [], [], False
    for raw in sql.splitlines():
        ln = raw.rstrip()
        if ln.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        if not in_dollar and ln.strip().startswith("--"):
            continue
        if not ln.strip():
            continue
        buf.append(ln)
        if not in_dollar and ln.strip().endswith(";"):
            chunks.append("\n".join(buf))
            buf = []
    if buf:
        chunks.append("\n".join(buf) + ";")
    return chunks


def _run_sql(c, sql: str, echo_rows: bool = False, tolerate: tuple[str, ...] = ()):
    for i, stmt in enumerate(_split(sql), start=1):
        started = time.perf_counter()
        try:
            cur = c.cursor().execute(stmt)
            rows = cur.fetchall() if cur.description else []
        except Exception as e:  # pragma: no cover - live only
            msg = str(e)
            if any(t.lower() in msg.lower() for t in tolerate):
                print(f"  [{i}] tolerated: {msg.splitlines()[0][:120]}")
                continue
            print(f"  [{i}] FAILED after {time.perf_counter() - started:.1f}s:\n{stmt[:600]}")
            raise
        dur = time.perf_counter() - started
        head = stmt.strip().splitlines()[0][:90]
        if echo_rows and rows:
            cols = [d[0] for d in cur.description]
            print(f"  [{i}] {head}")
            for r in rows[:40]:
                print("      ", dict(zip(cols, r)))
        elif dur > 5 or i % 10 == 0:
            print(f"  [{i}] {dur:6.1f}s  {head}")


def _run_sql_file(c, path: Path, variables: dict, echo_rows: bool = False, tolerate: tuple[str, ...] = ()):
    print(f"== {path.name}")
    _run_sql(c, _render(path, variables), echo_rows=echo_rows, tolerate=tolerate)


def _suspend_build_wh(c):
    try:
        c.cursor().execute(f"ALTER WAREHOUSE {BUILD_WH} SUSPEND")
        print(f"  {BUILD_WH} suspended.")
    except Exception as e:  # already suspended or no privilege
        print(f"  (suspend {BUILD_WH}: {str(e).splitlines()[0][:100]})")


def _load(c):
    """Stage the local synthetic seed (dims + events) into BRONZE. Idempotent MERGEs."""
    local = connect(DB)
    try:
        data = {
            "territories": [dict(r) for r in local.execute("SELECT * FROM territories")],
            "salespeople": [dict(r) for r in local.execute("SELECT * FROM salespeople")],
            "vendors": [dict(r) for r in local.execute("SELECT * FROM vendors")],
            "dealers": [dict(r) for r in local.execute("SELECT * FROM dealers")],
            "products": [dict(r) for r in local.execute("SELECT * FROM products")],
            "monthly": [dict(r) for r in local.execute("SELECT * FROM silver_monthly")],
            "vendor_kpi": [dict(r) for r in local.execute("SELECT * FROM silver_vendor_kpi")],
            "events": [dict(r) for r in local.execute("SELECT * FROM bronze")],
        }
    finally:
        local.close()
    for e in data["events"]:
        e["payload"] = json.loads(e["payload"])

    merges = {
        "territories": (
            "BRONZE.TERRITORIES", "TERRITORY_ID",
            "V:territory_id::VARCHAR territory_id, V:name::VARCHAR name, V:region::VARCHAR region, V:capacity_dealers::NUMBER capacity_dealers",
            ["territory_id", "name", "region", "capacity_dealers"],
        ),
        "salespeople": (
            "BRONZE.SALESPEOPLE", "REP_ID",
            "V:rep_id::VARCHAR rep_id, V:name::VARCHAR name, V:territory_id::VARCHAR territory_id, V:hire_month::VARCHAR hire_month, V:quarterly_quota_cents::NUMBER quarterly_quota_cents",
            ["rep_id", "name", "territory_id", "hire_month", "quarterly_quota_cents"],
        ),
        "vendors": (
            "BRONZE.VENDORS", "VENDOR_ID",
            "V:vendor_id::VARCHAR vendor_id, V:name::VARCHAR name, V:country::VARCHAR country",
            ["vendor_id", "name", "country"],
        ),
        "dealers": (
            "BRONZE.DEALERS", "DEALER_ID",
            "V:dealer_id::VARCHAR dealer_id, V:name::VARCHAR name, V:region::VARCHAR region, V:channel_focus::VARCHAR channel_focus, V:city::VARCHAR city, V:territory_id::VARCHAR territory_id",
            ["dealer_id", "name", "region", "channel_focus", "city", "territory_id"],
        ),
        "products": (
            "BRONZE.PRODUCTS", "SKU_ID",
            "V:sku_id::VARCHAR sku_id, V:name::VARCHAR name, V:family::VARCHAR family, V:designer::VARCHAR designer, V:finish::VARCHAR finish, "
            "V:list_price_cents::NUMBER list_price_cents, V:lead_band::VARCHAR lead_band, V:cost_cents::NUMBER cost_cents, V:vendor_id::VARCHAR vendor_id, V:safety_stock::NUMBER safety_stock",
            ["sku_id", "name", "family", "designer", "finish", "list_price_cents", "lead_band", "cost_cents", "vendor_id", "safety_stock"],
        ),
        "vendor_kpi": (
            "BRONZE.VENDOR_KPI", "VENDOR_ID",
            "V:vendor_id::VARCHAR vendor_id, V:otif_pct::FLOAT otif_pct, V:defect_pct::FLOAT defect_pct, V:avg_lead_days::FLOAT avg_lead_days, V:promised_lead_days::FLOAT promised_lead_days, V:shipments::NUMBER shipments",
            ["vendor_id", "otif_pct", "defect_pct", "avg_lead_days", "promised_lead_days", "shipments"],
        ),
    }
    c.cursor().execute("USE DATABASE VC_RETAIL_DEMO")
    c.cursor().execute(f"USE WAREHOUSE {SERVE_WH}")
    with tempfile.TemporaryDirectory() as d:
        for name, records in data.items():
            f = Path(d) / (name + ".jsonl")
            f.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
            c.cursor().execute("PUT '" + f.as_uri() + "' @BRONZE.INGEST_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
            c.cursor().execute("TRUNCATE TABLE BRONZE.INCOMING")
            c.cursor().execute(f"COPY INTO BRONZE.INCOMING FROM @BRONZE.INGEST_STAGE/{name}.jsonl.gz FILE_FORMAT=(TYPE=JSON) FORCE=TRUE")
            if name in merges:
                table, key, proj, cols = merges[name]
                sets = ", ".join(f"{col}=s.{col}" for col in cols if col.lower() != key.lower())
                c.cursor().execute(
                    f"MERGE INTO {table} t USING (SELECT {proj} FROM BRONZE.INCOMING) s ON t.{key}=s.{key} "
                    f"WHEN MATCHED THEN UPDATE SET {sets} "
                    f"WHEN NOT MATCHED THEN INSERT ({', '.join(cols)}) VALUES ({', '.join('s.' + col for col in cols)})"
                )
            elif name == "monthly":
                c.cursor().execute("DELETE FROM BRONZE.MONTHLY_FACTS WHERE DEALER_ID IN (SELECT V:dealer_id::VARCHAR FROM BRONZE.INCOMING)")
                c.cursor().execute(
                    "INSERT INTO BRONZE.MONTHLY_FACTS SELECT V:dealer_id::VARCHAR, V:sku_id::VARCHAR, V:month::VARCHAR, V:units_sold::NUMBER, "
                    "V:net_sales_cents::NUMBER, V:margin_cents::NUMBER, V:family::VARCHAR, V:channel::VARCHAR, V:region::VARCHAR, V:rep_id::VARCHAR FROM BRONZE.INCOMING"
                )
            else:  # events: identity/version conflict guard then MERGE
                conflicts = c.cursor().execute(
                    """
                    SELECT COUNT(*) FROM BRONZE.INCOMING i
                    JOIN BRONZE.EVENTS e ON e.EVENT_ID=i.V:event_id::VARCHAR
                      OR (e.DEALER_ID=i.V:dealer_id::VARCHAR AND e.SOURCE_ID=i.V:source_id::VARCHAR AND e.VERSION=i.V:version::NUMBER)
                    WHERE e.EVENT_ID<>i.V:event_id::VARCHAR OR e.DEALER_ID<>i.V:dealer_id::VARCHAR
                       OR e.SOURCE_ID<>i.V:source_id::VARCHAR OR e.VERSION<>i.V:version::NUMBER
                       OR e.OP<>i.V:op::VARCHAR OR e.PAYLOAD<>i.V:payload
                    """
                ).fetchone()[0]
                if conflicts:
                    raise RuntimeError("Conflicting event identity/version. Resolve before loading.")
                c.cursor().execute(
                    """
                    MERGE INTO BRONZE.EVENTS t USING(
                      SELECT V:event_id::VARCHAR event_id, V:dealer_id::VARCHAR dealer_id, V:source_id::VARCHAR source_id,
                             V:version::NUMBER version, V:op::VARCHAR op, V:payload payload, V:received_at::TIMESTAMP_TZ received_at
                      FROM BRONZE.INCOMING
                    ) s ON t.EVENT_ID=s.EVENT_ID
                    WHEN NOT MATCHED THEN INSERT VALUES(s.event_id,s.dealer_id,s.source_id,s.version,s.op,s.payload,s.received_at)
                    """
                )
    print(f"Loaded {len(data['events'])} events, {len(data['dealers'])} dealers, {len(data['products'])} products, "
          f"{len(data['salespeople'])} reps, {len(data['vendors'])} vendors, {len(data['monthly'])} monthly rows.")


def _reconcile(c, out: Path | None):
    c.cursor().execute("USE DATABASE VC_RETAIL_DEMO")
    c.cursor().execute(f"USE WAREHOUSE {SERVE_WH}")
    q = """
        SELECT (SELECT COUNT(*) FROM SILVER.FACTS) AS silver_facts,
               (SELECT SUM(UNITS_SOLD) FROM SILVER.FACTS) AS units,
               (SELECT SUM(NET_SALES_CENTS)/100.0 FROM SILVER.FACTS) AS net_sales,
               (SELECT COUNT(*) FROM BRONZE.DEALERS) AS dealers,
               (SELECT COUNT(*) FROM SILVER.QUARANTINE) AS quarantined,
               (SELECT COUNT(*) FROM BRONZE.PURCHASE_ORDERS) AS purchase_orders,
               (SELECT COUNT(*) FROM BRONZE.INVENTORY_SNAPSHOTS) AS inventory_snapshots,
               (SELECT COUNT(*) FROM BRONZE.MRP_PLAN) AS mrp_plan
    """
    keys = ["silver_facts", "units", "net_sales", "dealers", "quarantined", "purchase_orders", "inventory_snapshots", "mrp_plan"]
    sf = dict(zip(keys, c.cursor().execute(q).fetchone()))
    # Event-sourced subset (the 50 synthetic dealers' SKU-xxxx facts) is the apples-to-apples comparison with local.
    ev = c.cursor().execute(
        "SELECT COUNT(*), SUM(UNITS_SOLD), SUM(NET_SALES_CENTS)/100.0 FROM SILVER.FACTS WHERE LENGTH(SKU_ID) = 8"
    ).fetchone()
    local = connect(DB)
    try:
        loc = dict(zip(keys[:5], local.execute(
            "SELECT (SELECT COUNT(*) FROM silver_facts), (SELECT SUM(units_sold) FROM silver_facts), "
            "(SELECT SUM(net_sales_cents)/100.0 FROM silver_facts), (SELECT COUNT(*) FROM dealers), (SELECT COUNT(*) FROM quarantine)"
        ).fetchone()))
        loc.update({k: local.execute(f"SELECT COUNT(*) FROM {k}").fetchone()[0] for k in ("purchase_orders", "inventory_snapshots", "mrp_plan")})
    finally:
        local.close()
    norm = lambda d: {k: (float(v) if v is not None else None) for k, v in d.items()}
    evidence = {
        "synthetic": True,
        "as_of": AS_OF,
        "snowflake": norm(sf),
        "snowflake_event_subset": {"silver_facts": float(ev[0] or 0), "units": float(ev[1] or 0), "net_sales": float(ev[2] or 0)},
        "local": norm(loc),
        "event_subset_vs_local_facts": float(ev[0] or 0) - loc["silver_facts"],
        "event_subset_vs_local_sales": round(float(ev[2] or 0) - float(loc["net_sales"]), 2),
        "note": "Snowflake totals include the TPC-DS backbone (scoped dealers x SKU) and the generated layer; the event subset should match local exactly.",
    }
    out = out or (ROOT / "docs" / "evidence" / "reconcile.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(json.dumps(evidence, indent=2, default=str))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["doctor", "platform", "load", "transform", "backbone", "generate", "build", "governance", "semantic", "validate", "reconcile", "all"])
    p.add_argument("--connection", default="aq")
    p.add_argument("--out", type=Path)
    p.add_argument("--scale", type=float, default=1.0, help="Generated-layer scale (1.0 = 2M POs, 50K components). Backbone is always the full 10 TB share.")
    p.add_argument("--demo-dealers", type=int, default=50, help="Dealers kept at dealer x SKU grain in SILVER.FACTS")
    p.add_argument("--sample-mod", type=int, default=200, help="Keep 1 in N TPC-DS tickets/orders (volume re-skin: retailer -> lighting dealer). 1 = keep all.")
    p.add_argument("--build-timeout", type=int, default=5400)
    p.add_argument("--confirm-cost", action="store_true", help="Required for backbone/generate/build (LARGE warehouse credits)")
    a = p.parse_args()

    import snowflake.connector

    variables = _template_vars(a)
    heavy = {"backbone": "06_backbone.sql", "generate": "07_generate_layer.sql", "build": "08_silver_gold.sql"}
    light = {"platform": "01_platform.sql", "transform": "02_transform.sql", "governance": "03_governance.sql", "semantic": "04_semantic.sql", "validate": "05_validation.sql"}

    steps = [a.action] if a.action != "all" else ["platform", "load", "transform", "backbone", "generate", "build", "governance", "semantic", "validate", "reconcile"]
    if any(s in heavy for s in steps) and not a.confirm_cost:
        for s in steps:
            if s in heavy:
                print(f"{s}: {COST_HINTS[s]}")
        raise SystemExit("Heavy steps run on AQ_VC_BUILD_WH (LARGE). Re-run with --confirm-cost to proceed.")

    with snowflake.connector.connect(
        connection_name=a.connection,
        session_parameters={"QUERY_TAG": "aq-vc-retail-demo", "STATEMENT_TIMEOUT_IN_SECONDS": a.build_timeout},
    ) as c:
        for step in steps:
            if step == "doctor":
                r = c.cursor().execute("SELECT CURRENT_ACCOUNT(),CURRENT_USER(),CURRENT_ROLE(),CURRENT_WAREHOUSE(),CURRENT_REGION()").fetchone()
                print(dict(zip(["account", "user", "role", "warehouse", "region"], r)))
                share = c.cursor().execute(
                    "SELECT COUNT(*) FROM SNOWFLAKE_SAMPLE_DATA.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='TPCDS_SF10TCL'"
                ).fetchone()[0]
                print({"tpcds_sf10tcl_tables": share, "ok": share >= 20})
                continue
            if step == "load":
                _load(c)
                continue
            if step == "reconcile":
                _reconcile(c, a.out)
                continue
            if step in heavy:
                print(f"-- {step}: {COST_HINTS[step]}")
                started = time.perf_counter()
                try:
                    _run_sql_file(c, SQL_DIR / heavy[step], variables, echo_rows=True)
                finally:
                    _suspend_build_wh(c)
                print(f"{step} completed in {(time.perf_counter() - started) / 60:.1f} min.")
                continue
            tolerate = ("already", "does not exist or not authorized") if step == "governance" else ()
            _run_sql_file(c, SQL_DIR / light[step], variables, echo_rows=(step == "validate"), tolerate=tolerate)
            print(f"{step} completed.")


if __name__ == "__main__":
    main()
