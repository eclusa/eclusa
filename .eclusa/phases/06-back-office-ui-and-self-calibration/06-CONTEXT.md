# Phase 6: Back Office UI and Self-Calibration - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

React SPA back office for operators: active cascades dashboard, pending gates with resolution controls, session transcript viewer, cost dashboard, ledger AS OF explorer, knowledge graph browser, and all 8 self-calibration metrics. Full docker-compose bootstrap (db + executor + proxy + web + email adapter + UI). The UI is internal/operator-facing, not end-user-facing.

</domain>

<decisions>
## Implementation Decisions

### UI framework and aesthetics
- **D-01:** React 19 + Vite 6 + shadcn/ui + Tailwind CSS 4 — locked by CLAUDE.md
- **D-02:** MercuryOS-like minimal aesthetic — clean, not cluttered, ambient information density
- **D-03:** TanStack Query 5 for all server state, Zustand 5 for local UI state (selected cascade, open panels)
- **D-04:** React Router 6 for SPA routing, no SSR needed

### Agent interaction surface (LOAD-BEARING DECISION)
- **D-05:** Research must evaluate Open WebUI, Vercel AI SDK, and similar frameworks for the agent interaction parts (session transcripts, gate resolution, potentially live session steering)
- **D-06:** Forking an existing framework may be better than building from scratch or trying to iframe it — the framework MUST share the same frontend stack (React + Vite) or be adaptable to it
- **D-07:** The agent interaction surface is not a chat widget — it's the back office view of work sessions, judgment passes, and gate contexts. It needs structured data display, not just message bubbles
- **D-08:** Research should compare: (a) build custom with shadcn/ui components, (b) fork Open WebUI's React frontend, (c) use Vercel AI SDK's useChat/useCompletion hooks with custom UI, (d) other relevant frameworks
- **D-09:** The chosen approach must support: real-time transcript streaming (WebSocket), structured verdict display (not just text), gate resolution controls inline with context, cost attribution per message

### API layer
- **D-10:** FastAPI REST endpoints extending the Phase 5 app (adapters/web/)
- **D-11:** WebSocket endpoint for live cascade updates and session transcript streaming
- **D-12:** All endpoints return Pydantic response models with explicit schemas
- **D-13:** JWT auth middleware (simple, single-tenant — no OAuth complexity)

### Dashboard views
- **D-14:** Active cascades: list view with stage status indicators, click-through to cascade detail
- **D-15:** Pending gates: context + model recommendation + resolve controls, filterable by gate type
- **D-16:** Session transcripts: message history with role indicators, tool call display, cost per message
- **D-17:** Cost dashboard: Recharts bar/line charts — cost per cascade, per session, per model

### Ledger explorer
- **D-18:** TanStack Table with server-side pagination
- **D-19:** AS OF TIMESTAMP picker — date/time input that queries ledger state at that moment
- **D-20:** Pre-built timestamp templates: "now", "1 hour ago", "yesterday", "last week"

### Knowledge graph browser
- **D-21:** Entity/fact/community list views with hybrid search integration
- **D-22:** Fact detail shows bi-temporal timestamps (valid from/until, created/expired)
- **D-23:** Graph visualization deferred — list-based browsing for v1, force-directed graph is v2

### Self-calibration metrics
- **D-24:** All 8 metrics from db/queries/metrics/*.sql rendered in a single dashboard page
- **D-25:** Recharts for visualization — line charts for trends, bar charts for comparisons
- **D-26:** Metrics require 10+ gate resolutions to show meaningful values — empty state before that

### Docker-compose bootstrap
- **D-27:** Extend existing docker-compose.yml with `ui` service (Vite dev server or nginx for built assets)
- **D-28:** `docker-compose up` boots everything: db, executor, proxy, web API, email adapter, UI
- **D-29:** Health checks on all services — UI waits for web API to be healthy

### Claude's Discretion
- Exact shadcn/ui component choices per view
- Recharts chart types and color scheme
- WebSocket message format for live updates
- JWT token lifetime and refresh strategy
- Exact routing structure (/cascades, /gates, /sessions, /costs, /ledger, /knowledge, /metrics)
- Which Open WebUI / Vercel AI SDK patterns to adopt vs build custom (informed by research)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UI specification
- `eclusa.md` §7 — Back office UI: views, layouts, interaction patterns
- `eclusa.md` §9 — Self-calibration metrics: definitions, formulas, visualization

### Existing backend
- `adapters/web/routes.py` — FastAPI router with resolve endpoint (extend for all UI endpoints)
- `db/queries/metrics/*.sql` — 8 self-calibration metric SQL files (backend for metrics dashboard)
- `db/queries/as_of.sql` — AS OF TIMESTAMP query (backend for ledger explorer)
- `db/queries/trace_chain.sql` — Trace chain CTE (backend for cascade detail views)
- `knowledge/search.py` — Hybrid search (backend for KG browser)

### Research targets (D-05 through D-09)
- Open WebUI — open-source LLM chat interface, React-based
- Vercel AI SDK — useChat, useCompletion, useAssistant hooks for React
- Any other relevant framework the researcher finds

### Stack references
- `.eclusa/research/STACK.md` — React 19, Vite 6, shadcn/ui, TanStack Query/Table, Recharts, Zustand

### Prior phase context
- `.eclusa/phases/05-adapters-and-gates/05-CONTEXT.md` — FastAPI app structure, adapter registry

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `adapters/web/routes.py` — FastAPI app with RBAC middleware (extend for UI endpoints)
- `db/queries/metrics/*.sql` — 8 metric SQL files ready to query
- `db/queries/as_of.sql` — Ledger AS OF query ready to use
- `knowledge/search.py` — Hybrid search function ready to expose
- `executor/dispatch.py` — Gate context building (reuse for UI gate display)

### Established Patterns
- asyncpg for all DB queries
- Pydantic models for request/response schemas
- ULID-based IDs

### Integration Points
- FastAPI app → React SPA (API calls via TanStack Query)
- WebSocket → live cascade/session updates
- docker-compose.yml → add ui service

</code_context>

<specifics>
## Specific Ideas

- MercuryOS aesthetic: ambient, minimal, information-dense without feeling cluttered
- The agent interaction surface is the most important part — research Open WebUI / Vercel AI SDK before building custom
- Forking may be better than embedding if the framework shares our React stack
- Self-calibration metrics are the "system health" view — operators glance at this to know if the system is tuning itself well
- docker-compose up must be the single command that boots everything from zero

</specifics>

<deferred>
## Deferred Ideas

- Force-directed graph visualization for knowledge graph — v2
- Real-time collaborative features (multiple operators on same cascade) — v2
- Custom theme editor for MercuryOS aesthetic — v2

</deferred>

---

*Phase: 06-back-office-ui-and-self-calibration*
*Context gathered: 2026-04-05*
