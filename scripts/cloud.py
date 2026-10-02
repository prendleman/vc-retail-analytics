"""Explicit AQ Snowflake setup, staged ingestion, and validation. No embedded credentials."""
from __future__ import annotations

import argparse
import io
import json
import tempfile
from pathlib import Path

from app.core import DB, ROOT, connect


def _run_sql_file(c, path: Path, echo_rows: bool = False):
    sql = path.read_text(encoding="utf-8")
    chunks = []
    for part in sql.split(";"):
        body = "\n".join(ln for ln in part.splitlines() if ln.strip() and not ln.strip().startswith("--"))
        if body.strip():
            chunks.append(body.strip() + ";")
    for cursor in c.execute_stream(io.StringIO("\n".join(chunks))):
        rows = cursor.fetchall()
        if echo_rows and cursor.description:
            print(cursor.description, rows[:10])


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "action",
        choices=["doctor", "platform", "load", "transform", "governance", "semantic", "validate", "reconcile"],
    )
    p.add_argument("--connection", default="aq")
    p.add_argument("--out", type=Path)
    a = p.parse_args()

    import snowflake.connector

    with snowflake.connector.connect(
        connection_name=a.connection,
        session_parameters={"QUERY_TAG": "aq-vc-retail-demo", "STATEMENT_TIMEOUT_IN_SECONDS": 60},
    ) as c:
        if a.action == "doctor":
            r = c.cursor().execute(
                "SELECT CURRENT_ACCOUNT(),CURRENT_USER(),CURRENT_ROLE(),CURRENT_WAREHOUSE()"
            ).fetchone()
            print(dict(zip(["account", "user", "role", "warehouse"], r)))
            return

        if a.action == "reconcile":
            c.cursor().execute("USE DATABASE VC_RETAIL_DEMO")
            c.cursor().execute("USE WAREHOUSE AQ_VC_RETAIL_WH")
            sf = c.cursor().execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM SILVER.FACTS) AS silver_facts,
                  (SELECT SUM(UNITS_SOLD) FROM SILVER.FACTS) AS units,
                  (SELECT SUM(NET_SALES_CENTS)/100.0 FROM SILVER.FACTS) AS net_sales,
                  (SELECT COUNT(*) FROM BRONZE.DEALERS) AS dealers,
                  (SELECT COUNT(*) FROM SILVER.QUARANTINE) AS quarantined
                """
            ).fetchone()
            local = connect(DB)
            try:
                loc = local.execute(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM silver_facts) AS silver_facts,
                      (SELECT SUM(units_sold) FROM silver_facts) AS units,
                      (SELECT SUM(net_sales_cents)/100.0 FROM silver_facts) AS net_sales,
                      (SELECT COUNT(*) FROM dealers) AS dealers,
                      (SELECT COUNT(*) FROM quarantine) AS quarantined
                    """
                ).fetchone()
            finally:
                local.close()
            keys = ["silver_facts", "units", "net_sales", "dealers", "quarantined"]
            sf_d = {k: (float(v) if k == "net_sales" and v is not None else (int(v) if v is not None else None)) for k, v in zip(keys, sf)}
            loc_d = {k: (float(v) if k == "net_sales" and v is not None else (int(v) if v is not None else None)) for k, v in zip(keys, loc)}
            evidence = {
                "synthetic": True,
                "snowflake": sf_d,
                "local": loc_d,
                "local_vs_cloud_facts": loc_d["silver_facts"] - sf_d["silver_facts"],
                "local_vs_cloud_sales": loc_d["net_sales"] - sf_d["net_sales"],
            }
            out = a.out or (ROOT / "docs" / "evidence" / "reconcile.json")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
            print(json.dumps(evidence, indent=2, default=str))
            return

        scripts = {
            "platform": "01_platform.sql",
            "transform": "02_transform.sql",
            "governance": "03_governance.sql",
            "semantic": "04_semantic.sql",
            "validate": "05_validation.sql",
        }
        if a.action in scripts:
            _run_sql_file(c, ROOT / "sql" / "snowflake" / scripts[a.action], echo_rows=(a.action == "validate"))
            print(a.action + " completed. See docs/SNOWFLAKE.md for next gate.")
            return

        # load
        local = connect(DB)
        try:
            dealers = [dict(r) for r in local.execute("SELECT * FROM dealers")]
            products = [dict(r) for r in local.execute("SELECT * FROM products")]
            events = [dict(r) for r in local.execute("SELECT * FROM bronze")]
        finally:
            local.close()
        for e in events:
            e["payload"] = json.loads(e["payload"])
        c.cursor().execute("USE DATABASE VC_RETAIL_DEMO")
        c.cursor().execute("USE WAREHOUSE AQ_VC_RETAIL_WH")
        with tempfile.TemporaryDirectory() as d:
            for name, records in [("dealers", dealers), ("products", products), ("events", events)]:
                f = Path(d) / (name + ".jsonl")
                f.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
                c.cursor().execute("PUT '" + f.as_uri() + "' @BRONZE.INGEST_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
                c.cursor().execute("TRUNCATE TABLE BRONZE.INCOMING")
                c.cursor().execute(
                    f"COPY INTO BRONZE.INCOMING FROM @BRONZE.INGEST_STAGE/{name}.jsonl.gz FILE_FORMAT=(TYPE=JSON) FORCE=TRUE"
                )
                if name == "dealers":
                    c.cursor().execute(
                        """
                        MERGE INTO BRONZE.DEALERS t USING(
                          SELECT V:dealer_id::VARCHAR dealer_id, V:name::VARCHAR name, V:region::VARCHAR region,
                                 V:channel_focus::VARCHAR channel_focus, V:city::VARCHAR city
                          FROM BRONZE.INCOMING
                        ) s ON t.dealer_id=s.dealer_id
                        WHEN MATCHED THEN UPDATE SET name=s.name, region=s.region, channel_focus=s.channel_focus, city=s.city
                        WHEN NOT MATCHED THEN INSERT VALUES(s.dealer_id,s.name,s.region,s.channel_focus,s.city)
                        """
                    )
                elif name == "products":
                    c.cursor().execute(
                        """
                        MERGE INTO BRONZE.PRODUCTS t USING(
                          SELECT V:sku_id::VARCHAR sku_id, V:name::VARCHAR name, V:family::VARCHAR family,
                                 V:designer::VARCHAR designer, V:finish::VARCHAR finish,
                                 V:list_price_cents::NUMBER list_price_cents, V:lead_band::VARCHAR lead_band
                          FROM BRONZE.INCOMING
                        ) s ON t.sku_id=s.sku_id
                        WHEN MATCHED THEN UPDATE SET name=s.name, family=s.family, designer=s.designer,
                          finish=s.finish, list_price_cents=s.list_price_cents, lead_band=s.lead_band
                        WHEN NOT MATCHED THEN INSERT VALUES(s.sku_id,s.name,s.family,s.designer,s.finish,s.list_price_cents,s.lead_band)
                        """
                    )
                else:
                    conflicts = c.cursor().execute(
                        """
                        SELECT COUNT(*) FROM BRONZE.INCOMING i
                        JOIN BRONZE.EVENTS e ON e.EVENT_ID=i.V:event_id::VARCHAR
                          OR (e.DEALER_ID=i.V:dealer_id::VARCHAR AND e.SOURCE_ID=i.V:source_id::VARCHAR AND e.VERSION=i.V:version::NUMBER)
                        WHERE e.EVENT_ID<>i.V:event_id::VARCHAR
                           OR e.DEALER_ID<>i.V:dealer_id::VARCHAR
                           OR e.SOURCE_ID<>i.V:source_id::VARCHAR
                           OR e.VERSION<>i.V:version::NUMBER
                           OR e.OP<>i.V:op::VARCHAR
                           OR e.PAYLOAD<>i.V:payload
                        """
                    ).fetchone()[0]
                    if conflicts:
                        raise RuntimeError("Conflicting event identity/version. Resolve before loading.")
                    c.cursor().execute(
                        """
                        MERGE INTO BRONZE.EVENTS t USING(
                          SELECT V:event_id::VARCHAR event_id, V:dealer_id::VARCHAR dealer_id,
                                 V:source_id::VARCHAR source_id, V:version::NUMBER version,
                                 V:op::VARCHAR op, V:payload payload, V:received_at::TIMESTAMP_TZ received_at
                          FROM BRONZE.INCOMING
                        ) s ON t.EVENT_ID=s.EVENT_ID
                        WHEN NOT MATCHED THEN INSERT VALUES(s.event_id,s.dealer_id,s.source_id,s.version,s.op,s.payload,s.received_at)
                        """
                    )
        print(f"Loaded {len(events)} events for {len(dealers)} dealers / {len(products)} products.")


if __name__ == "__main__":
    main()
