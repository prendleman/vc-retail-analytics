#!/usr/bin/env python3
"""One-time Cloudflare setup for permanent vc.datasharkbi.com share.

Mirrors aq-relief-data/scripts/cf_route53_setup.ps1 for the already-migrated
datasharkbi.com zone: create named tunnel + DNS + Access allowlist.

Secrets stay local (.env / ~/.cloudflared). Never prints token values.
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
CF_HOME = Path.home() / ".cloudflared"
DEFAULT_DOMAIN = "datasharkbi.com"
DEFAULT_SUBDOMAIN = "vc"
DEFAULT_TUNNEL = "vc-retail-demo"
DEFAULT_ORIGIN = "http://127.0.0.1:8770"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def cf_api(method: str, path: str, token: str, body=None):
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise SystemExit(f"Cloudflare API {method} {path} failed ({e.code}): {err}") from e
    if not payload.get("success"):
        raise SystemExit(f"Cloudflare API error: {json.dumps(payload.get('errors'))}")
    return payload.get("result")


def main() -> int:
    p = argparse.ArgumentParser(description="Setup permanent Cloudflare Tunnel + Access for VC demo")
    p.add_argument("--domain", default=DEFAULT_DOMAIN)
    p.add_argument("--subdomain", default=DEFAULT_SUBDOMAIN)
    p.add_argument("--tunnel-name", default=DEFAULT_TUNNEL)
    p.add_argument("--origin", default=DEFAULT_ORIGIN)
    p.add_argument("--allow-email", action="append", default=[])
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    load_dotenv(ROOT / ".env")
    hostname = f"{a.subdomain}.{a.domain}"
    token = (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    account = (os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    allow = list(a.allow_email)
    env_email = (os.environ.get("CLOUDFLARE_ACCESS_ALLOW_EMAIL") or "").strip()
    if env_email:
        allow.append(env_email)
    # support comma-separated
    expanded = []
    for e in allow:
        expanded.extend([x.strip() for x in e.split(",") if x.strip()])
    allow = sorted(set(expanded))

    if not token or token.startswith("REPLACE"):
        print("Missing CLOUDFLARE_API_TOKEN in .env", file=sys.stderr)
        print("See docs/SHARE_PRIVATE.md", file=sys.stderr)
        return 2
    if not account or account.startswith("REPLACE"):
        print("Missing CLOUDFLARE_ACCOUNT_ID in .env", file=sys.stderr)
        return 2
    if not allow:
        print("Need at least one allowlist email (--allow-email or CLOUDFLARE_ACCESS_ALLOW_EMAIL)", file=sys.stderr)
        return 2

    print(f"hostname={hostname} tunnel={a.tunnel_name} origin={a.origin} dry_run={a.dry_run}")
    print(f"allow_emails={len(allow)}")

    zones = cf_api("GET", f"/zones?name={a.domain}", token)
    if not zones:
        raise SystemExit(f"Zone {a.domain} not found on this Cloudflare account")
    zone = zones[0] if isinstance(zones, list) else zones
    zone_id = zone["id"]
    print(f"zone_id={zone_id} status={zone.get('status')}")

    tunnels = cf_api("GET", f"/accounts/{account}/cfd_tunnel?is_deleted=false", token) or []
    tunnel = next((t for t in tunnels if t.get("name") == a.tunnel_name), None)

    if a.dry_run:
        print(f"[dry-run] would ensure tunnel {a.tunnel_name}, DNS {hostname}, Access app, allow {allow}")
        return 0

    if not tunnel:
        tunnel = cf_api(
            "POST",
            f"/accounts/{account}/cfd_tunnel",
            token,
            {"name": a.tunnel_name, "config_src": "cloudflare"},
        )
        print(f"created tunnel id={tunnel['id']}")
    else:
        print(f"tunnel exists id={tunnel['id']}")

    tunnel_id = tunnel["id"]

    # Tunnel token for cloudflared tunnel run --token
    tok = cf_api("GET", f"/accounts/{account}/cfd_tunnel/{tunnel_id}/token", token)
    # API may return bare string or object
    run_token = tok if isinstance(tok, str) else (tok.get("token") if isinstance(tok, dict) else None)
    if not run_token:
        raise SystemExit("Could not fetch tunnel run token")

    CF_HOME.mkdir(parents=True, exist_ok=True)
    token_path = CF_HOME / f"{a.tunnel_name}.run.token"
    token_path.write_text(run_token.strip() + "\n", encoding="utf-8")
    token_path.chmod(0o600)
    print(f"wrote {token_path} (chmod 600)")

    # Remotely managed ingress
    cf_api(
        "PUT",
        f"/accounts/{account}/cfd_tunnel/{tunnel_id}/configurations",
        token,
        {
            "config": {
                "ingress": [
                    {"hostname": hostname, "service": a.origin},
                    {"service": "http_status:404"},
                ]
            }
        },
    )
    print(f"ingress {hostname} -> {a.origin}")

    # DNS CNAME proxied
    existing = cf_api("GET", f"/zones/{zone_id}/dns_records?type=CNAME&name={hostname}", token) or []
    target = f"{tunnel_id}.cfargotunnel.com"
    if existing:
        rec = existing[0]
        cf_api(
            "PUT",
            f"/zones/{zone_id}/dns_records/{rec['id']}",
            token,
            {"type": "CNAME", "name": hostname, "content": target, "proxied": True, "ttl": 1},
        )
        print(f"dns updated CNAME {hostname} -> {target}")
    else:
        cf_api(
            "POST",
            f"/zones/{zone_id}/dns_records",
            token,
            {"type": "CNAME", "name": hostname, "content": target, "proxied": True, "ttl": 1},
        )
        print(f"dns created CNAME {hostname} -> {target}")

    # Access self-hosted app
    apps = cf_api("GET", f"/accounts/{account}/access/apps", token) or []
    app = next(
        (
            x
            for x in apps
            if x.get("domain") == hostname
            or hostname in (x.get("self_hosted_domains") or [])
            or any(d.get("hostname") == hostname for d in (x.get("destinations") or []) if isinstance(d, dict))
        ),
        None,
    )
    if not app:
        app = cf_api(
            "POST",
            f"/accounts/{account}/access/apps",
            token,
            {
                "name": "VC Retail Analytics Demo",
                "domain": hostname,
                "type": "self_hosted",
                "session_duration": "24h",
                "auto_redirect_to_identity": True,
            },
        )
        print(f"created Access app id={app['id']}")
    else:
        print(f"Access app exists id={app['id']}")

    policies = cf_api("GET", f"/accounts/{account}/access/apps/{app['id']}/policies", token) or []
    include = [{"email": {"email": e}} for e in allow]
    allow_pol = next((x for x in policies if x.get("decision") == "allow"), None)
    body = {"name": "Allowlist email", "decision": "allow", "include": include}
    if allow_pol:
        cf_api(
            "PUT",
            f"/accounts/{account}/access/apps/{app['id']}/policies/{allow_pol['id']}",
            token,
            body,
        )
        print("updated Access allow policy")
    else:
        cf_api(
            "POST",
            f"/accounts/{account}/access/apps/{app['id']}/policies",
            token,
            body,
        )
        print("created Access allow policy")

    config_path = CF_HOME / "config.vc-retail.yml"
    config_path.write_text(
        f"""# Generated by scripts/cf_setup_permanent.py — do not commit
tunnel: {tunnel_id}
# Prefer: cloudflared tunnel run --token "$(cat ~/.cloudflared/{a.tunnel_name}.run.token)"

ingress:
  - hostname: {hostname}
    service: {a.origin}
  - service: http_status:404
""",
        encoding="utf-8",
    )
    print(f"wrote {config_path}")

    # Persist hostname hint for deck / scripts
    hint = ROOT / ".env"
    # do not rewrite secrets; only remind
    print(
        f"""
DONE.
  1) python3 -m app.server
  2) ./scripts/share_private.sh
  3) Open https://{hostname}  (Access email OTP, then dlr-0001 / vc-demo)
  4) VC_DEMO_URL=https://{hostname}/ python3 scripts/gen_deck.py
"""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
