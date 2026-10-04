"""Local + Snowflake dual-backend HTTP app for VC Retail Analytics."""
from __future__ import annotations

import argparse
import json
import re
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app import demo_auth
from app import voice as voice_mod
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
    resolve_metric,
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
    "mp3": "audio/mpeg",
    "json": "application/json",
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

    def prefer_snowflake_store(self):
        """Voice analytics prefers the Snowflake scale when the backend is warm."""
        stores = getattr(self.server, "stores", None) or {}
        sf = stores.get("snowflake")
        if not sf:
            return self.store()
        try:
            sf.rows("SELECT dealer_id FROM dealers LIMIT 1")
            return sf
        except Exception as e:  # noqa: BLE001
            print("voice snowflake warm failed:", type(e).__name__, str(e)[:160], flush=True)
            return self.store()

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
                            "voice": voice_mod.configured(),
                            "cortex": voice_mod.cortex_configured(),
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
                        "SELECT COUNT(DISTINCT sku_id) AS skus, COALESCE(SUM(units_sold),0) AS units_sold, "
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
                            "SELECT COUNT(DISTINCT sku_id) AS skus, COALESCE(SUM(units_sold),0) AS units_sold, "
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
            if u.path.startswith("/audio/"):
                name = Path(u.path).name
                if not name or name != Path(u.path[1:]).name or ".." in u.path:
                    return self.send({"error": "Not found"}, 404)
                file = (STATIC / "audio" / name).resolve()
                if not str(file).startswith(str((STATIC / "audio").resolve())) or not file.is_file():
                    return self.send({"error": "Not found"}, 404)
                ext = file.suffix[1:]
                if ext not in CTYPES:
                    return self.send({"error": "Not found"}, 404)
                return self.send(file.read_bytes(), content_type=CTYPES[ext])
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
            path = urlparse(self.path).path
            ctype = self.headers.get("Content-Type", "")
            size = int(self.headers.get("Content-Length", "0"))

            if path == "/api/stt":
                if not self.session() and not self.server.dealer:
                    raise PermissionError("Login required")
                if not voice_mod.configured():
                    return self.send({"error": "Voice is not configured on this host"}, 503)
                if size <= 0 or size > 2_500_000:
                    raise ValueError("Audio payload missing or too large")
                raw = self.rfile.read(size)
                # Parse multipart: find file part after double CRLF following Content-Type header of the part
                filename, content_type, audio = "clip.webm", "audio/webm", raw
                if "multipart/form-data" in ctype:
                    m = re.search(rb'name="file";\s*filename="([^"]*)"[^\r\n]*\r\nContent-Type:\s*([^\r\n]+)\r\n\r\n', raw, re.I)
                    if not m:
                        m = re.search(rb'name="file";\s*filename="([^"]*)"[^\r\n]*\r\n\r\n', raw, re.I)
                        content_type = "application/octet-stream"
                        if m:
                            filename = m.group(1).decode("utf-8", "ignore") or filename
                            start = m.end()
                            end = raw.rfind(b"--")
                            audio = raw[start:end].rstrip(b"\r\n")
                    else:
                        filename = m.group(1).decode("utf-8", "ignore") or filename
                        content_type = m.group(2).decode("ascii", "ignore").strip() or content_type
                        start = m.end()
                        # trim trailing boundary
                        end = raw.find(b"\r\n--", start)
                        audio = raw[start:end if end > 0 else None]
                text = voice_mod.transcribe(audio, filename=filename, content_type=content_type)
                return self.send({"text": text, "ok": True})

            if "application/json" not in ctype:
                raise ValueError("JSON required")
            max_body = 32_000 if path in ("/api/tts", "/api/voice-ask", "/api/voice-brief") else 8192
            if size > max_body:
                raise ValueError("Request too large")
            body = json.loads(self.rfile.read(size) or b"{}")
            s = self.store()
            if path == "/api/tts":
                if not self.session() and not self.server.dealer:
                    raise PermissionError("Login required")
                if not voice_mod.configured():
                    return self.send({"error": "Voice is not configured on this host"}, 503)
                mp3 = voice_mod.synthesize(body.get("text") or "")
                return self.send(mp3, content_type="audio/mpeg")
            if path == "/api/voice-ask":
                if not self.session() and not self.server.dealer:
                    raise PermissionError("Login required")
                question = (body.get("question") or "").strip()
                if not question:
                    raise ValueError("question required")
                dealer = self.scope({"dealer": [body.get("dealer", "")]})
                s = self.prefer_snowflake_store()
                try:
                    name = resolve_metric(question)
                except ValueError as err:
                    if s.backend == "snowflake" and voice_mod.cortex_configured():
                        try:
                            gen = voice_mod.cortex_generate_sql(question)
                            sql = gen.get("sql")
                            if not sql:
                                return self.send(
                                    {
                                        "mode": "voice analytics",
                                        "kind": "clarify",
                                        "answer": gen.get("text") or str(err),
                                        "suggestions": gen.get("suggestions") or [],
                                        "backend": s.backend,
                                        "source": "cortex",
                                        "spoken": (gen.get("text") or str(err))[:480],
                                        "trace": ["voice_ask", "fuzzy_miss", "cortex_no_sql", "clarify"],
                                    },
                                    400,
                                )
                            rows = voice_mod.execute_cortex_select(s, sql)
                            spoken = voice_mod.speakable_cortex(question, rows, sql)
                            s.audit(dealer, "cortex:" + question[:80], len(rows))
                            return self.send(
                                {
                                    "mode": "voice analytics (Cortex Analyst + reader execute)",
                                    "kind": "cortex",
                                    "answer": gen.get("text") or spoken,
                                    "sql": sql,
                                    "rows": rows,
                                    "spoken": spoken,
                                    "backend": s.backend,
                                    "source": "cortex",
                                    "trace": [
                                        "voice_ask",
                                        "prefer_snowflake",
                                        "fuzzy_miss",
                                        "cortex_analyst",
                                        "execute_select",
                                        "speakable_brief",
                                    ],
                                }
                            )
                        except Exception as e:  # noqa: BLE001
                            print("voice cortex failed:", type(e).__name__, str(e)[:200], flush=True)
                            return self.send(
                                {
                                    "mode": "voice analytics",
                                    "kind": "clarify",
                                    "answer": str(err),
                                    "backend": s.backend,
                                    "source": "metric",
                                    "spoken": str(err)[:480],
                                    "trace": ["voice_ask", "fuzzy_miss", "cortex_failed"],
                                },
                                400,
                            )
                    return self.send(
                        {
                            "mode": "voice analytics",
                            "kind": "clarify",
                            "answer": str(err),
                            "backend": s.backend,
                            "source": "metric",
                            "spoken": str(err)[:480],
                            "trace": ["voice_ask", "fuzzy_miss", "clarify"],
                        },
                        400,
                    )
                sql, p = metric_sql(name, dealer, s.dialect)
                rows = s.rows(sql, p)
                s.audit(dealer, name, len(rows))
                spoken = voice_mod.speakable_metric(name, rows, METRICS[name]["description"])
                return self.send(
                    {
                        "mode": "voice analytics (governed metric)",
                        "kind": "metric",
                        "metric": name,
                        "description": METRICS[name]["description"],
                        "sql": sql,
                        "parameters": p,
                        "rows": rows,
                        "spoken": spoken,
                        "backend": s.backend,
                        "source": "metric",
                        "trace": [
                            "voice_ask",
                            "prefer_snowflake",
                            "resolve_metric",
                            "execute_read_only_metric",
                            "speakable_brief",
                        ],
                    }
                )
            if path == "/api/voice-brief":
                if not self.session() and not self.server.dealer:
                    raise PermissionError("Login required")
                dealer = self.scope({"dealer": [body.get("dealer", "")]})
                s = self.prefer_snowflake_store()
                where = " WHERE dealer_id=?" if dealer else ""
                params = [dealer] if dealer else []
                summary = s.rows(
                    "SELECT COUNT(DISTINCT sku_id) AS skus, COALESCE(SUM(units_sold),0) AS units_sold, "
                    "COALESCE(SUM(net_sales_cents),0)/100.0 AS net_sales, "
                    "COALESCE(SUM(margin_cents),0)/100.0 AS margin, "
                    "COALESCE(SUM(on_hand),0) AS on_hand FROM silver_facts" + where,
                    params,
                )[0]
                summary["dealers"] = s.rows("SELECT COUNT(*) AS n FROM dealers" + where, params)[0]["n"]
                channels = s.metric_rows("by_channel", dealer)
                try:
                    stock_risk = s.metric_rows("stock_risk", dealer)[:5]
                except Exception:  # noqa: BLE001
                    stock_risk = []
                spoken = voice_mod.speakable_portfolio_brief(summary, channels, stock_risk)
                s.audit(dealer, "voice_brief", len(channels))
                return self.send(
                    {
                        "mode": "voice portfolio brief",
                        "kind": "brief",
                        "spoken": spoken,
                        "summary": summary,
                        "by_channel": channels,
                        "stock_risk": stock_risk,
                        "backend": s.backend,
                        "source": "brief",
                        "trace": [
                            "voice_brief",
                            "prefer_snowflake",
                            "summary",
                            "by_channel",
                            "stock_risk",
                            "speakable_brief",
                        ],
                    }
                )
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
