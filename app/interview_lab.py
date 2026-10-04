"""Interview Lab pack — board brief, evals, Cortex compare, scope demo, 90-day plan.

Synthetic demo aids for the Visual Comfort AI Engineer conversation. Not production
VC systems. Numbers always come from governed metric SQL (or Cortex SELECT when shown).
"""
from __future__ import annotations

import time
from typing import Any, Callable

from app.core import METRICS, interpret_metric, match_faq, metric_sql, resolve_metric
from app import voice as voice_mod

# Chained board narrative: take share → fund with GM → demand call → momentum
BOARD_CHAIN = (
    "share_expansion",
    "gm_opportunity_usd",
    "forecast_vs_runrate",
    "growth_momentum",
)


def speakable_board_brief(sections: list[dict]) -> str:
    """~40s spoken board narrative from live chained metrics."""
    parts = [
        "Board brief from governed warehouse metrics.",
    ]
    by = {s["metric"]: s for s in sections}
    if "share_expansion" in by and by["share_expansion"]["rows"]:
        r = by["share_expansion"]["rows"][0]
        parts.append(
            voice_mod.speakable_metric("share_expansion", by["share_expansion"]["rows"])
        )
    if "gm_opportunity_usd" in by and by["gm_opportunity_usd"]["rows"]:
        parts.append(
            voice_mod.speakable_metric("gm_opportunity_usd", by["gm_opportunity_usd"]["rows"])
        )
    if "forecast_vs_runrate" in by and by["forecast_vs_runrate"]["rows"]:
        parts.append(
            voice_mod.speakable_metric("forecast_vs_runrate", by["forecast_vs_runrate"]["rows"])
        )
    if "growth_momentum" in by and by["growth_momentum"]["rows"]:
        parts.append(
            voice_mod.speakable_metric("growth_momentum", by["growth_momentum"]["rows"])
        )
    parts.append(
        "Recommendation: prioritize the top share-expansion play, fund it by closing half the "
        "gross-margin gap on the weakest family, and align buy-ahead to the forecast-versus-run-rate signal."
    )
    return " ".join(parts)


def run_board_brief(store, dealer=None) -> dict:
    """Execute the board chain and return speakable + per-metric rows/SQL."""
    sections = []
    errors = []
    t0 = time.perf_counter()
    for name in BOARD_CHAIN:
        try:
            sql, params = metric_sql(name, dealer, store.dialect)
            rows = store.metric_rows(name, dealer)
            sections.append(
                {
                    "metric": name,
                    "description": METRICS[name]["description"],
                    "sql": sql,
                    "parameters": params,
                    "rows": rows[:12],
                    "row_count": len(rows),
                }
            )
        except Exception as e:  # noqa: BLE001
            errors.append({"metric": name, "error": f"{type(e).__name__}: {e}"})
    if not sections:
        raise RuntimeError("Board brief failed: " + "; ".join(e["error"] for e in errors))
    spoken = speakable_board_brief(sections)
    return {
        "kind": "board_brief",
        "mode": "chained governed metrics",
        "spoken": spoken,
        "sections": sections,
        "errors": errors,
        "trace": ["board_brief", *[s["metric"] for s in sections], "speakable_board_brief"],
        "backend": getattr(store, "backend", "local"),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


# --- Eval harness -----------------------------------------------------------

EVAL_CASES: list[dict[str, Any]] = [
    # FAQ
    {"id": "faq_custom", "lane": "faq", "question": "custom order lead time", "expect_kind": "faq", "expect_source": "custom_lead"},
    {"id": "faq_open_box", "lane": "faq", "question": "what is open box", "expect_kind": "faq", "expect_source": "open_box"},
    # Governed exact
    {"id": "metric_margin", "lane": "metric", "question": "show margin percent", "expect_kind": "metric", "expect_metric": "margin_pct"},
    {"id": "metric_portfolio", "lane": "metric", "question": "show portfolio", "expect_kind": "metric", "expect_metric": "portfolio"},
    {"id": "metric_share_exp", "lane": "metric", "question": "show share expansion", "expect_kind": "metric", "expect_metric": "share_expansion"},
    {"id": "metric_gm", "lane": "metric", "question": "show gm opportunity", "expect_kind": "metric", "expect_metric": "gm_opportunity_usd"},
    {"id": "metric_competitors", "lane": "metric", "question": "show competitor landscape", "expect_kind": "metric", "expect_metric": "competitor_landscape"},
    {"id": "metric_forecast", "lane": "metric", "question": "show demand outlook", "expect_kind": "metric", "expect_metric": "demand_outlook"},
    # Voice fuzzy → same metrics
    {"id": "fuzzy_gm", "lane": "voice", "question": "move the needle on gross margin", "expect_kind": "metric", "expect_metric": "gm_opportunity_usd", "resolver": "resolve"},
    {"id": "fuzzy_share", "lane": "voice", "question": "where can we win competitor share", "expect_kind": "metric", "expect_metric": "share_expansion", "resolver": "resolve"},
    {"id": "fuzzy_growth", "lane": "voice", "question": "are we accelerating growth", "expect_kind": "metric", "expect_metric": "growth_momentum", "resolver": "resolve"},
    {"id": "fuzzy_channel", "lane": "voice", "question": "sales by channel please", "expect_kind": "metric", "expect_metric": "by_channel", "resolver": "resolve"},
    # Refuse / clarify unknown metric
    {"id": "refuse_order", "lane": "refuse", "question": "where is my order 12345", "expect_kind": "clarify"},
    {"id": "refuse_invent", "lane": "refuse", "question": "invent next quarter EBITDA for Visual Comfort", "expect_kind": "clarify"},
    # Escalate-ish / no warehouse
    {"id": "faq_contact", "lane": "faq", "question": "who do I contact", "expect_kind": "faq", "expect_source": "channels"},
    {"id": "metric_stock", "lane": "metric", "question": "show stock risk", "expect_kind": "metric", "expect_metric": "stock_risk"},
    {"id": "metric_vendor", "lane": "metric", "question": "show vendor scorecard", "expect_kind": "metric", "expect_metric": "vendor_scorecard"},
    {"id": "fuzzy_season", "lane": "voice", "question": "what's our seasonality", "expect_kind": "metric", "expect_metric": "seasonal_index", "resolver": "resolve"},
    {"id": "metric_outlook_gap", "lane": "metric", "question": "show forecast vs runrate", "expect_kind": "metric", "expect_metric": "forecast_vs_runrate"},
    {"id": "fuzzy_competitors", "lane": "voice", "question": "who are our competitors", "expect_kind": "metric", "expect_metric": "competitor_landscape", "resolver": "resolve"},
]


def _run_one_eval(store, case: dict, dealer=None) -> dict:
    t0 = time.perf_counter()
    q = case["question"]
    expect_kind = case["expect_kind"]
    ok = False
    detail: dict[str, Any] = {"question": q, "expect_kind": expect_kind}
    try:
        if expect_kind == "faq":
            faq = match_faq(q)
            got = "faq" if faq else "miss"
            detail["got_kind"] = got
            detail["got_source"] = (faq or {}).get("id")
            ok = bool(faq) and (
                not case.get("expect_source") or faq.get("id") == case["expect_source"]
            )
        elif expect_kind == "metric":
            if case.get("resolver") == "resolve":
                name = resolve_metric(q)
            else:
                name = interpret_metric(q)
            detail["got_kind"] = "metric"
            detail["got_metric"] = name
            ok = name == case.get("expect_metric")
            if ok:
                # Prove SQL executes
                rows = store.metric_rows(name, dealer)
                detail["rows"] = len(rows)
                ok = len(rows) >= 0  # empty still passes routing; note it
                detail["empty"] = len(rows) == 0
        elif expect_kind == "clarify":
            # Must NOT resolve to a metric and must NOT be a clean FAQ hit for warehouse invent
            faq = match_faq(q)
            try:
                resolve_metric(q)
                routed = True
            except ValueError:
                routed = False
            try:
                interpret_metric(q)
                exact = True
            except ValueError:
                exact = False
            detail["got_kind"] = "clarify" if (not routed and not exact) else "leaked"
            detail["faq_hit"] = bool(faq)
            # Order status should escalate / clarify — FAQ may not match; invent must not route
            ok = not routed and not exact
        else:
            detail["error"] = f"unknown expect_kind {expect_kind}"
            ok = False
    except Exception as e:  # noqa: BLE001
        detail["error"] = f"{type(e).__name__}: {e}"
        ok = False
    detail["ok"] = ok
    detail["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    detail["id"] = case["id"]
    detail["lane"] = case.get("lane")
    return detail


def run_evals(store, dealer=None, case_ids: list[str] | None = None) -> dict:
    cases = EVAL_CASES
    if case_ids:
        want = set(case_ids)
        cases = [c for c in cases if c["id"] in want]
    t0 = time.perf_counter()
    results = [_run_one_eval(store, c, dealer) for c in cases]
    passed = sum(1 for r in results if r["ok"])
    return {
        "kind": "eval_report",
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_pct": round(100.0 * passed / len(results), 1) if results else 0.0,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "backend": getattr(store, "backend", "local"),
        "results": results,
        "note": "Golden prompts for the offline assistant + voice resolver. Not an LLM eval.",
    }


# --- Cortex vs governed -----------------------------------------------------

def compare_governed_cortex(store, question: str, dealer=None) -> dict:
    """Side-by-side: closed metric path vs Cortex Analyst (when configured)."""
    q = (question or "").strip()
    if not q:
        raise ValueError("question required")
    out: dict[str, Any] = {
        "kind": "compare",
        "question": q,
        "backend": getattr(store, "backend", "local"),
        "governed": None,
        "cortex": None,
        "delta_note": "",
    }
    t0 = time.perf_counter()
    try:
        name = resolve_metric(q)
        sql, params = metric_sql(name, dealer, store.dialect)
        rows = store.metric_rows(name, dealer)
        out["governed"] = {
            "ok": True,
            "metric": name,
            "description": METRICS[name]["description"],
            "sql": sql,
            "parameters": params,
            "rows": rows[:8],
            "row_count": len(rows),
            "spoken": voice_mod.speakable_metric(name, rows, METRICS[name]["description"]),
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "trace": ["resolve_metric", "metric_sql", "execute"],
        }
    except ValueError as e:
        out["governed"] = {
            "ok": False,
            "error": str(e),
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "trace": ["resolve_metric_miss"],
        }

    t1 = time.perf_counter()
    if getattr(store, "backend", "") != "snowflake":
        out["cortex"] = {
            "ok": False,
            "error": "Cortex compare needs a Snowflake session (header Data → Snowflake).",
            "elapsed_ms": 0,
        }
    elif not voice_mod.cortex_configured():
        out["cortex"] = {
            "ok": False,
            "error": "Cortex Analyst is not configured on this host (SNOWFLAKE_PAT / account).",
            "elapsed_ms": 0,
        }
    else:
        try:
            gen = voice_mod.cortex_generate_sql(q)
            sql = gen.get("sql")
            if not sql:
                out["cortex"] = {
                    "ok": False,
                    "error": gen.get("text") or "Cortex returned no SQL",
                    "suggestions": gen.get("suggestions") or [],
                    "elapsed_ms": round((time.perf_counter() - t1) * 1000, 1),
                    "trace": ["cortex_analyst", "no_sql"],
                }
            else:
                rows = voice_mod.execute_cortex_select(store, sql)
                out["cortex"] = {
                    "ok": True,
                    "sql": sql,
                    "answer": gen.get("text"),
                    "rows": rows[:8],
                    "row_count": len(rows),
                    "spoken": voice_mod.speakable_cortex(q, rows, sql),
                    "elapsed_ms": round((time.perf_counter() - t1) * 1000, 1),
                    "trace": ["cortex_analyst", "execute_select"],
                }
        except Exception as e:  # noqa: BLE001
            out["cortex"] = {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "elapsed_ms": round((time.perf_counter() - t1) * 1000, 1),
                "trace": ["cortex_failed"],
            }

    g_ok = bool(out["governed"] and out["governed"].get("ok"))
    c_ok = bool(out["cortex"] and out["cortex"].get("ok"))
    if g_ok and c_ok:
        out["delta_note"] = (
            "Both paths returned rows. Prefer the governed metric for production answers "
            "(closed vocabulary + audited SQL). Cortex is a discovery/fallback lane — "
            "read-only SELECT only, RAP still applies on Snowflake."
        )
    elif g_ok and not c_ok:
        out["delta_note"] = (
            "Governed metric hit; Cortex unavailable or refused. This is the safe default for dealer chat."
        )
    elif not g_ok and c_ok:
        out["delta_note"] = (
            "No closed metric matched — Cortex proposed SQL. Review before promoting into the metric registry."
        )
    else:
        out["delta_note"] = "Neither path answered — clarify or escalate to a human lane."
    return out


# --- 90-day plan ------------------------------------------------------------

PLAN_90_DAYS = {
    "title": "What I'd ship in 90 days",
    "subtitle": "Grounded retail AI for Visual Comfort — interview plan, not a commitment",
    "audience": "AI Engineer III conversation",
    "phases": [
        {
            "days": "Days 1–30",
            "theme": "Grounding layer",
            "bullets": [
                "Inventory every dealer/internal question class: FAQ, catalog, metric, refuse, escalate",
                "Stand up a closed metric registry over Silver/Gold (this demo's pattern) with RAP on dealer grain",
                "Ship an offline router + tool traces before any free-form LLM answers numbers",
                "Golden eval set (≥50 prompts) in CI: routing accuracy, refuse rate, SQL allow-list",
            ],
        },
        {
            "days": "Days 31–60",
            "theme": "Assist + measure",
            "bullets": [
                "Wire Cortex Analyst (or equivalent) as a *discovery* lane only — promote winners into governed metrics",
                "Human escalation packet with lane, dealer scope, last SQL, and confidence",
                "Latency + cost dashboards; kill-switch for generative paths",
                "Voice/STT optional for field — same metric tools, no separate brain",
            ],
        },
        {
            "days": "Days 61–90",
            "theme": "Hardening",
            "bullets": [
                "RAP dual-principal proof in every env (operator * vs dealer pin)",
                "Prompt-injection + metric-exfiltration tests; PII redaction on transcripts",
                "Shadow mode vs current FAQ/chat; publish win/loss on warehouse questions only",
                "Hand off runbooks: how to add a metric, how to retire a bad Cortex suggestion",
            ],
        },
    ],
    "non_goals": [
        "Not replacing Trade/Consumer phone lanes on day one",
        "Not inventing live order status from an LLM",
        "Not training on production chat without legal + eval gates",
    ],
    "demo_map": [
        "Lab → Board brief = multi-tool grounding",
        "Lab → Evals = measurement culture",
        "Lab → Cortex vs governed = discovery vs production",
        "Lab → Scope = RAP/session isolation story",
        "Assistant Mic = same tools, spoken UX",
    ],
}


def plan_90() -> dict:
    return {"kind": "plan_90", **PLAN_90_DAYS}
