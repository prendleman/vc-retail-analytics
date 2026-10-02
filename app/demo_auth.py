"""Synthetic demo portal users for VC Retail Analytics. Not Visual Comfort credentials."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

DEMO_PASSWORD = "vc-demo"
SECRET = os.environ.get("VC_DEMO_COOKIE_SECRET", "vc-retail-demo-local-secret").encode()

ACCOUNTS = {
    "dlr-0001": {"dealer": "DLR-0001", "role": "dealer", "label": "South Lighting Studio 0001"},
    "dlr-0002": {"dealer": "DLR-0002", "role": "dealer", "label": "West Lighting Studio 0002"},
    "operator": {"dealer": None, "role": "operator", "label": "Internal analyst (all dealers)"},
}


def public_accounts():
    return [
        {"username": u, "label": meta["label"], "dealer": meta["dealer"], "role": meta["role"]}
        for u, meta in ACCOUNTS.items()
    ]


def authenticate(username, password):
    user = (username or "").strip().lower()
    if user not in ACCOUNTS or password != DEMO_PASSWORD:
        return None
    meta = ACCOUNTS[user]
    return {
        "username": user,
        "dealer": meta["dealer"],
        "role": meta["role"],
        "label": meta["label"],
        "iat": int(time.time()),
    }


def _sign(payload: bytes) -> str:
    return hmac.new(SECRET, payload, hashlib.sha256).hexdigest()


def issue_cookie(sess: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(sess, separators=(",", ":")).encode()).decode()
    sig = _sign(raw.encode())
    return f"vc_demo={raw}.{sig}; Path=/; HttpOnly; SameSite=Lax"


def clear_cookie() -> str:
    return "vc_demo=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"


def parse_cookie(header: str | None):
    if not header:
        return None
    for part in header.split(";"):
        part = part.strip()
        if not part.startswith("vc_demo="):
            continue
        val = part.split("=", 1)[1]
        if "." not in val:
            return None
        raw, sig = val.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(raw.encode())):
            return None
        try:
            return json.loads(base64.urlsafe_b64decode(raw.encode()))
        except Exception:
            return None
    return None
