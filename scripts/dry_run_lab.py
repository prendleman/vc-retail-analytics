#!/usr/bin/env python3
"""Dry-run Interview Lab APIs against local origin (run inside Fly or local server)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8770"


def merge_cookie(jar: dict, set_cookie: str | None) -> str:
    if not set_cookie:
        return "; ".join(f"{k}={v}" for k, v in jar.items())
    # Only the first name=value of each Set-Cookie header matters here
    part = set_cookie.split(";")[0]
    if "=" in part:
        k, _, v = part.partition("=")
        jar[k.strip()] = v.strip()
    return "; ".join(f"{k}={v}" for k, v in jar.items())


def req(method, path, body=None, jar=None):
    jar = jar if jar is not None else {}
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if jar:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            raw = resp.read()
            # urllib may only expose one Set-Cookie; fine for our two cookies
            merge_cookie(jar, resp.headers.get("Set-Cookie"))
            return resp.status, json.loads(raw.decode() or "null"), jar
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            j = json.loads(raw)
        except Exception:
            j = {"raw": raw[:400]}
        return e.code, j, jar


def main():
    fails = []
    jar: dict[str, str] = {}
    st, login, jar = req("POST", "/api/login", {"username": "operator", "password": "vc-demo"}, jar)
    if st != 200 or "vc_demo" not in jar:
        print("FAIL login", st, login, jar)
        sys.exit(1)
    print("OK login", list(jar))

    st, h, jar = req("GET", "/api/health", None, jar)
    print("OK health", h.get("backend"), h.get("backends_available"), "voice", h.get("voice"), "cortex", h.get("cortex"))

    st, b, jar = req("POST", "/api/backend", {"backend": "snowflake"}, jar)
    if st == 200 and b.get("ok"):
        print("OK snowflake switch warm_ms", b.get("warm_ms"), list(jar))
    else:
        print("WARN snowflake switch", st, b)
        fails.append("snowflake_switch")

    st, br, jar = req("POST", "/api/voice-board-brief", {}, jar)
    if st == 200 and br.get("kind") == "board_brief" and len(br.get("sections") or []) == 4 and br.get("spoken"):
        print("OK board", br.get("backend"), "ms", br.get("elapsed_ms"), "spoken", len(br["spoken"]))
    else:
        print("FAIL board", st, br)
        fails.append("board")

    st, ev, jar = req("POST", "/api/evals/run", {}, jar)
    if st == 200 and (ev.get("passed") or 0) >= 17:
        print("OK evals", f"{ev.get('passed')}/{ev.get('total')}", ev.get("pass_pct"), "ms", ev.get("elapsed_ms"))
    else:
        print("FAIL evals", st, ev)
        fails.append("evals")

    st, cp, jar = req("POST", "/api/compare", {"question": "show margin percent"}, jar)
    g = (cp or {}).get("governed") or {}
    c = (cp or {}).get("cortex") or {}
    if st == 200 and g.get("ok") and g.get("metric") == "margin_pct":
        print("OK compare governed", "cortex_ok", c.get("ok"), (c.get("error") or c.get("spoken") or "")[:80])
    else:
        print("FAIL compare", st, cp)
        fails.append("compare")

    st, scp, jar = req("POST", "/api/demo-scope", {"dealer": "DLR-0001"}, jar)
    st, port, jar = req("GET", "/api/metric?name=portfolio", None, jar)
    n1 = len((port or {}).get("rows") or [])
    st, scp2, jar = req("POST", "/api/demo-scope", {"dealer": ""}, jar)
    st, port2, jar = req("GET", "/api/metric?name=portfolio", None, jar)
    n2 = len((port2 or {}).get("rows") or [])
    if n1 == 1 and n2 >= 10:
        print("OK scope", "pinned", n1, "all", n2)
    else:
        print("FAIL scope", "pinned", n1, "all", n2, scp)
        fails.append("scope")

    st, pl, jar = req("GET", "/api/plan-90", None, jar)
    if st == 200 and pl.get("title") and len(pl.get("phases") or []) == 3:
        print("OK plan90", pl.get("title"))
    else:
        print("FAIL plan90", st, pl)
        fails.append("plan90")

    if fails:
        print("DRY_RUN_FAIL", fails)
        sys.exit(1)
    print("DRY_RUN_PASS")


if __name__ == "__main__":
    main()
