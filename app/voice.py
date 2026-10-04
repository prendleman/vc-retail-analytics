"""ElevenLabs STT/TTS + speakable warehouse briefs for the voice analytics path.

Key is read from ELEVENLABS_API_KEY (env) or Interview-Cockpit/.env — never logged or committed.
Default voice: Sarah (premium female, mature/reassuring) unless ELEVENLABS_VOICE_ID is set.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COCKPIT_ENV = Path("/Users/paulrendleman/Documents/Interview-Cockpit/.env")

# Sarah — Mature, Reassuring, Confident (ElevenLabs premade)
DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
TTS_URL_TMPL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
VOICES_URL = "https://api.elevenlabs.io/v1/voices"
TTS_MAX_CHARS = 700
CORTEX_ROW_CAP = 12


def _read_env_value(path: Path, name: str) -> str:
    if not path.is_file():
        return ""
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def load_api_key() -> str:
    return (
        (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
        or _read_env_value(ROOT / ".env", "ELEVENLABS_API_KEY")
        or _read_env_value(COCKPIT_ENV, "ELEVENLABS_API_KEY")
    )


def voice_id() -> str:
    return (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip() or DEFAULT_VOICE_ID


def configured() -> bool:
    return bool(load_api_key())


def cortex_configured() -> bool:
    host = os.environ.get("SNOWFLAKE_HOST") or (
        f"{os.environ['SNOWFLAKE_ACCOUNT']}.snowflakecomputing.com"
        if os.environ.get("SNOWFLAKE_ACCOUNT")
        else None
    )
    return bool(host and os.environ.get("SNOWFLAKE_PAT"))


def _money(n: Any) -> str:
    try:
        x = float(n)
    except (TypeError, ValueError):
        return "—"
    absx = abs(x)
    if absx >= 1e9:
        return f"${x / 1e9:.1f} billion"
    if absx >= 1e6:
        return f"${x / 1e6:.1f} million"
    if absx >= 1e3:
        return f"${x:,.0f}"
    return f"${x:,.0f}"


def _pct(n: Any) -> str:
    try:
        return f"{float(n):.1f} percent"
    except (TypeError, ValueError):
        return "—"


def _num(n: Any) -> str:
    try:
        x = float(n)
    except (TypeError, ValueError):
        return "—"
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    return f"{x:,.1f}"


def speakable_portfolio_brief(summary: dict, channels: list[dict], stock_risk: list[dict] | None = None) -> str:
    """~20s Overview brief from live summary + channel mix (+ optional stock risk)."""
    dealers = summary.get("dealers")
    skus = summary.get("skus")
    units = summary.get("units_sold")
    net = summary.get("net_sales")
    margin = summary.get("margin")
    try:
        margin_pct = 100.0 * float(margin) / float(net) if net not in (None, 0, "0") else None
    except (TypeError, ValueError, ZeroDivisionError):
        margin_pct = None
    parts = [
        f"Portfolio brief: {_num(dealers)} accounts, {_num(skus)} active SKUs, "
        f"{_num(units)} units sold for {_money(net)} net sales"
    ]
    if margin_pct is not None:
        parts[0] += f" at {_pct(margin_pct)} gross margin"
    parts[0] += "."
    if channels:
        ordered = sorted(channels, key=lambda r: float(r.get("net_sales") or 0), reverse=True)
        mix = "; ".join(
            f"{r.get('channel')} {_money(r.get('net_sales'))}"
            + (f", margin {_pct(r.get('margin_pct'))}" if r.get("margin_pct") is not None else "")
            for r in ordered[:3]
        )
        parts.append(f"Channel mix: {mix}.")
    if stock_risk:
        top = stock_risk[0]
        label = top.get("sku_id") or top.get("family") or top.get("name") or "top SKU"
        parts.append(
            f"Stock risk flag: {label} with sell-through pressure "
            f"({_num(top.get('units_sold') or top.get('skus') or len(stock_risk))} in the risk set)."
        )
    else:
        parts.append("No stock-risk SKUs in the top slice for this scope.")
    return " ".join(parts)


def speakable_metric(name: str, rows: list[dict], description: str = "") -> str:
    """1–3 spoken sentences from live metric rows (warehouse numbers, not canned copy)."""
    if not rows:
        return f"The governed metric {name.replace('_', ' ')} returned no rows for this scope."
    r0 = rows[0]

    if name == "margin_pct":
        bits = [f"{r.get('channel')} at {_pct(r.get('margin_pct'))}" for r in rows[:3] if r.get("channel") is not None]
        return "Gross margin by channel: " + "; ".join(bits) + "."

    if name in ("by_channel", "by_family", "by_region"):
        label = {"by_channel": "channel", "by_family": "family", "by_region": "region"}[name]
        key = label if label != "region" else "region"
        # rows may use channel/family/region or territory
        label_key = next((k for k in (key, "channel", "family", "region", "territory") if k in r0), None)
        parts = []
        for r in rows[:3]:
            lab = r.get(label_key) if label_key else next(iter(r.values()), "?")
            parts.append(f"{lab} {_money(r.get('net_sales'))}")
        total = sum(float(r.get("net_sales") or 0) for r in rows)
        return f"Net sales by {label.replace('_', ' ')}: " + "; ".join(parts) + f". Across the result set, {_money(total)}."

    if name == "portfolio":
        top = r0.get("dealer_id") or r0.get("name") or "top dealer"
        return (
            f"Portfolio leads with {top} at {_money(r0.get('net_sales'))} net sales, "
            f"{_num(r0.get('units_sold'))} units, {_money(r0.get('margin'))} margin. "
            f"{len(rows)} dealers in this slice."
        )

    if name == "vendor_scorecard" and r0.get("name"):
        return (
            f"Vendor scorecard: {r0.get('name')} is tier {r0.get('tier')} "
            f"with score {_num(r0.get('score'))}. Showing {len(rows)} vendors."
        )

    if name == "rep_grade" and r0.get("rep"):
        return (
            f"Top rep grade: {r0.get('rep')} is grade {r0.get('grade')} "
            f"with attainment {_pct(r0.get('attainment_pct'))}."
        )

    if name == "po_past_due" and r0.get("vendor"):
        return (
            f"Past-due POs: {r0.get('vendor')} leads with {_money(r0.get('past_due_value'))} "
            f"across {_num(r0.get('past_due_lines'))} lines."
        )

    if name == "vendor_otif_detail" and r0.get("vendor"):
        return (
            f"Vendor OTIF: {r0.get('vendor')} at {_pct(r0.get('otif_pct'))} "
            f"versus target {_pct(r0.get('target_pct'))}."
        )

    if name == "dc_inventory_health" and r0.get("dc"):
        return (
            f"DC inventory: {r0.get('dc')} has {_num(r0.get('available'))} available "
            f"of {_num(r0.get('on_hand'))} on hand."
        )

    if name == "mrp_exceptions" and r0.get("exception_code"):
        return (
            f"Largest MRP exception bucket is {r0.get('exception_code')} at {r0.get('dc')} "
            f"covering {_num(r0.get('skus'))} SKUs."
        )

    if name == "demand_outlook" and r0.get("family"):
        months = sorted({str(r.get("month")) for r in rows if r.get("month")})
        top = rows[0]
        return (
            f"Demand outlook for {', '.join(months[:3])}: {top.get('family')} leads at "
            f"{_num(top.get('forecast_units'))} forecast units. {len(rows)} family-month rows."
        )

    if name == "forecast_vs_runrate" and r0.get("family"):
        return (
            f"Forecast versus run-rate: {r0.get('family')} is {_pct(r0.get('outlook_gap_pct'))} "
            f"vs trailing three months — signal {r0.get('signal')}."
        )

    if name == "share_opportunity" and r0.get("name"):
        return (
            f"Largest share gap: {r0.get('name')} is {_money(r0.get('share_gap_usd'))} below "
            f"region peer average at {_pct(r0.get('of_peer_pct'))} of peer."
        )

    if name == "gm_opportunity_usd" and r0.get("family"):
        lift = next((r for r in rows if (r.get("gm_lift_usd") or 0) > 0), r0)
        return (
            f"Gross-margin opportunity: closing half the gap on {lift.get('family')} "
            f"is about {_money(lift.get('gm_lift_usd'))} of lift."
        )

    if name == "growth_momentum" and r0.get("family"):
        return (
            f"Growth momentum: {r0.get('family')} is {_pct(r0.get('momentum_pct'))} "
            f"trailing six versus prior six — {r0.get('accel_flag')}."
        )

    if name == "channel_share" and r0.get("channel"):
        bits = [f"{r.get('channel')} {_pct(r.get('share_pct'))}" for r in rows[:3]]
        return "Channel share of net sales: " + "; ".join(bits) + "."

    if name == "discount_drag" and r0.get("family"):
        return (
            f"Discount drag: {r0.get('family')} leaves {_money(r0.get('discount_drag_usd'))} "
            f"on the table versus list at realization {_num(r0.get('realization'))}."
        )

    if name == "competitor_landscape" and r0.get("name"):
        peers = [r for r in rows if not r.get("is_us")][:2]
        bits = [f"{p.get('name')} {_pct(p.get('share_pct'))}" for p in peers]
        us = next((r for r in rows if r.get("is_us")), r0)
        return (
            f"Decorative set: we are modeled at {_pct(us.get('share_pct'))}. "
            f"Named peers include " + "; ".join(bits) + "."
        )

    if name == "share_expansion" and r0.get("competitor"):
        return (
            f"Top share-expansion play: {r0.get('family')} versus {r0.get('competitor')} "
            f"for about {_num(r0.get('expansion_m'))} million dollars at an eight percent capture rate — {r0.get('play')}."
        )

    if name == "competitive_position" and r0.get("name"):
        return (
            f"Competitive position: {r0.get('name')} at about {_num(r0.get('revenue_m'))} million dollars "
            f"estimated revenue, {_pct(r0.get('share_pct'))} of the synthetic set."
        )

    # Generic: mention first numeric-looking fields
    keys = [k for k in r0.keys() if k not in ("sql",)][:4]
    bits = []
    for k in keys:
        v = r0.get(k)
        if v is None:
            continue
        lk = k.lower()
        if any(x in lk for x in ("sales", "margin", "value", "spend", "quota")) and "pct" not in lk:
            bits.append(f"{k.replace('_', ' ')} {_money(v)}")
        elif "pct" in lk or "otif" in lk or "attainment" in lk:
            bits.append(f"{k.replace('_', ' ')} {_pct(v)}")
        else:
            bits.append(f"{k.replace('_', ' ')} {v}")
        if len(bits) >= 3:
            break
    head = description or name.replace("_", " ")
    return f"From {head}: " + "; ".join(bits) + f". {len(rows)} rows returned."


def speakable_cortex(question: str, rows: list[dict], sql: str = "") -> str:
    if not rows:
        return f"Cortex Analyst returned SQL for “{question}”, but the query produced no rows in this scope."
    cols = list(rows[0].keys())
    preview = rows[: min(3, len(rows))]
    parts = []
    for r in preview:
        cell = []
        for c in cols[:4]:
            v = r.get(c)
            lc = c.lower()
            if any(x in lc for x in ("sales", "margin", "value", "amount", "spend")) and "pct" not in lc:
                cell.append(f"{c.replace('_', ' ')} {_money(v)}")
            elif "pct" in lc:
                cell.append(f"{c.replace('_', ' ')} {_pct(v)}")
            else:
                cell.append(f"{c.replace('_', ' ')} {v}")
        parts.append(", ".join(cell))
    return (
        f"From the warehouse for “{question}”: "
        + ". ".join(parts)
        + f". {len(rows)} rows in the result."
    )


def synthesize(text: str) -> bytes:
    key = load_api_key()
    if not key:
        raise RuntimeError("ElevenLabs API key not configured")
    clean = " ".join((text or "").split())
    if not clean:
        raise ValueError("Nothing to speak")
    if len(clean) > TTS_MAX_CHARS:
        clean = clean[: TTS_MAX_CHARS - 1].rsplit(" ", 1)[0] + "…"
    body = json.dumps(
        {
            "text": clean,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "speed": 0.85,
                "use_speaker_boost": True,
            },
        }
    ).encode()
    req = urllib.request.Request(
        TTS_URL_TMPL.format(voice_id=voice_id()),
        data=body,
        headers={
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"TTS failed ({e.code})") from e


def transcribe(audio_bytes: bytes, filename: str = "clip.webm", content_type: str = "audio/webm") -> str:
    key = load_api_key()
    if not key:
        raise RuntimeError("ElevenLabs API key not configured")
    if not audio_bytes or len(audio_bytes) < 200:
        return ""
    # multipart/form-data without requests
    boundary = "----VCVoiceBoundary7MA4YWxkTrZu0gW"
    parts = []

    def add_field(name: str, value: str):
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )

    add_field("model_id", "scribe_v2")
    add_field("language_code", "en")
    add_field("tag_audio_events", "false")
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        + audio_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        STT_URL,
        data=body,
        headers={
            "xi-api-key": key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"STT failed ({e.code})") from e
    return (data.get("text") or "").strip()


def cortex_generate_sql(question: str, semantic_view: str = "VC_RETAIL_DEMO.SERVING.VC_RETAIL_SEMANTICS") -> dict:
    """Call Cortex Analyst; return {text, sql, suggestions} — does not execute."""
    host = os.environ.get("SNOWFLAKE_HOST") or (
        f"{os.environ['SNOWFLAKE_ACCOUNT']}.snowflakecomputing.com"
        if os.environ.get("SNOWFLAKE_ACCOUNT")
        else None
    )
    pat = os.environ.get("SNOWFLAKE_PAT")
    if not host or not pat:
        raise RuntimeError("Cortex requires SNOWFLAKE_PAT and SNOWFLAKE_ACCOUNT (or SNOWFLAKE_HOST)")
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "semantic_view": semantic_view,
    }
    req = urllib.request.Request(
        f"https://{host}/api/v2/cortex/analyst/message",
        data=json.dumps(payload).encode(),
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
        raise RuntimeError(f"Cortex Analyst failed ({e.code})") from e
    text_parts, sql, suggestions = [], None, []
    for part in data.get("message", {}).get("content", []):
        kind = part.get("type")
        if kind == "text":
            text_parts.append((part.get("text") or "").strip())
        elif kind == "sql":
            sql = (part.get("statement") or "").strip()
        elif kind == "suggestions":
            suggestions = part.get("suggestions") or []
    return {"text": "\n".join(t for t in text_parts if t), "sql": sql, "suggestions": suggestions, "raw": data}


_SELECT_OK = re.compile(r"^\s*(with\b[\s\S]+)?select\b", re.I)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|call|execute|put|remove|copy)\b",
    re.I,
)


def safe_select_sql(sql: str) -> str:
    """Allow a single SELECT / WITH…SELECT only."""
    if not sql or not sql.strip():
        raise ValueError("No SQL from Cortex Analyst")
    # strip trailing semicolons; reject multi-statement
    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        raise ValueError("Refusing multi-statement Cortex SQL")
    if not _SELECT_OK.search(cleaned):
        raise ValueError("Cortex SQL is not a SELECT")
    if _FORBIDDEN.search(cleaned):
        raise ValueError("Cortex SQL contains a non-read statement")
    return cleaned


def execute_cortex_select(store, sql: str) -> list[dict]:
    safe = safe_select_sql(sql)
    # Cap via wrapper when possible — Snowflake/SQLite both accept subquery
    wrapped = f"SELECT * FROM ({safe}) AS cortex_q LIMIT {CORTEX_ROW_CAP}"
    try:
        return store.rows(wrapped, [])
    except Exception:
        # Some dialects dislike wrapping; try bare SELECT with trust in LIMIT already present
        return store.rows(safe, [])[:CORTEX_ROW_CAP]
