# Cursor start here — VC Retail Analytics

Build and finish this independent synthetic interview demonstration for the **Visual Comfort AI Engineer III** opportunity. Work in this project. Preserve the executable local baseline while making the optional Snowflake path work.

Read README.md, docs/CLIENT.md, docs/ARCHITECTURE.md, docs/SNOWFLAKE.md, docs/CHATBOT_GAP.md first.

1. **Verify baseline.** `python3 -m unittest discover -s tests -v`. Start `python3 -m app.server`, exercise Overview / Analytics / Assistant / Catalog.
2. **Label honesty.** Every number from a query. Never call the offline assistant an LLM. Never claim Snowflake/Cortex is live until observed. Synthetic banner always visible.
3. **Snowflake (optional).** Isolated database `VC_RETAIL_DEMO` only. Reuse AQ profiles; never print secrets. Follow docs/SNOWFLAKE.md ordered setup.
4. **Chatbot story.** Today panel documents observed VC support surface; Proposed panel runs live governed tools over demo data.
5. **Demo pack.** Walk docs/DEMO_SCRIPT.md in under 10 minutes.

Acceptance: local tests pass, browser flows work, metrics reconcile, secrets absent from git, cloud claims have live evidence.
