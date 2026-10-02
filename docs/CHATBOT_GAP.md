# Chatbot gap: Visual Comfort site support vs Proposed demo assistant

## What we observed (2026-10-02)

Public site [visualcomfort.com](https://www.visualcomfort.com/):

| Surface | Observation |
|---------|-------------|
| Contact | [/contact/](https://www.visualcomfort.com/contact/) form + phone/email lanes: B2B Partners, Consumer\|Trade, Contract\|Hospitality |
| FAQ | Rich static answers (shipping, custom lead times, Open Box, finishes, UL/ADA, care) |
| Live chat | Privacy policy states a **third-party chat platform** collects chat + navigation data. Automated browser session did not surface a reliable widget (cookie/geo gating possible). Treat as **human/chat CS**, not a warehouse-grounded product advisor. |
| SEO/content AI | Public case study exists for automated category-page SEO agents (Similar.ai) — different problem than conversational retail intelligence. |

This document is an **observation**, not a reverse-engineering of a proprietary bot.

## Gap matrix

| Capability | Today (site pattern) | Proposed (this demo) |
|------------|----------------------|----------------------|
| Order / policy FAQ | Static FAQ + escalate to form/phone | Grounded FAQ store with source ids |
| Product discovery | Browse / search site | Synthetic catalog attribute lookup |
| Sell-through / margin | Not available in chat | Verified `/api/metric` tools + SQL/params in trace |
| Stock risk | Not available | `stock_risk` governed metric |
| Channel awareness | Separate phone lanes | Session dealer scope + channel metrics; escalate packet names lane |
| Hallucination control | Human judgment | Offline closed vocabulary; refuse unknown metrics |
| Escalation | Form / phone | Structured JSON handoff packet (demo only) |
| Analytics grounding | None | Bronze → Silver → Gold lineage exposed in catalog |

## Honest demo claim

> Current site support is human/form/chat for order and product FAQs. The Proposed assistant answers product policy from a synthetic catalog+FAQ store, answers retail questions from warehouse metrics with SQL/tool traces, and escalates with a structured handoff — it does not invent inventory, margin, or live order status.

## Eval prompts for the Assistant tab

**Today column**

1. `custom order lead time`
2. `what is open box`
3. `where is my order 12345` → expect escalate stub

**Proposed column**

1. `show sales by channel`
2. `show stock risk`
3. `alabaster` → catalog hits
4. `invent next quarter forecast` → clarify / refuse
