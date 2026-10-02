"""Optional Cortex Analyst client against SERVING.VC_RETAIL_SEMANTICS.

Requires SNOWFLAKE_HOST + SNOWFLAKE_PAT in the environment. Never commit secrets.
This script proposes answers; it does not auto-run arbitrary model SQL.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request


def main():
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--semantic-view", default="VC_RETAIL_DEMO.SERVING.VC_RETAIL_SEMANTICS")
    a = p.parse_args()
    host = os.environ.get("SNOWFLAKE_HOST")
    pat = os.environ.get("SNOWFLAKE_PAT")
    if not host or not pat:
        raise SystemExit("Set SNOWFLAKE_HOST and SNOWFLAKE_PAT (see .env.example).")
    body = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": a.question}]}],
        "semantic_view": a.semantic_view,
    }
    req = urllib.request.Request(
        f"https://{host}/api/v2/cortex/analyst/message",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        print(json.dumps(json.loads(resp.read().decode()), indent=2))


if __name__ == "__main__":
    main()
