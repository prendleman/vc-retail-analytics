#!/usr/bin/env python3
"""Submission PDF deck (evidence-backed, 10 core slides + appendix).

Output:
  docs/deck/VC_Retail_Analytics_Submission_Final.pdf
  docs/deck/VC_Retail_Analytics_Submission_Revised.pdf  (same bytes alias)
  docs/deck/VC_Retail_Analytics_Deck.html  (editable source mirror)
  docs/deck/VC_Retail_Analytics_Deck.pdf   (same render alias)
"""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "deck" / "assets"
OUT_HTML = ROOT / "docs" / "deck" / "VC_Retail_Analytics_Deck.html"
OUT_PDF = ROOT / "docs" / "deck" / "VC_Retail_Analytics_Submission_Final.pdf"
OUT_PDF_REVISED = ROOT / "docs" / "deck" / "VC_Retail_Analytics_Submission_Revised.pdf"
OUT_PDF_ALIAS = ROOT / "docs" / "deck" / "VC_Retail_Analytics_Deck.pdf"
DEMO_URL = os.environ.get("VC_DEMO_URL", "https://vc.datasharkbi.com/").rstrip("/") + "/"
GITHUB_URL = os.environ.get(
    "VC_GITHUB_URL", "https://github.com/prendleman/vc-retail-analytics"
).rstrip("/")
# Application build under local/hosted smoke (docs-only commits excluded).
LOCAL_TESTED = os.environ.get("VC_LOCAL_TESTED", "c24bebd")
HOSTED_BUILD = os.environ.get("VC_HOSTED_BUILD", "c24bebd")
TOTAL = 13  # 11 core + 2 appendix


def uri(name: str) -> str:
    return (ASSETS / name).resolve().as_uri()


def foot(n: int) -> str:
    return (
        f'<div class="foot"><span>VC Retail Analytics · synthetic · Paul Rendleman</span>'
        f'<a href="{DEMO_URL}">{DEMO_URL.rstrip("/")}</a>'
        f'<span>{n} / {TOTAL}</span></div>'
    )


def build_html() -> str:
    hero = uri("vc-hero-lighting.jpg")
    shot_m = uri("shot_analytics_margin.png")
    shot_a = uri("shot_assistant_margin.png")
    shot_o = uri("shot_overview.png")
    arch = uri("arch_flow.png")
    e2e = uri("wiring_e2e.png")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>VC Retail Analytics — Submission Revised</title>
<style>
  @page {{ size: Letter landscape; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0; color: #1c1914;
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    background: #f3efe6;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }}
  .page {{
    width: 11in; height: 8.5in; page-break-after: always; position: relative; overflow: hidden;
    background: radial-gradient(900px 420px at 8% -10%, #fff8ea, transparent),
                linear-gradient(180deg, #f7f2e8, #f3efe6);
  }}
  .page:last-child {{ page-break-after: auto; }}
  .page.hero, .page.dark {{ background: #1c1914; color: #f4efe4; }}
  .hero-bg {{
    position: absolute; inset: 0;
    background: linear-gradient(90deg, rgba(28,25,20,.94) 0%, rgba(28,25,20,.7) 45%, rgba(28,25,20,.3) 100%),
                url('{hero}') center/cover no-repeat;
  }}
  .accent-bar {{ position: absolute; left: 42%; top: 0; bottom: 0; width: 4px; background: #8a6a3b; }}
  .pad {{ padding: 0.48in 0.58in 0.46in; position: relative; z-index: 1; height: 100%; }}
  .eyebrow {{
    text-transform: uppercase; letter-spacing: 0.14em; font-size: 11px;
    color: #8a6a3b; font-weight: 600; margin: 0 0 8px;
  }}
  .hero .eyebrow, .dark .eyebrow {{ color: #c4a574; }}
  h1 {{
    font-family: "Iowan Old Style", Palatino, Georgia, serif;
    font-weight: 500; font-size: 36px; line-height: 1.08; letter-spacing: -0.02em;
    margin: 0 0 10px; max-width: 6in;
  }}
  h2 {{
    font-family: "Iowan Old Style", Palatino, Georgia, serif;
    font-weight: 500; font-size: 24px; margin: 0 0 8px; letter-spacing: -0.02em;
  }}
  h3 {{ font-family: "Iowan Old Style", Georgia, serif; font-weight: 500; font-size: 14px; margin: 0 0 6px; }}
  .lede {{ font-size: 14px; line-height: 1.45; color: #6b6458; max-width: 5.8in; margin: 0 0 12px; }}
  .hero .lede, .dark .lede {{ color: #c8c0b0; }}
  .fine {{ font-size: 11.5px; color: #6b6458; }}
  .hero .fine, .dark .fine {{ color: #8a8378; }}
  a.cta {{
    display: inline-block; background: #8a6a3b; color: #fffdf8 !important;
    text-decoration: none; padding: 11px 18px; font-size: 13px; font-weight: 600; border-radius: 2px;
  }}
  a.url {{ color: #8a6a3b; font-weight: 600; font-size: 12.5px; text-decoration: underline; text-underline-offset: 3px; }}
  .hero a.url {{ color: #c4a574; }}
  .chips {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }}
  .chip {{
    border: 1px solid #8a6a3b; color: #8a6a3b; font-size: 10px; letter-spacing: 0.08em;
    padding: 5px 9px; text-transform: uppercase;
  }}
  .hero .chip {{ border-color: #c4a574; color: #c4a574; }}
  .title-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
  .title-row .bar {{ width: 4px; height: 24px; background: #8a6a3b; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .grid3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
  .grid4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
  .card {{
    background: #fffdf8; border: 1px solid #d9d0c0; padding: 11px 12px; border-top: 3px solid #8a6a3b;
  }}
  .card p {{ margin: 0; font-size: 11.5px; line-height: 1.4; color: #6b6458; }}
  .card.ink {{ background: #1c1914; border-color: #3a342c; color: #f4efe4; }}
  .card.ink p {{ color: #c8c0b0; }}
  .card.ink h3 {{ color: #c4a574; }}
  img.shot {{
    width: 100%; height: auto; max-height: 4.85in; object-fit: contain; object-position: top;
    display: block; border: 1px solid #d9d0c0; background: #fffdf8;
  }}
  img.diag {{
    width: 100%; max-height: 4.2in; object-fit: contain; display: block;
    border: 1px solid #d9d0c0; background: #fffdf8;
  }}
  table.data {{
    width: 100%; border-collapse: collapse; font-size: 11.5px; background: #fffdf8;
    border: 1px solid #d9d0c0; margin-top: 6px;
  }}
  table.data th, table.data td {{
    text-align: left; padding: 7px 10px; border-bottom: 1px solid #d9d0c0; vertical-align: top;
  }}
  table.data th {{
    background: #e8dfcf; font-size: 10px; letter-spacing: 0.05em; text-transform: uppercase;
  }}
  .pass {{ color: #2f5a28; font-weight: 700; }}
  .note {{ color: #7a4020; font-weight: 600; }}
  .foot {{
    position: absolute; left: 0.58in; right: 0.58in; bottom: 0.24in;
    display: flex; justify-content: space-between; align-items: center;
    font-size: 10px; color: #6b6458; border-top: 1px solid #d9d0c0; padding-top: 5px;
  }}
  .hero .foot, .dark .foot {{ color: #8a8378; border-color: rgba(217,208,192,.25); }}
  .foot a {{ color: #8a6a3b; font-weight: 600; }}
  .link-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; align-items: center; }}
  ul.clean {{ margin: 6px 0 0; padding-left: 1.05rem; color: #6b6458; font-size: 12px; line-height: 1.45; }}
  .callout {{
    background: #1c1914; color: #f4efe4; padding: 12px 14px; margin-top: 10px; border-left: 3px solid #c4a574;
    font-size: 12.5px; line-height: 1.4;
  }}
  .callout strong {{ color: #c4a574; }}
</style>
</head>
<body>

<!-- 1 Purpose -->
<section class="page hero">
  <div class="hero-bg"></div>
  <div class="accent-bar"></div>
  <div class="pad" style="display:flex;flex-direction:column;justify-content:center;max-width:6.2in;">
    <p class="eyebrow">Independent prototype · Synthetic data</p>
    <h1>VC Retail Analytics</h1>
    <p class="lede" style="max-width:5.9in;">An independent analytics prototype for designer-lighting retail workflows. Synthetic retail data sized to public Visual Comfort scale, controlled metric queries, voice on Snowflake, Market / competitor share plays, and an Interview Lab for AI-engineering conversation.</p>
    <p class="fine" style="color:#c8c0b0;max-width:5.9in;">The typed assistant is <strong style="color:#f4efe4;">not an LLM</strong>. It routes supported prompts to approved metric queries and returns traceable SQL and rows. Voice can fuzzy-route, then fall back to Cortex Analyst on Snowflake. That constraint is the engineering point: tool access, metric definitions, user scope, and testable responses.</p>
    <div class="link-row" style="margin-top:14px;">
      <a class="cta" href="{DEMO_URL}">Open hosted demo →</a>
    </div>
    <div class="link-row">
      <a class="url" href="{DEMO_URL}">{DEMO_URL.rstrip('/')}</a>
      <a class="url" href="{GITHUB_URL}">GitHub (public)</a>
    </div>
    <div class="chips">
      <span class="chip">Synthetic</span>
      <span class="chip">SQLite + Snowflake</span>
      <span class="chip">Interview Lab</span>
      <span class="chip">Access-gated</span>
    </div>
    <p class="fine" style="margin-top:18px;">Paul Rendleman · independent prototype</p>
  </div>
</section>

<!-- 2 Working analytics -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Working product</p>
    <div class="title-row"><div class="bar"></div><h2>Which channel has the thinnest margin?</h2></div>
    <p class="lede" style="max-width:100%;">Live capture from the synthetic app (operator session). Margin section shows margin % by channel, mix contribution waterfall, and price realization. Insight callouts summarize the approved metric results.</p>
    <img class="shot" src="{shot_m}" alt="Analytics margin view screenshot" />
    <p class="fine" style="margin-top:8px;">Business next step: inspect mix and discounts on the thinnest channel, then low-margin SKUs. Numbers are synthetic fixtures, not Visual Comfort business results.</p>
  </div>
  {foot(2)}
</section>

<!-- 3 Traceable assistant -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Traceable assistant</p>
    <div class="title-row"><div class="bar"></div><h2>Supported prompt → approved query → result</h2></div>
    <div class="grid2">
      <div>
        <img class="shot" src="{shot_a}" alt="Assistant margin percent response" style="max-height:5.3in;" />
      </div>
      <div>
        <div class="card">
          <h3>Exact prompt used</h3>
          <p><code>show margin percent</code></p>
        </div>
        <div class="card" style="margin-top:10px;">
          <h3>What returned</h3>
          <p>Metric <code>margin_pct</code>, one-line insight, bar chart, table, and expandable SQL + tool trace. Scope follows the signed session (operator = all dealers).</p>
        </div>
        <div class="card" style="margin-top:10px;">
          <h3>Unsupported requests</h3>
          <p>Invented forecasts and free-form questions are refused or clarified. The router only accepts an exact supported vocabulary.</p>
        </div>
        <div class="callout"><strong>Proposed (not built):</strong> an LLM could interpret natural language, then call the same approved tools, with authorization enforced outside the model.</div>
      </div>
    </div>
  </div>
  {foot(3)}
</section>

<!-- 4 Retail use cases -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Coverage in the app</p>
    <div class="title-row"><div class="bar"></div><h2>Analytics sections actually implemented</h2></div>
    <div class="grid2" style="margin-bottom:10px;">
      <img class="shot" src="{shot_o}" alt="Overview screenshot" style="max-height:2.6in;" />
      <div class="card ink">
        <h3>Illustrative rule-based scores</h3>
        <p>Rep A–D grades and vendor Prefer / Watch / Exit are synthetic, rule-based composites (attainment, margin vs peer, mix, OTIF, quality). They are demo decision aids, not real personnel or supplier recommendations.</p>
      </div>
    </div>
    <div class="grid4">
      <div class="card"><h3>Market</h3><p>Demand outlook, competitor landscape (public-estimate), share expansion, GM lift, growth momentum.</p></div>
      <div class="card"><h3>Margin</h3><p>Margin %, realization, mix waterfall, low-margin SKUs.</p></div>
      <div class="card"><h3>Season &amp; Field</h3><p>Seasonal index, YoY, territories, whitespace, rep grades.</p></div>
      <div class="card"><h3>Supply &amp; Plan</h3><p>Days of cover, reorder, vendor Prefer/Watch/Exit, MRP, forecast accuracy.</p></div>
    </div>
    <p class="fine" style="margin-top:10px;">Analytics subnav includes Market · Core · Margin · Season · Field · Supply · Procurement · Planning. Interview Lab adds board brief, golden evals, Cortex vs governed, RAP-style scope switch, and a 90-day plan.</p>
  </div>
  {foot(4)}
</section>

<!-- 5 Runtime path -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Runtime and access</p>
    <div class="title-row"><div class="bar"></div><h2>Browser → Access → hosted app → SQLite</h2></div>
    <img class="diag" src="{e2e}" alt="Runtime path diagram" />
    <div class="grid3" style="margin-top:10px;">
      <div class="card"><h3>Access gate</h3><p>Cloudflare Access email OTP in front of the hostname. Demo app login is separate (<code>operator</code> / <code>vc-demo</code>).</p></div>
      <div class="card"><h3>Hosted demo</h3><p>Fly.io app <code>vc-retail-analytics</code> (ord) runs Python + tunnel. Observed machine state: started at verification time.</p></div>
      <div class="card"><h3>Session scope</h3><p>HMAC-signed cookie binds dealer or operator role. Dealer sessions cannot request another dealer via query or body.</p></div>
    </div>
  </div>
  {foot(5)}
</section>

<!-- 6 Data model -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Data model and quality</p>
    <div class="title-row"><div class="bar"></div><h2>Sources → silver facts → served metrics</h2></div>
    <img class="diag" src="{arch}" alt="Medallion diagram" style="max-height:3.5in;" />
    <div class="grid3" style="margin-top:10px;">
      <div class="card"><h3>Grain</h3><p>Current silver fact: one row per (dealer_id, sku_id). Monthly series: 24 months for seasonality.</p></div>
      <div class="card"><h3>Quarantine</h3><p>Invalid amounts, unknown channels, and conflicting versions are rejected. Full seed (50 dealers) produced 4 quarantined events in local verification.</p></div>
      <div class="card"><h3>Approved metrics</h3><p>Named SQL templates in <code>METRICS</code>. UI and assistant only expose that closed set.</p></div>
    </div>
  </div>
  {foot(6)}
</section>

<!-- 7 Engineering checks -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Evidence</p>
    <div class="title-row"><div class="bar"></div><h2>Engineering checks and observed results</h2></div>
    <p class="fine">Local checks: <code>{LOCAL_TESTED}</code>, 2026-10-02T20:38Z (re-run PASS). Hosted smoke: <code>{HOSTED_BUILD}</code> image, 2026-10-02T20:45Z, PASS. Details in docs/VC_Submission_Verification.md.</p>
    <table class="data">
      <tr><th>Check</th><th>Observed result</th><th>Evidence</th></tr>
      <tr><td>Unit / API suite</td><td class="pass">PASS</td><td>6/6 tests in <code>tests/test_core.py</code> + <code>tests/test_assistant.py</code></td></tr>
      <tr><td>Dealer isolation</td><td class="pass">PASS</td><td>DLR-0001 session → GET summary?dealer=DLR-0002 returns 403; ask with other dealer denied; portfolio rows only DLR-0001</td></tr>
      <tr><td>Auth failure</td><td class="pass">PASS</td><td>Wrong password → 403</td></tr>
      <tr><td>Metric reconcile</td><td class="pass">PASS</td><td>API summary net/margin matched independent SQL on silver_facts (tolerance $0.02)</td></tr>
      <tr><td>Unsupported forecast</td><td class="pass">PASS</td><td>Local: 400 clarify. Hosted: HTTP 400 (no fabricated rows)</td></tr>
      <tr><td>Quarantine seed</td><td class="pass">PASS</td><td>Full seed quarantined=4 invalid fixture events</td></tr>
      <tr><td>Snowflake parity</td><td class="note">Not run</td><td>Adapter and SQL exist; no reconcile evidence in this pass</td></tr>
      <tr><td>Hosted authenticated walkthrough</td><td class="pass">PASS</td><td>Operator path on vc.datasharkbi.com: Overview, Analytics (5 sections), assistant metric + SQL trace, catalog search, logout</td></tr>
    </table>
  </div>
  {foot(7)}
</section>

<!-- 8 Status -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Implementation status</p>
    <div class="title-row"><div class="bar"></div><h2>What is running vs proposed</h2></div>
    <table class="data">
      <tr><th>Component</th><th>Status</th><th>Notes</th></tr>
      <tr><td>Hosted app + SQLite</td><td class="pass">Running</td><td>Fly machine started; Access OTP gate; authenticated hosted walkthrough PASS (see verification notes)</td></tr>
      <tr><td>Deterministic assistant</td><td class="pass">Implemented + tested</td><td>Exact-match router; SQL trace; forecast refusal tested</td></tr>
      <tr><td>Session dealer scope</td><td class="pass">Implemented + tested</td><td>Server-side scope + isolation tests</td></tr>
      <tr><td>Analytics depth (Market + depth)</td><td class="pass">Implemented</td><td>Market forecast / competitors / GM / growth; margin / season / field / supply / procure / plan</td></tr>
      <tr><td>Interview Lab</td><td class="pass">Implemented</td><td>Board brief, golden evals, Cortex vs governed, operator scope pin, 90-day plan</td></tr>
      <tr><td>Voice on Snowflake</td><td class="pass">Implemented</td><td>Continuous Mic + board/portfolio brief; ElevenLabs; Snowflake-only numbers</td></tr>
      <tr><td>Snowflake adapter / RAP</td><td class="pass">Verified</td><td>Hosted toggle + RAP evidence; Lab scope mirrors dealer pin</td></tr>
      <tr><td>LLM as free-form answerer</td><td class="note">Not the product</td><td>Cortex is discovery/fallback; production answers stay governed</td></tr>
    </table>
    <p class="fine" style="margin-top:12px;">Public support and authenticated dealer analytics serve different needs. This prototype explores how controlled warehouse metrics could support dealer and internal questions alongside familiar FAQ and escalation workflows. It is not an assessment of Visual Comfort internal systems.</p>
  </div>
  {foot(8)}
</section>

<!-- 9 Interview Lab -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">For the AI Engineer conversation</p>
    <div class="title-row"><div class="bar"></div><h2>Interview Lab — what to open with Rahul</h2></div>
    <div class="grid2">
      <div class="card"><h3>1 · Board brief</h3><p>Chains share expansion → GM lift → forecast vs run-rate → growth into one spoken narrative with SQL traces.</p></div>
      <div class="card"><h3>2 · Eval harness</h3><p>20 golden prompts (FAQ · metric · voice fuzzy · refuse). Pass/fail + latency on screen.</p></div>
      <div class="card"><h3>3 · Cortex vs governed</h3><p>Same question side-by-side. Prefer closed metrics; Cortex is discovery/fallback on Snowflake.</p></div>
      <div class="card"><h3>4 · Scope / RAP story</h3><p>As <code>operator</code>, pin DLR-0001 — same ask, fewer rows. App-layer mirror of Snowflake RAP.</p></div>
    </div>
    <div class="card" style="margin-top:10px;">
      <h3>5 · What I'd ship in 90 days</h3>
      <p>Days 1–30 grounding · 31–60 assist + measure · 61–90 harden. Non-goals: inventing order status, replacing phone lanes day one.</p>
    </div>
    <p class="fine" style="margin-top:10px;">Also: Market tab (competitors / GM / growth) and continuous Mic on Assistant. Login: <code>operator</code> / <code>vc-demo</code>.</p>
  </div>
  {foot(9)}
</section>

<!-- 10 Reviewer walkthrough -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Reviewer path</p>
    <div class="title-row"><div class="bar"></div><h2>How to review the hosted demo</h2></div>
    <div class="grid2">
      <div class="card">
        <h3>Access</h3>
        <ul class="clean">
          <li>Open <a class="url" href="{DEMO_URL}">{DEMO_URL.rstrip('/')}</a></li>
          <li>Complete Cloudflare Access email OTP (allowlisted addresses only)</li>
          <li>Demo login: <code>operator</code> / <code>vc-demo</code></li>
          <li>Optional tenancy check: <code>dlr-0001</code> / <code>vc-demo</code></li>
        </ul>
      </div>
      <div class="card">
        <h3>Path to try</h3>
        <ul class="clean">
          <li>Analytics → <strong>Market</strong></li>
          <li><strong>Lab</strong>: board brief → evals → Compare → pin DLR-0001</li>
          <li>Assistant Mic: “show share expansion”</li>
          <li>Refuse check: invent a forecast</li>
        </ul>
      </div>
    </div>
    <div class="card" style="margin-top:12px;">
      <h3>Fallback if Access blocks you</h3>
      <p>Screenshots in this PDF are from the current synthetic build. Source is public at <a class="url" href="{GITHUB_URL}">{GITHUB_URL}</a>. Local run: <code>python3 -m app.server</code> then http://127.0.0.1:8770/login.</p>
    </div>
    <p class="fine" style="margin-top:10px;">Hard-refresh after deploy to pull versioned assets.</p>
  </div>
  {foot(10)}
</section>

<!-- 11 Close -->
<section class="page hero">
  <div class="hero-bg"></div>
  <div class="accent-bar"></div>
  <div class="pad" style="display:flex;flex-direction:column;justify-content:center;max-width:6in;">
    <p class="eyebrow">Close</p>
    <h1>What this prototype demonstrates</h1>
    <p class="lede">Synthetic dealer analytics with approved metrics, session scope, Snowflake toggle, voice, Market/competitor plays, and an Interview Lab for grounding, evals, and a 90-day plan — without inventing warehouse answers.</p>
    <p class="fine" style="color:#c8c0b0;">Limitations: synthetic data; competitor $ are public-estimate calibrated; Access OTP required; capture rates are illustrative.</p>
    <div class="link-row" style="margin-top:16px;">
      <a class="cta" href="{DEMO_URL}">Open hosted demo →</a>
    </div>
    <div class="link-row">
      <a class="url" href="{DEMO_URL}">{DEMO_URL.rstrip('/')}</a>
      <a class="url" href="{GITHUB_URL}">github.com/prendleman/vc-retail-analytics</a>
    </div>
    <p class="fine" style="margin-top:22px;color:#f4efe4;">Paul Rendleman</p>
  </div>
  {foot(11)}
</section>

<!-- A1 Appendix optional Snowflake -->
<section class="page">
  <div class="pad">
    <p class="eyebrow">Appendix A · optional</p>
    <div class="title-row"><div class="bar"></div><h2>Snowflake path (live on hosted toggle)</h2></div>
    <p class="lede">One UI targets SQLite or Snowflake. Hosted demo defaults to SQLite with a header switch. SERVING views, RAP, and Cortex Analyst are demonstrated; competitor metrics use dialect-safe CTE literals.</p>
    <div class="grid3">
      <div class="card"><h3>Present</h3><p>Platform, transform, governance, semantic SQL; dual-backend flag; Lab Cortex compare.</p></div>
      <div class="card"><h3>Evidence</h3><p>docs/evidence RAP dual-principal + Cortex Analyst; hosted health reports cortex + snowflake.</p></div>
      <div class="card"><h3>Honesty</h3><p>Competitor revenues are public-estimate / assumption calibrated — not filed financials.</p></div>
    </div>
  </div>
  {foot(12)}
</section>
<section class="page">
  <div class="pad">
    <p class="eyebrow">Appendix B · optional</p>
    <div class="title-row"><div class="bar"></div><h2>Approved metric vocabulary (excerpt)</h2></div>
    <div class="grid2">
      <div class="card">
        <h3>Market / growth / competitors</h3>
        <ul class="clean">
          <li>demand_outlook, forecast_vs_runrate, growth_momentum, channel_growth</li>
          <li>competitor_landscape, competitive_position, share_expansion, region_expansion</li>
          <li>gm_opportunity_usd, discount_drag, channel_share</li>
        </ul>
      </div>
      <div class="card">
        <h3>Core / margin / season / field</h3>
        <ul class="clean">
          <li>portfolio, by_channel, margin_pct, margin_waterfall, seasonal_index</li>
          <li>territory_perf, whitespace, rep_grade, vendor_scorecard</li>
          <li>stock_risk, reorder_candidates, forecast_accuracy</li>
        </ul>
      </div>
    </div>
    <p class="fine" style="margin-top:14px;">Full definitions live in <code>app/core.py</code> (<code>METRICS</code> / <code>METRIC_PHRASES</code>). Assistant accepts only exact phrases from that map.</p>
  </div>
  {foot(13)}
</section>

</body>
</html>
"""


def main() -> None:
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    html = build_html()
    OUT_HTML.write_text(html, encoding="utf-8")
    print("wrote", OUT_HTML)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(OUT_HTML.resolve().as_uri(), wait_until="networkidle")
        for dest in (OUT_PDF, OUT_PDF_REVISED, OUT_PDF_ALIAS):
            page.pdf(
                path=str(dest),
                landscape=True,
                format="Letter",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                prefer_css_page_size=True,
            )
            print("wrote", dest)
        browser.close()


if __name__ == "__main__":
    main()
