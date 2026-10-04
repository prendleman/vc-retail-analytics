"""Local + Snowflake dual-backend HTTP app for VC Retail Analytics."""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app import demo_auth
from app.core import (
    DB,
    FAQ,
    METRICS,
    ROOT,
    connect,
    interpret_metric,
    match_faq,
    metric_sql,
    now,
    product_lookup,
    seed,
)

STATIC = ROOT / "app" / "static"
ALLOWED_STATIC = {
    "/": "marketing.html",
    "/app": "index.html",
    "/login": "login.html",
    "/app.js": "app.js",
    "/style.css": "style.css",
    "/vc-hero.jpg": "vc-hero.jpg",
    "/vc-still.jpg": "vc-still.jpg",
}
CTYPES = {
    "html": "text/html; charset=utf-8",
    "css": "text/css",
    "js": "text/javascript",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}


BACKEND_COOKIE = "vc_backend"
DATA_SCALE = {
    "local": "SQLite: small synthetic seed (same schema as Snowflake SERVING)",
    "snowflake": "Snowflake: 10 TB TPC-DS backbone (shared, 56.9B rows) re-skinned to public Visual Comfort scale (~$750M/yr, 1,500 accounts, 31K SKUs, 4 DCs) + generated sales-org / procurement / inventory / MRP layer",
}


def snowflake_env_config():
    """Hosted deployments pass the reader credential as environment (Fly secrets) instead of connections.toml.
    Returns None when the env is not set, so local runs fall back to a named connection profile."""
    env = os.environ
    if not (env.get("SNOWFLAKE_ACCOUNT") and env.get("SNOWFLAKE_USER") and env.get("SNOWFLAKE_PAT")):
        return None
    return {
        "account": env["SNOWFLAKE_ACCOUNT"],
        "user": env["SNOWFLAKE_USER"],
        "authenticator": "PROGRAMMATIC_ACCESS_TOKEN",
        "token": env["SNOWFLAKE_PAT"],
        "role": env.get("SNOWFLAKE_ROLE", "AQ_VC_READER"),
        "warehouse": env.get("SNOWFLAKE_WAREHOUSE", "AQ_VC_RETAIL_WH"),
        "database": "VC_RETAIL_DEMO",
        "schema": "SERVING",
    }


class Store:
    """Local SQLite by default; Snowflake backend keeps one authenticated connection (opened lazily on first use)
    and serves heavy metrics from Gold-backed SERVING views via the 'snowflake' SQL dialect."""

    def __init__(self, path, backend="local", connection="aq_vc_reader"):
        self.path = path
        self.backend = backend
        self.connection = connection
        self.dialect = "snowflake" if backend == "snowflake" else "sqlite"
        self._sf = None
        self._lock = threading.Lock()

    def _snowflake(self):
        import snowflake.connector

        with self._lock:
            if self._sf is None or self._sf.is_closed():
                kwargs = snowflake_env_config() or {"connection_name": self.connection}
                self._sf = snowflake.connector.connect(
                    session_parameters={"QUERY_TAG": "vc-retail-demo-app", "STATEMENT_TIMEOUT_IN_SECONDS": 60},
                    client_session_keep_alive=True,
                    login_timeout=20,
                    network_timeout=60,
                    **kwargs,
                )
                self._sf.cursor().execute("USE DATABASE VC_RETAIL_DEMO")
                self._sf.cursor().execute("USE SCHEMA SERVING")
            return self._sf

    def rows(self, sql, params=()):
        if self.backend == "local":
            c = connect(self.path)
            try:
                return [dict(r) for r in c.execute(sql, params)]
            finally:
                c.close()
        c = self._snowflake()
        try:
            cur = c.cursor().execute(sql.replace("?", "%s"), list(params))
        except Exception:
            # One reconnect on a dropped session, then surface the error.
            with self._lock:
                self._sf = None
            cur = self._snowflake().cursor().execute(sql.replace("?", "%s"), list(params))
        columns = [d[0].lower() for d in cur.description]
        return [dict(zip(columns, r)) for r in cur.fetchall()]

    def metric_rows(self, name, dealer):
        return self.rows(*metric_sql(name, dealer, self.dialect))

    def many(self, names, dealer):
        """Run several governed metrics; fan out on Snowflake (network-bound), sequential on SQLite."""
        if self.backend == "local":
            return {n: self.metric_rows(n, dealer) for n in names}
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {n: pool.submit(self.metric_rows, n, dealer) for n in names}
            return {n: f.result() for n, f in futures.items()}

    def audit(self, dealer, metric, n):
        c = connect(self.path)
        c.execute(
            "INSERT INTO audit(at,dealer_id,metric,rows_returned) VALUES(?,?,?,?)",
            (now(), dealer or "*", metric, n),
        )
        c.commit()
        c.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)

    def send(self, data, status=200, content_type="application/json", extra_headers=None):
        raw = json.dumps(data, default=str).encode() if content_type == "application/json" else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def session(self):
        return demo_auth.parse_cookie(self.headers.get("Cookie"))

    # ---- backend selection (per browser session; a preference cookie, not a security boundary) ----
    def backend_pref(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == BACKEND_COOKIE and v in ("local", "snowflake"):
                return v
        return None

    def store(self):
        stores = getattr(self.server, "stores", None) or {}
        pref = self.backend_pref()
        if pref and stores.get(pref):
            return stores[pref]
        return self.server.store

    def backends_available(self):
        stores = getattr(self.server, "stores", None) or {}
        return [b for b in ("local", "snowflake") if stores.get(b)] or [self.server.store.backend]

    def same_origin_ok(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host", "")
        return origin in (f"http://{host}", f"https://{host}")

    def scope(self, query):
        requested = query.get("dealer", [""])[0] or None
        sess = self.session()
        if sess and sess.get("dealer"):
            if requested and requested != sess["dealer"]:
                raise PermissionError("Dealer access denied")
            dealer = sess["dealer"]
        elif self.server.dealer:
            if requested and requested != self.server.dealer:
                raise PermissionError("Dealer access denied")
            dealer = self.server.dealer
        else:
            dealer = requested
        if dealer and not self.store().rows("SELECT dealer_id FROM dealers WHERE dealer_id=?", [dealer]):
            raise ValueError("Unknown or inaccessible dealer")
        return dealer

    def do_GET(self):
        try:
            u = urlparse(self.path)
            q = parse_qs(u.query)
            s = self.store()
            if u.path.startswith("/api/"):
                if u.path == "/api/session":
                    sess = self.session()
                    return self.send(
                        {
                            "authenticated": bool(sess),
                            "session": sess,
                            "accounts": demo_auth.public_accounts(),
                            "password_hint": demo_auth.DEMO_PASSWORD,
                        }
                    )
                if u.path == "/api/health":
                    sess = self.session()
                    scope = (sess.get("dealer") if sess and sess.get("dealer") else None) or self.server.dealer or "all dealers"
                    return self.send(
                        {
                            "ok": True,
                            "backend": s.backend,
                            "backends_available": self.backends_available(),
                            "scope": scope,
                            "synthetic": True,
                            "label": "VC Retail Analytics — synthetic demo",
                            "data_scale": DATA_SCALE[s.backend],
                        }
                    )
                dealer = self.scope(q)
                where = " WHERE dealer_id=?" if dealer else ""
                params = [dealer] if dealer else []
                if u.path == "/api/catalog":
                    return self.send(
                        {
                            "metrics": {k: v["description"] for k, v in METRICS.items()},
                            "faq_ids": [f["id"] for f in FAQ],
                            "lineage": [
                                "synthetic dealer + catalog (Snowflake: TPC-DS 10 TB backbone re-skinned)",
                                "bronze events / backbone sales + inventory",
                                "validated silver_facts + monthly",
                                "sales org · procurement · inventory · MRP (generated layer)",
                                "gold aggregates",
                                "dashboard / governed tools",
                            ],
                            "grain": "One current fact per (dealer_id, sku_id); PO lines, weekly DC snapshots, monthly forecast, latest MRP run",
                            "amounts": "USD cents in Silver; dollars in Gold/API",
                            "domains": {
                                "sales_org": ["salespeople", "territories", "rep_assignments", "rep_quotas"],
                                "procurement": ["vendors", "vendor_contracts", "purchase_orders", "po_lines", "shipments", "receipts"],
                                "inventory": ["distribution_centers", "inventory_snapshots"],
                                "mrp": ["components", "bom", "demand_forecast", "mrp_plan", "work_orders"],
                            },
                        }
                    )
                if u.path == "/api/dealers":
                    return self.send(s.rows("SELECT * FROM dealers" + where + " ORDER BY dealer_id LIMIT 200", params))
                if u.path == "/api/products":
                    term = (q.get("q", [""])[0] or "").strip()
                    if s.backend == "local":
                        c = connect(s.path)
                        try:
                            rows = product_lookup(c, term) if term else [dict(r) for r in c.execute("SELECT * FROM products LIMIT 40")]
                        finally:
                            c.close()
                    else:
                        if term:
                            like = f"%{term.lower()}%"
                            rows = s.rows(
                                "SELECT * FROM products WHERE LOWER(name) LIKE ? OR LOWER(family) LIKE ? OR LOWER(designer) LIKE ? OR LOWER(finish) LIKE ? LIMIT 8",
                                [like, like, like, like],
                            )
                        else:
                            rows = s.rows("SELECT * FROM products LIMIT 40")
                    return self.send(rows)
                if u.path == "/api/summary":
                    row = s.rows(
                        "SELECT COUNT(*) AS skus, COALESCE(SUM(units_sold),0) AS units_sold, "
                        "COALESCE(SUM(net_sales_cents),0)/100.0 AS net_sales, "
                        "COALESCE(SUM(margin_cents),0)/100.0 AS margin, "
                        "COALESCE(SUM(on_hand),0) AS on_hand FROM silver_facts" + where,
                        params,
                    )[0]
                    row["dealers"] = s.rows("SELECT COUNT(*) AS n FROM dealers" + where, params)[0]["n"]
                    row["quarantined"] = s.rows("SELECT COUNT(*) AS n FROM quarantine" + where, params)[0]["n"]
                    return self.send(row)
                if u.path == "/api/metric":
                    name = q.get("name", ["portfolio"])[0]
                    sql, p = metric_sql(name, dealer, s.dialect)
                    start = time.perf_counter()
                    rows = s.rows(sql, p)
                    s.audit(dealer, name, len(rows))
                    return self.send(
                        {
                            "metric": name,
                            "description": METRICS[name]["description"],
                            "sql": sql,
                            "parameters": p,
                            "rows": rows,
                            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                        }
                    )
                if u.path == "/api/analytics":
                    start = time.perf_counter()
                    deep_keys = [
                        "by_channel",
                        "by_family",
                        "by_region",
                        "stock_risk",
                        "margin_pct",
                        "price_realization",
                        "low_margin_skus",
                        "margin_waterfall",
                        "reorder_candidates",
                        "days_of_cover",
                        "units_by_month",
                        "seasonal_index",
                        "yoy_family",
                        "lead_vs_peak",
                        "territory_perf",
                        "territory_coverage",
                        "whitespace",
                        "plan_vs_season",
                        "rep_leaderboard",
                        "rep_grade",
                        "vendor_otif",
                        "vendor_scorecard",
                        # sales org / procurement / inventory / MRP
                        "rep_attainment",
                        "rep_coverage",
                        "po_past_due",
                        "inbound_pipeline",
                        "vendor_otif_detail",
                        "vendor_defects",
                        "vendor_concentration",
                        "freight_cost",
                        "dc_inventory_health",
                        "inventory_trend",
                        "mrp_exceptions",
                        "mrp_shortages",
                        "forecast_accuracy",
                        "bom_cost_rollup",
                        "component_risk",
                        "work_order_status",
                    ]
                    payload = {
                        "synthetic": True,
                        "dealer_scope": dealer or "all",
                        "summary": s.rows(
                            "SELECT COUNT(*) AS skus, COALESCE(SUM(units_sold),0) AS units_sold, "
                            "COALESCE(SUM(net_sales_cents),0)/100.0 AS net_sales, "
                            "COALESCE(SUM(margin_cents),0)/100.0 AS margin, "
                            "ROUND(100.0 * COALESCE(SUM(margin_cents),0) / NULLIF(SUM(net_sales_cents),0), 1) AS margin_pct "
                            "FROM silver_facts" + where,
                            params,
                        )[0],
                        "elapsed_ms": 0,
                    }
                    payload.update(s.many(deep_keys, dealer))
                    payload["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 2)
                    s.audit(dealer, "analytics", len(payload["by_channel"]))
                    return self.send(payload)
                if u.path == "/api/faq":
                    return self.send({"items": FAQ, "note": "Synthetic policy copy inspired by public FAQ language"})
                if u.path == "/api/quality":
                    return self.send(s.rows("SELECT * FROM quarantine" + where + " ORDER BY event_id LIMIT 50", params))
                if u.path == "/api/audit":
                    c = connect(s.path)
                    rows = [dict(r) for r in c.execute("SELECT * FROM audit" + where.replace("dealer_id", "dealer_id") + " ORDER BY id DESC LIMIT 30", params)]
                    c.close()
                    return self.send(rows)
                return self.send({"error": "Not found"}, 404)

            if u.path == "/app" and not self.session() and not self.server.dealer:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            if u.path not in ALLOWED_STATIC:
                return self.send({"error": "Not found"}, 404)
            file = STATIC / Path(ALLOWED_STATIC[u.path])
            self.send(file.read_bytes(), content_type=CTYPES[file.suffix[1:]])
        except PermissionError as e:
            self.send({"error": str(e)}, 403)
        except ValueError as e:
            self.send({"error": str(e)}, 400)
        except Exception as e:
            print(type(e).__name__, str(e))
            self.send({"error": "Request failed. Check server log."}, 500)

    def do_POST(self):
        try:
            if not self.same_origin_ok():
                raise PermissionError("Cross-origin request rejected")
            if "application/json" not in self.headers.get("Content-Type", ""):
                raise ValueError("JSON required")
            size = int(self.headers.get("Content-Length", "0"))
            if size > 8192:
                raise ValueError("Request too large")
            body = json.loads(self.rfile.read(size) or b"{}")
            s = self.store()
            path = urlparse(self.path).path
            if path == "/api/login":
                sess = demo_auth.authenticate(body.get("username"), body.get("password"))
                if not sess:
                    raise PermissionError("Invalid demo credentials")
                return self.send({"ok": True, "session": sess}, extra_headers={"Set-Cookie": demo_auth.issue_cookie(sess)})
            if path == "/api/logout":
                return self.send({"ok": True}, extra_headers={"Set-Cookie": demo_auth.clear_cookie()})
            if path == "/api/backend":
                if not self.session() and not self.server.dealer:
                    raise PermissionError("Login required")
                want = (body.get("backend") or "").lower()
                if want not in self.backends_available():
                    return self.send({"error": f"Backend '{want}' is not available on this host", "backends_available": self.backends_available()}, 409)
                target = (getattr(self.server, "stores", None) or {}).get(want) or self.server.store
                try:
                    # Prove the backend answers before switching the session (Snowflake warehouse may need to resume).
                    start = time.perf_counter()
                    target.rows("SELECT dealer_id FROM dealers LIMIT 1")
                    warm_ms = round((time.perf_counter() - start) * 1000, 1)
                except Exception as e:  # noqa: BLE001 - surfaced to the UI, logged server-side
                    print("backend switch failed:", type(e).__name__, str(e)[:200], flush=True)
                    return self.send({"error": f"{want} backend did not respond; staying on {s.backend}", "backend": s.backend}, 503)
                cookie = f"{BACKEND_COOKIE}={want}; Path=/; Max-Age=43200; SameSite=Lax; HttpOnly"
                return self.send(
                    {"ok": True, "backend": want, "data_scale": DATA_SCALE[want], "warm_ms": warm_ms},
                    extra_headers={"Set-Cookie": cookie},
                )

            dealer = self.scope({"dealer": [body.get("dealer", "")]})
            if path == "/api/ask":
                question = (body.get("question") or "").strip()
                mode = (body.get("mode") or "proposed").lower()
                if mode == "today":
                    # Reconstruct current-site pattern: FAQ snippet or escalate stub.
                    faq = match_faq(question)
                    if faq:
                        return self.send(
                            {
                                "mode": "today_site_pattern",
                                "kind": "faq",
                                "answer": faq["a"],
                                "source": faq["id"],
                                "trace": ["observe_public_faq_language", "return_static_policy_snippet"],
                                "improvement_gap": "No warehouse grounding, no tool SQL, no structured retail analytics.",
                            }
                        )
                    return self.send(
                        {
                            "mode": "today_site_pattern",
                            "kind": "escalate",
                            "answer": (
                                "I can help with common FAQ topics. For order status, returns, or account-specific "
                                "questions, please use the contact form, call Consumer|Trade 877.762.2323, or email "
                                "customerservice@visualcomfort.com (public lanes — observation only)."
                            ),
                            "trace": ["no_faq_match", "escalate_to_human_form_or_phone"],
                            "improvement_gap": "Dead-end to form/phone; no governed inventory/margin/sell-through answers.",
                        }
                    )

                # Proposed: FAQ + catalog + verified metrics
                faq = match_faq(question)
                if faq and not any(
                    k in question.lower()
                    for k in (
                        "sales",
                        "margin",
                        "stock",
                        "portfolio",
                        "channel",
                        "family",
                        "region",
                        "quality",
                        "reorder",
                        "season",
                        "territory",
                        "whitespace",
                        "rep",
                        "vendor",
                        "realization",
                        "cover",
                    )
                ):
                    return self.send(
                        {
                            "mode": "offline governed assistant (not LLM)",
                            "kind": "faq",
                            "answer": faq["a"],
                            "source": faq["id"],
                            "trace": ["match_faq", "return_grounded_policy", "no_fabricated_order_status"],
                        }
                    )
                if any(k in question.lower() for k in ("sku", "alabaster", "chandelier", "sconce", "fan", "cordless", "finish", "designer")):
                    c = connect(s.path)
                    try:
                        hits = product_lookup(c, question, limit=5)
                    finally:
                        c.close()
                    if hits:
                        return self.send(
                            {
                                "mode": "offline governed assistant (not LLM)",
                                "kind": "catalog",
                                "answer": f"Found {len(hits)} synthetic catalog matches.",
                                "rows": hits,
                                "trace": ["catalog_lookup", "return_attributes_only"],
                            }
                        )
                try:
                    name = interpret_metric(question)
                except ValueError as err:
                    return self.send(
                        {
                            "mode": "offline governed assistant (not LLM)",
                            "kind": "clarify",
                            "answer": str(err),
                            "trace": ["resolve_verified_question", "refuse_unguarded_generation"],
                        },
                        400,
                    )
                sql, p = metric_sql(name, dealer, s.dialect)
                rows = s.rows(sql, p)
                s.audit(dealer, name, len(rows))
                return self.send(
                    {
                        "mode": "offline governed assistant (not LLM)",
                        "kind": "metric",
                        "metric": name,
                        "description": METRICS[name]["description"],
                        "sql": sql,
                        "parameters": p,
                        "rows": rows,
                        "trace": [
                            "discover_catalog",
                            "resolve_verified_question",
                            "compile_scoped_metric",
                            "execute_read_only_metric",
                            "audit_result",
                        ],
                    }
                )
            if path == "/api/escalate":
                packet = {
                    "at": now(),
                    "dealer_scope": dealer or "all",
                    "lane": body.get("lane") or "Consumer|Trade",
                    "question": body.get("question") or "",
                    "reason": body.get("reason") or "needs_human",
                    "context_metrics": body.get("context") or {},
                }
                return self.send(
                    {
                        "ok": True,
                        "escalation": packet,
                        "note": "Structured handoff packet for a human agent — demo only, not sent externally.",
                    }
                )
            self.send({"error": "Not found"}, 404)
        except PermissionError as e:
            self.send({"error": str(e)}, 403)
        except (ValueError, KeyError) as e:
            self.send({"error": str(e)}, 400)
        except Exception as e:
            print(type(e).__name__, str(e))
            self.send({"error": "Request failed. Check server log."}, 500)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=int(__import__("os").environ.get("PORT", "8770")))
    p.add_argument("--host", default=__import__("os").environ.get("HOST", "127.0.0.1"))
    p.add_argument("--dealer")
    p.add_argument("--db", type=Path, default=DB)
    p.add_argument("--backend", choices=["local", "snowflake"], default="local", help="Default backend for new sessions")
    p.add_argument("--connection", default="aq_vc_reader", help="connections.toml profile for Snowflake (ignored when SNOWFLAKE_* env is set)")
    p.add_argument(
        "--enable-snowflake",
        action="store_true",
        help="Offer Snowflake as a per-session toggle alongside SQLite (implied by --backend snowflake or SNOWFLAKE_PAT in env)",
    )
    a = p.parse_args()
    if not a.db.exists():
        print("Seeding synthetic VC retail dealers + catalog...", flush=True)
        print(seed(a.db), flush=True)
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    server.dealer = a.dealer
    snowflake_on = a.enable_snowflake or a.backend == "snowflake" or snowflake_env_config() is not None
    server.stores = {"local": Store(a.db, "local", a.connection)}
    if snowflake_on:
        server.stores["snowflake"] = Store(a.db, "snowflake", a.connection)
    server.store = server.stores[a.backend] if a.backend in server.stores else server.stores["local"]
    print(
        f"VC Retail Analytics | http://{a.host}:{a.port} | default={server.store.backend} "
        f"available={sorted(server.stores)} | " + (a.dealer or "session/operator"),
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
