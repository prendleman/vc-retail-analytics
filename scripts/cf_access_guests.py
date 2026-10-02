#!/usr/bin/env python3
"""Add or refresh Cloudflare Access email allowlist for vc.datasharkbi.com.

Usage:
  python3 scripts/cf_access_guests.py you@company.com recruiter@firm.com
  python3 scripts/cf_access_guests.py --list

Reads CLOUDFLARE_* from .env. Merges new emails with the existing allow policy
(and CLOUDFLARE_ACCESS_ALLOW_EMAIL) instead of wiping prior guests.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOSTNAME = "vc.datasharkbi.com"


def load_env():
    env = dict(os.environ)
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip())
    return env


def cf_api(method: str, path: str, token: str, body=None):
    url = f"https://api.cloudflare.com/client/v4{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if "not_enabled" in err or e.code == 403:
            print(
                "API token cannot manage Access policies (Zero Trust UI still works).\n"
                "Add guests manually:\n"
                "  1) https://one.dash.cloudflare.com/ → Access → Applications\n"
                "  2) Open the vc.datasharkbi.com app → Policies → Allowlist\n"
                f"  3) Add email(s): {', '.join(sys.argv[1:]) or '(your guests)'}\n"
                "  4) Guests open https://vc.datasharkbi.com/ → OTP → operator / vc-demo\n",
                file=sys.stderr,
            )
        raise SystemExit(f"Cloudflare API {method} {path} failed: {e.code} {err}") from e
    if not payload.get("success"):
        raise SystemExit(f"Cloudflare API error: {payload.get('errors')}")
    return payload.get("result")


def main():
    p = argparse.ArgumentParser(description="Manage Access email guests for VC demo")
    p.add_argument("emails", nargs="*", help="Emails to allow (OTP)")
    p.add_argument("--list", action="store_true", help="List current allow emails")
    p.add_argument("--replace", action="store_true", help="Replace policy instead of merge")
    a = p.parse_args()
    env = load_env()
    account = env.get("CLOUDFLARE_ACCOUNT_ID")
    token = env.get("CLOUDFLARE_API_TOKEN")
    if not account or not token or "REPLACE" in (account + token):
        raise SystemExit("Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env")

    apps = cf_api("GET", f"/accounts/{account}/access/apps", token) or []
    app = next(
        (
            x
            for x in apps
            if x.get("domain") == HOSTNAME
            or HOSTNAME in (x.get("self_hosted_domains") or [])
            or any(
                isinstance(d, dict) and d.get("hostname") == HOSTNAME
                for d in (x.get("destinations") or [])
            )
        ),
        None,
    )
    if not app:
        raise SystemExit(f"No Access app found for {HOSTNAME} — run scripts/cf_setup_permanent.py first")

    policies = cf_api("GET", f"/accounts/{account}/access/apps/{app['id']}/policies", token) or []
    allow_pol = next((x for x in policies if x.get("decision") == "allow"), None)
    existing = set()
    if allow_pol:
        for rule in allow_pol.get("include") or []:
            if "email" in rule and isinstance(rule["email"], dict):
                existing.add(rule["email"]["email"].lower())
            if "email_domain" in rule and isinstance(rule["email_domain"], dict):
                existing.add("*@" + rule["email_domain"]["domain"].lower())

    base = env.get("CLOUDFLARE_ACCESS_ALLOW_EMAIL", "")
    if base:
        existing.add(base.lower())
    # Known demo owner emails used during setup
    existing.add("prendleman@aureaquantra.com")

    if a.list and not a.emails:
        print(f"Access app: {app.get('name')} ({app['id']})")
        for e in sorted(existing):
            print(f"  {e}")
        return 0

    if not a.emails:
        raise SystemExit("Pass one or more emails, or --list")

    new = {e.strip().lower() for e in a.emails if e.strip() and "@" in e}
    if a.replace:
        emails = sorted(new | ({base.lower()} if base else set()) | {"prendleman@aureaquantra.com"})
    else:
        emails = sorted(existing | new)

    include = [{"email": {"email": e}} for e in emails if not e.startswith("*@")]
    body = {"name": "Allowlist email", "decision": "allow", "include": include}
    if allow_pol:
        cf_api("PUT", f"/accounts/{account}/access/apps/{app['id']}/policies/{allow_pol['id']}", token, body)
        print(f"updated allow policy ({len(emails)} emails)")
    else:
        cf_api("POST", f"/accounts/{account}/access/apps/{app['id']}/policies", token, body)
        print(f"created allow policy ({len(emails)} emails)")
    for e in emails:
        print(f"  {e}")
    print(f"\nGuests open https://{HOSTNAME}/ → Access email OTP → demo login dlr-0001 / vc-demo")
    print("Hard-refresh (Cmd+Shift+R) after login if Analytics looks like TSV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
