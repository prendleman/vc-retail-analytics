#!/usr/bin/env python3
"""Add emails to the existing vc.datasharkbi.com Cloudflare Access allow policy via Playwright.

Usage:
  python3 scripts/cf_access_add_guest_playwright.py \\
    tyler@perceptiverecruiting.com \\
    jegenberg@visualcomfort.com \\
    ragarwal@visualcomfort.com

Opens headed Chromium (~/.cloudflared/pw-profile). Complete Cloudflare login if prompted.
Navigates Zero Trust → Access controls (not the legacy /access/apps path that 404s).
Preserves existing allow entries; only adds missing emails.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PwTimeout
from playwright.sync_api import sync_playwright

HOSTNAME = "vc.datasharkbi.com"
PROFILE = Path.home() / ".cloudflared" / "pw-profile"
SHOTS = Path.home() / ".cloudflared" / "pw-shots"


def shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"add_guest_{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        print(f"screenshot: {path}")
    except Exception as e:
        print(f"screenshot failed: {e}")


def is_login_screen(page) -> bool:
    url = page.url.lower()
    if any(x in url for x in ("/login", "signin", "oauth", "challenge", "accounts.google.com")):
        return True
    try:
        body = page.inner_text("body")[:4000]
    except Exception:
        return False
    return bool(
        re.search(
            r"Sign in to Cloudflare|Continue with SSO|Sign in with Google|Save email and login method",
            body,
            re.I,
        )
    )


def click_text(page, patterns: list[str], timeout: int = 10000) -> bool:
    for pat in patterns:
        for factory in (
            lambda p: page.get_by_role("button", name=re.compile(p, re.I)),
            lambda p: page.get_by_role("link", name=re.compile(p, re.I)),
            lambda p: page.get_by_text(re.compile(p, re.I)),
        ):
            try:
                loc = factory(pat)
                if loc.count():
                    loc.first.click(timeout=timeout)
                    print(f"clicked ~ {pat}")
                    return True
            except Exception:
                continue
    return False


def list_accounts(page) -> list[dict]:
    try:
        data = page.evaluate(
            """async () => {
              const r = await fetch('https://dash.cloudflare.com/api/v4/accounts?per_page=50', {
                credentials: 'include',
                headers: {'Accept': 'application/json'}
              });
              return await r.json();
            }"""
        )
        if data and data.get("success"):
            return data.get("result") or []
        print(f"accounts API payload: {data}")
    except Exception as e:
        print(f"list_accounts: {e}")
    return []


def discover_account_id(page) -> str | None:
    accounts = list_accounts(page)
    if accounts:
        print("accounts visible:", [(a.get("id"), a.get("name")) for a in accounts])
        for a in accounts:
            name = (a.get("name") or "").lower()
            if any(k in name for k in ("aurea", "datashark", "rendleman")):
                return a["id"]
        return accounts[0]["id"]
    m = re.search(r"dash\.cloudflare\.com/([a-f0-9]{32})", page.url)
    return m.group(1) if m else None


def wait_logged_in(page, timeout_s: int = 600) -> str:
    print("Waiting for Cloudflare dashboard login…")
    print("Sign in as the user that owns datasharkbi.com Access (e.g. prendleman@aureaquantra.com).")
    deadline = time.time() + timeout_s
    page.goto("https://dash.cloudflare.com/", wait_until="domcontentloaded", timeout=120000)
    while time.time() < deadline:
        if is_login_screen(page):
            time.sleep(2)
            continue
        try:
            body = page.inner_text("body")[:2000]
        except Exception:
            body = ""
        if "temporarily unavailable" in body.lower():
            time.sleep(5)
            page.reload(wait_until="domcontentloaded", timeout=60000)
            continue
        account_id = discover_account_id(page)
        if account_id:
            print(f"using account_id={account_id}")
            return account_id
        time.sleep(2)
    raise SystemExit("Timed out waiting for dashboard login")


def open_access_applications(page, account_id: str) -> None:
    """Cloudflare One UI: Access controls → Applications (not /access/apps which 404s)."""
    # Newer Zero Trust home
    candidates = [
        f"https://one.dash.cloudflare.com/{account_id}/access/apps",
        f"https://dash.cloudflare.com/{account_id}/one",
        f"https://one.dash.cloudflare.com/{account_id}",
    ]
    for url in candidates:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            time.sleep(2)
        except Exception as e:
            print(f"goto {url}: {e}")
            continue
        body = page.inner_text("body")[:2500]
        if "could not find that page" in body.lower() or "does not belong" in body.lower():
            print(f"skip dead page: {page.url}")
            continue
        # Click Access controls in sidebar
        if click_text(page, [r"Access controls", r"^Access$"]):
            time.sleep(2)
        if click_text(page, [r"^Applications$", r"Applications"]):
            time.sleep(2)
            shot(page, "01_apps")
            return
        if re.search(r"Add an application|Self-hosted|Applications", body, re.I):
            shot(page, "01_apps")
            return
    # Last resort: search nav
    page.goto(f"https://dash.cloudflare.com/{account_id}/one", wait_until="domcontentloaded", timeout=90000)
    time.sleep(2)
    if not click_text(page, [r"Access controls"]):
        raise SystemExit("Could not open Access controls — use sidebar Access controls → Applications manually")
    time.sleep(1)
    if not click_text(page, [r"^Applications$", r"Applications"]):
        raise SystemExit("Opened Access controls but not Applications")
    time.sleep(2)
    shot(page, "01_apps")


def open_vc_app(page) -> None:
    body = page.inner_text("body")
    if HOSTNAME not in body:
        for sel in ('input[placeholder*="Search" i]', 'input[type="search"]', 'input[aria-label*="Search" i]'):
            try:
                if page.locator(sel).count():
                    page.locator(sel).first.fill(HOSTNAME)
                    time.sleep(1.2)
                    break
            except Exception:
                continue
    page.get_by_text(HOSTNAME, exact=False).first.click(timeout=20000)
    print(f"opened {HOSTNAME}")
    time.sleep(2)
    shot(page, "02_app")


def open_policies(page) -> None:
    if not click_text(page, [r"^Policies$", r"Policies"]):
        raise SystemExit("Could not open Policies tab")
    time.sleep(2)
    shot(page, "03_policies")


def open_allow_policy_editor(page) -> None:
    for pat in (r"Configure", r"Edit policy", r"Edit", r"Allow"):
        if click_text(page, [pat]):
            time.sleep(2)
            break
    shot(page, "04_edit")


def add_emails(page, emails: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    body0 = page.inner_text("body").lower()
    for email in emails:
        if email.lower() in body0:
            print(f"already visible: {email}")
            results[email] = "already_present"
            continue
        click_text(page, [r"Add include", r"Add a rule", r"Include", r"Selector"])
        time.sleep(0.4)
        click_text(page, [r"^Emails$", r"^Email$"])
        time.sleep(0.3)
        filled = False
        for sel in (
            'input[placeholder*="email" i]',
            'input[aria-label*="Value" i]',
            'input[aria-label*="email" i]',
            'input[type="email"]',
        ):
            try:
                loc = page.locator(sel)
                if not loc.count():
                    continue
                loc.last.click(timeout=3000)
                loc.last.fill(email, timeout=5000)
                page.keyboard.press("Enter")
                filled = True
                print(f"added: {email}")
                results[email] = "added"
                break
            except Exception:
                continue
        if not filled:
            page.keyboard.type(email)
            page.keyboard.press("Enter")
            print(f"typed: {email}")
            results[email] = "typed"
        time.sleep(0.5)
        body0 = page.inner_text("body").lower()
    shot(page, "05_emails")
    return results


def save_policy(page) -> None:
    for pat in (r"^Save$", r"Save policy", r"Update"):
        if click_text(page, [pat]):
            time.sleep(2)
            print("saved")
            break
    shot(page, "06_saved")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("emails", nargs="+")
    a = ap.parse_args()
    emails = [e.strip().lower() for e in a.emails if e.strip()]

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            viewport={"width": 1440, "height": 920},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            account_id = wait_logged_in(page)
            open_access_applications(page, account_id)
            open_vc_app(page)
            open_policies(page)
            open_allow_policy_editor(page)
            results = add_emails(page, emails)
            save_policy(page)
            time.sleep(2)
            body = page.inner_text("body").lower()
            print("--- policy readback ---")
            for email in emails:
                visible = email.lower() in body
                action = results.get(email, "unknown")
                status = "Confirmed permitted (visible after save)" if visible else f"Unable to verify (action={action})"
                print(f"{email}: {status}")
            print("Leaving browser open 30s…")
            time.sleep(30)
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PwTimeout as e:
        print(f"Playwright timeout: {e}", file=sys.stderr)
        raise SystemExit(1)
