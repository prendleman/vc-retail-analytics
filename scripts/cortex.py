"""Optional Cortex Analyst client against the SERVING semantic views.

Requires SNOWFLAKE_PAT plus SNOWFLAKE_ACCOUNT (org-account identifier) or SNOWFLAKE_HOST in the
environment. Never commit secrets. Cortex Analyst only *generates* SQL; this script prints the
interpretation and the SQL and does not execute it. Run the SQL yourself as the reader principal
so the row access policy applies (see docs/evidence/cortex_analyst.txt for a logged run).

    SNOWFLAKE_ACCOUNT=ORG-ACCOUNT SNOWFLAKE_PAT=... python3 -m scripts.cortex "What is net sales by channel?"
    ... --semantic-view VC_RETAIL_DEMO.SERVING.VC_SUPPLY_SEMANTICS "Open PO value by vendor country?"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--semantic-view", default="VC_RETAIL_DEMO.SERVING.VC_RETAIL_SEMANTICS")
    p.add_argument("--raw", action="store_true", help="print the full JSON response")
    a = p.parse_args()
    host = os.environ.get("SNOWFLAKE_HOST") or (
        f"{os.environ['SNOWFLAKE_ACCOUNT']}.snowflakecomputing.com" if os.environ.get("SNOWFLAKE_ACCOUNT") else None
    )
    pat = os.environ.get("SNOWFLAKE_PAT")
    if not host or not pat:
        raise SystemExit("Set SNOWFLAKE_PAT and SNOWFLAKE_ACCOUNT (or SNOWFLAKE_HOST); see .env.example.")
    body = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": a.question}]}],
        "semantic_view": a.semantic_view,
    }
    req = urllib.request.Request(
        f"https://{host}/api/v2/cortex/analyst/message",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {pat}",
            "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode()[:800]}")
    if a.raw:
        print(json.dumps(data, indent=2))
        return
    print(f"request_id: {data.get('request_id')}")
    for part in data.get("message", {}).get("content", []):
        kind = part.get("type")
        if kind == "text":
            print("\n" + part.get("text", "").strip())
        elif kind == "sql":
            print("\n-- SQL (not executed):\n" + part.get("statement", "").strip())
        elif kind == "suggestions":
            print("\nsuggestions:", *[f"  - {s}" for s in part.get("suggestions", [])], sep="\n")
    if data.get("warnings"):
        print("\nwarnings:", json.dumps(data["warnings"]), file=sys.stderr)


if __name__ == "__main__":
    main()
