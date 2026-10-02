#!/usr/bin/env python3
"""Create Cloudflare Access (self-hosted) for vc.datasharkbi.com via Playwright.

Headed browser + persistent profile. Complete login as prendleman@aureaquantra.com
if prompted, then the script finishes the Access app + email allow policy.
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
APP_NAME = "VC Retail Analytics Demo"
PROFILE = Path.home() / ".cloudflared" / "pw-profile"
SHOTS = Path.home() / ".cloudflared" / "pw-shots"


def shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        print(f"screenshot: {path}")
    except Exception as e:
        print(f"screenshot failed: {e}")


def is_login_screen(page) -> bool:
    url = page.url.lower()
    if any(
        x in url
        for x in (
            "/login",
            "signin",
            "oauth",
            "challenge",
            "accounts.google.com",
            "appleid.apple.com",
            "github.com/login",
        )
    ):
        return True
    try:
        body = page.inner_text("body")[:4000]
    except Exception:
        return False
    return bool(
        re.search(
            r"Sign in to Cloudflare|Log in to Cloudflare|Continue with SSO|"
            r"Forgot your email|Sign in with Google|Enter your password|"
            r"Email or phone",
            body,
            re.I,
        )
    )


def on_access_apps(page) -> bool:
    """True when Zero Trust Access Applications UI is visible."""
    if is_login_screen(page):
        return False
    try:
        body = page.inner_text("body")[:5000]
    except Exception:
        return False
    return bool(
        re.search(r"Add an application|Access applications|Self-hosted", body, re.I)
    ) and ("one.dash.cloudflare.com" in page.url or "Applications" in body)


def wait_for_login(page, timeout_s: int = 600) -> None:
    """Wait until Access Applications page is reachable (user completes Google/SSO)."""
    deadline = time.time() + timeout_s
    print("Waiting for Cloudflare Zero Trust login in the Playwright window…")
    print("Use prendleman@aureaquantra.com (complete Google/SSO yourself).")
    print("Script continues only after Access → Applications is visible.")
    page.goto("https://one.dash.cloudflare.com/", wait_until="domcontentloaded", timeout=120000)
    while time.time() < deadline:
        if is_login_screen(page):
            try:
                email = page.locator(
                    'input[type="email"], input[name="email"], input[autocomplete="username"], input[type="text"]'
                ).first
                if email.count():
                    cur = email.input_value()
                    if "aureaquantra" not in cur and "@" not in cur:
                        # don't fight Google mid-flow if user is typing
                        if "accounts.google.com" not in page.url:
                            email.fill("prendleman@aureaquantra.com")
            except Exception:
                pass
            time.sleep(2)
            continue
        # Navigate to apps once past login
        if "one.dash.cloudflare.com" in page.url or "dash.cloudflare.com" in page.url:
            if not on_access_apps(page):
                try:
                    page.goto(
                        "https://one.dash.cloudflare.com/access/apps",
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                except Exception:
                    pass
                time.sleep(2)
            if on_access_apps(page):
                print(f"Access apps ready: {page.url}")
                return
        time.sleep(2)
    raise SystemExit("Timed out — finish login in the Playwright window, then re-run")

def discover_account_id(page) -> str | None:
    """Try to read account id from Zero Trust / dash URLs."""
    for _ in range(10):
        m = re.search(r"one\.dash\.cloudflare\.com/([a-f0-9]{32})", page.url)
        if m:
            return m.group(1)
        m = re.search(r"dash\.cloudflare\.com/([a-f0-9]{32})", page.url)
        if m:
            return m.group(1)
        time.sleep(0.5)
    # Probe accounts API via page evaluate fetch (session cookies)
    try:
        data = page.evaluate(
            """async () => {
              const r = await fetch('https://api.cloudflare.com/client/v4/accounts', {credentials:'include'});
              return await r.json();
            }"""
        )
        if data and data.get("success") and data.get("result"):
            return data["result"][0]["id"]
    except Exception as e:
        print(f"account probe via fetch failed: {e}")
    return None


def click_first(page, selectors: list[str], timeout: int = 8000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.click(timeout=timeout)
            print(f"clicked: {sel}")
            return True
        except Exception:
            continue
    return False


def fill_first(page, selectors: list[str], value: str, timeout: int = 8000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.fill(value, timeout=timeout)
            print(f"filled: {sel}")
            return True
        except Exception:
            continue
    return False


def create_access_via_api(page, account_id: str, emails: list[str]) -> bool:
    """Prefer API using dashboard session (Bearer from cookie boot) — often blocked.

    Falls back to false so UI path runs.
    """
    try:
        result = page.evaluate(
            """async ({ accountId, hostname, appName, emails }) => {
              // Session cookie auth does not work on api.cloudflare.com for most accounts.
              // Return null to force UI.
              return null;
            }""",
            {
                "accountId": account_id,
                "hostname": HOSTNAME,
                "appName": APP_NAME,
                "emails": emails,
            },
        )
        return bool(result)
    except Exception:
        return False


def create_access_ui(page, account_id: str | None, emails: list[str]) -> None:
    base = f"https://one.dash.cloudflare.com/{account_id}" if account_id else "https://one.dash.cloudflare.com"
    # Applications list
    apps_url = f"{base}/access/apps"
    print(f"goto {apps_url}")
    page.goto(apps_url, wait_until="domcontentloaded", timeout=120000)
    time.sleep(3)
    shot(page, "01_apps")

    # If already exists, stop
    try:
        if page.get_by_text(HOSTNAME, exact=False).count() > 0:
            print(f"Access app mentioning {HOSTNAME} already present — checking policy only")
            page.get_by_text(HOSTNAME, exact=False).first.click(timeout=5000)
            time.sleep(2)
            shot(page, "01b_existing")
    except Exception:
        pass

    # Add application
    added = click_first(
        page,
        [
            'role=button[name=/Add an application/i]',
            'role=link[name=/Add an application/i]',
            'button:has-text("Add an application")',
            'a:has-text("Add an application")',
            'button:has-text("Add")',
        ],
    )
    if not added:
        # Direct new URL variants — ignore aborted navigations
        for path in ("/access/apps/add", "/access/apps/new", "/access/apps/add/self-hosted"):
            try:
                page.goto(f"{base}{path}", wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)
                shot(page, f"02_try_{path.replace('/', '_')}")
                content = page.content().lower()
                if "self-hosted" in content or "application name" in content:
                    break
            except Exception as e:
                print(f"goto {path} skipped: {e}")
                continue
    time.sleep(2)
    shot(page, "02_add_menu")

    # Choose Self-hosted
    click_first(
        page,
        [
            'role=button[name=/Self-hosted/i]',
            'role=link[name=/Self-hosted/i]',
            'text=Self-hosted',
            '[data-testid*="self-hosted"]',
        ],
    )
    time.sleep(2)
    shot(page, "03_self_hosted")

    # Application name
    fill_first(
        page,
        [
            'input[name="name"]',
            'input[placeholder*="name" i]',
            'label:has-text("Application name") >> .. >> input',
            'input[aria-label*="Application name" i]',
        ],
        APP_NAME,
    )

    # Domain / public hostname
    # Newer UI: subdomain + domain select, or single hostname field
    filled_host = fill_first(
        page,
        [
            'input[name="domain"]',
            'input[placeholder*="example.com" i]',
            'input[aria-label*="domain" i]',
            'input[aria-label*="hostname" i]',
        ],
        HOSTNAME,
    )
    if not filled_host:
        # Split subdomain + zone
        fill_first(
            page,
            [
                'input[name="subdomain"]',
                'input[placeholder*="subdomain" i]',
                'input[aria-label*="Subdomain" i]',
            ],
            "vc",
        )
        # domain dropdown
        if click_first(page, ['role=combobox', 'select', '[aria-label*="Domain" i]']):
            time.sleep(0.5)
            click_first(page, ['text=datasharkbi.com', 'role=option[name=/datasharkbi\\.com/i]'])

    # Path often defaults to /
    time.sleep(1)
    shot(page, "04_filled_app")

    # Next / Add application
    click_first(
        page,
        [
            'role=button[name=/Next/i]',
            'button:has-text("Next")',
            'button:has-text("Add application")',
            'button:has-text("Save")',
        ],
    )
    time.sleep(3)
    shot(page, "05_policy")

    # Policy name
    fill_first(
        page,
        [
            'input[name="policy.name"]',
            'input[name="name"]',
            'input[aria-label*="Policy name" i]',
            'label:has-text("Policy name") >> .. >> input',
        ],
        "Allowlist email",
    )

    # Action = Allow (usually default)
    click_first(page, ['role=button[name=/Allow/i]', 'text=Allow'])

    # Selector: Emails
    click_first(
        page,
        [
            'role=button[name=/Selector/i]',
            'text=Selector',
            '[aria-label*="Selector" i]',
        ],
    )
    time.sleep(0.5)
    click_first(page, ['role=option[name=/Emails/i]', 'text=Emails', 'text=Email'])
    time.sleep(0.5)

    # Value emails
    for email in emails:
        filled = fill_first(
            page,
            [
                'input[placeholder*="email" i]',
                'input[aria-label*="Value" i]',
                'input[aria-label*="email" i]',
                'input[type="email"]',
            ],
            email,
        )
        if filled:
            page.keyboard.press("Enter")
            time.sleep(0.4)
            print(f"added email: {email}")

    shot(page, "06_policy_filled")

    # Next / Save / Add application
    for label in ("Next", "Save", "Add application", "Create application"):
        if click_first(page, [f'role=button[name=/{label}/i]', f'button:has-text("{label}")']):
            time.sleep(2)

    shot(page, "07_done")
    print("Access UI flow finished — verify in dashboard and with curl -I https://vc.datasharkbi.com/")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--email",
        action="append",
        default=[],
        help="Allowlist email (repeatable). Default: prendleman@aureaquantra.com",
    )
    ap.add_argument("--headed", action="store_true", default=True)
    a = ap.parse_args()
    emails = a.email or ["prendleman@aureaquantra.com"]

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://one.dash.cloudflare.com/", wait_until="domcontentloaded", timeout=120000)
        wait_for_login(page)
        account_id = discover_account_id(page)
        print(f"account_id={account_id or '(unknown)'}")
        if account_id:
            create_access_via_api(page, account_id, emails)
        create_access_ui(page, account_id, emails)
        # Leave browser open briefly for visual confirm
        time.sleep(5)
        # Verify Access redirect
        try:
            import urllib.request

            req = urllib.request.Request(f"https://{HOSTNAME}/", method="HEAD")
            with urllib.request.urlopen(req, timeout=20) as resp:
                print(f"HEAD {HOSTNAME} -> {resp.status}")
        except Exception as e:
            # 302 to Access often raises as HTTPError
            err = getattr(e, "code", None)
            loc = getattr(e, "headers", {}) and e.headers.get("Location")
            print(f"probe {HOSTNAME}: code={err} location={loc} ({type(e).__name__})")
        context.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PwTimeout as e:
        print(f"Playwright timeout: {e}", file=sys.stderr)
        raise SystemExit(1)
