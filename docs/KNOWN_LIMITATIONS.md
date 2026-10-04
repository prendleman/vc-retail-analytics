# Known limitations

- Synthetic dealers/SKUs only; no Visual Comfort production data or credentials.
- Offline assistant is a verified FAQ + metric router, not an LLM.
- Today panel reconstructs the **public support pattern** (FAQ / form / phone). It is not a clone of VC’s third-party chat vendor UI.
- Public URL uses Cloudflare Access (email OTP allowlist). Invite guests with `scripts/cf_access_guests.py`.
- Hard-refresh after Access login if the Analytics UI looks like plain TSV (cached assets).
- Snowflake RAP on PRODUCTS is view-grant only (no dealer key on catalog).
- Staged `scripts.cloud load` is not Openflow.
- Cortex Analyst is demonstrated as a CLI/REST path (`scripts/cortex.py`, evidence `docs/evidence/cortex_analyst.txt`) and as a **voice-ask fallback** when the session is on Snowflake, the closed metric phrase does not match, and `SNOWFLAKE_PAT` + account/host are set. The typed Assistant tab stays a deterministic router by default. Cortex-generated SQL is executed only as a single read-only `SELECT` through the reader store (RAP applies); multi-statement / DML is refused.
- Voice analytics (ElevenLabs): mic / Brief me / header **Voice** → STT → `/api/voice-ask` or `/api/voice-brief` **Snowflake only** (no SQLite fallback; session cookie switched to snowflake). Fuzzy/alias routing onto governed metrics before Cortex. Overview **Brief me** speaks a live portfolio summary. Meters ElevenLabs credits; requires browser mic permission; synthetic voice, not a production VC system. Static `/audio/intro.mp3` is pre-rendered. Hosted demo needs `ELEVENLABS_API_KEY` (and optional `ELEVENLABS_VOICE_ID`) as Fly secrets; without them, typed asks still work and the Voice control stays hidden.
- Default SQLite seed (~50 dealers × 200 SKUs) proves behavior, not enterprise throughput. Scale lives in Snowflake: the "10 TB" is the TPC-DS SF10TCL *scale factor* (56.9B rows; 2.63 TB as Snowflake stores it compressed), shared and zero-copy, not generated VC data. The generated sales-org / procurement / MRP layer is ~1.5 GB.
- Interview **Lab** tab (board brief, golden evals, Cortex vs governed, operator scope switch, 90-day plan) is a conversation aid for the AI Engineer interview — not a production VC control plane.
- Snowflake build verified on one account (AWS us-east-1, Enterprise). RAP is demonstrated on three principals (owner `'*'`, hosted service user `'*'`, and a service user pinned to `DLR-0001`); Openflow ingestion is not demonstrated.
- Hosted toggle: Snowflake is opt-in per browser session (header switch, login required); the default stays SQLite. The first switch resumes the XSMALL warehouse (~4–5 s); it auto-suspends after 60 s idle, so a reviewer who flips, waits, and returns pays that again. One shared reader connection per host; many concurrent Snowflake sessions queue on it.
- On Snowflake, `SILVER.MONTHLY` is dealer × family × channel × month grain, so `silver_monthly.sku_id` is NULL there (dealer × SKU grain lives in `SILVER.FACTS`, trailing 12 months, all 1,500 accounts).
- Corporate supply-chain views (POs, inventory, MRP, BOM, vendors) are not dealer-keyed; dealer sessions see corporate supply data. `vendor_scorecard` on Snowflake ignores dealer scope (Gold is global).
- Snowflake-mode `/api/analytics` runs ~40 governed queries (6-way fan-out); expect 10–30 s on XSMALL, not the sub-second SQLite experience.
- Always-on host is Fly.io + named tunnel; local `share_private.sh` is fallback only.
