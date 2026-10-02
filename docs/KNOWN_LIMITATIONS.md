# Known limitations

- Synthetic dealers/SKUs only; no Visual Comfort production data or credentials.
- Offline assistant is a verified FAQ + metric router, not an LLM.
- Today panel reconstructs the **public support pattern** (FAQ / form / phone). It is not a clone of VC’s third-party chat vendor UI.
- Public URL uses Cloudflare Access (email OTP allowlist). Invite guests with `scripts/cf_access_guests.py`.
- Hard-refresh after Access login if the Analytics UI looks like plain TSV (cached assets).
- Snowflake RAP on PRODUCTS is view-grant only (no dealer key on catalog).
- Staged `scripts.cloud load` is not Openflow.
- Cortex path requires account features + PAT; untested until live evidence is captured under `docs/evidence/`.
- Default seed (~50 dealers × 200 SKUs) proves behavior, not enterprise throughput.
- Always-on host is Fly.io + named tunnel; local `share_private.sh` is fallback only.
