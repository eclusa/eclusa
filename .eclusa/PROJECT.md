# Eclusa

## What This Is

Eclusa is an evergreen company operating system — a coordination substrate where intents enter as ambiguity and exit as traced artifacts. Not an AI coding tool, not a workflow engine. The nervous system of an organization, with every decision traced, every gate resolved, and the full history queryable at any timestamp. 80% of users never open eclusa directly — they interact through Slack, WhatsApp, email, Figma, webhooks. The integration layer is the product surface.

## Core Value

Every artifact traces back to the root intent through an append-only ledger, and every decision is structurally separated from the work it evaluates — no agent evaluates its own output.

## Requirements

### Validated

- ✓ Postgres schema for all 9 domain entities + 4 KG tables — Phase 1
- ✓ Ledger append-only enforcement (REVOKE + defense-in-depth trigger) — Phase 1
- ✓ Trace chain queries (recursive CTE with CYCLE guard) — Phase 1
- ✓ AS OF TIMESTAMP ledger queries — Phase 1
- ✓ Self-calibration metric formulas SQL-computable (8 SQL files verified) — Phase 1
- ✓ pgvector HNSW indexes on embedding columns — Phase 1
- ✓ pg_search BM25 index on entity text columns — Phase 1
- ✓ Stateless executor loop with SKIP LOCKED + LISTEN/NOTIFY wake-hint — Phase 2
- ✓ Cascade as directed graph with branching, nesting, migration — Phase 2
- ✓ Multiple concurrent executors without double-dispatch (SKIP LOCKED) — Phase 2
- ✓ Cascade migration mechanics (proposal → apply on next dispatch cycle) — Phase 2
- ✓ Stage dispatch routing (narrowing/gate stubs, real in Phase 3/5) — Phase 2
- ✓ Crash-restart recovery (zero in-memory state) — Phase 2
- ✓ Work session harness (pydantic-ai, pause/resume, model hot-swap, cost tracking) — Phase 3
- ✓ Proxy layer (mitmproxy addon, async artifact capture, SSE passthrough) — Phase 3
- ✓ Judgment passes (single completion, VerdictModel, context prep, topological enforcement) — Phase 3
- ✓ Fan-out evaluation (parallel passes, convergence matrix, auto-resolve/gate on divergence) — Phase 3
- ✓ Schema commons: 5 parsers (OpenAPI, Prisma, SQL DDL, GraphQL SDL, protobuf) → canonical IR — Phase 4
- ✓ Embedding pipeline (entity-level, pgvector HNSW) — Phase 4
- ✓ Temporal knowledge graph (episode → entity → fact, bi-temporal, edge invalidation) — Phase 4
- ✓ Community detection via label propagation — Phase 4
- ✓ Hybrid search (cosine + BM25 + BFS + RRF fusion, per-signal scores) — Phase 4
- ✓ Object storage (LocalObjectStore with blake3 content-hash keying) — Phase 4
- ✓ Email adapter (inbound IMAP + outbound SMTP, Message-ID dedup) — Phase 5
- ✓ Gate mechanism (suspend/surface/resolve with adapter dispatch) — Phase 5
- ✓ RBAC enforcement (permission check at API boundary, JSONB permissions) — Phase 5
- ✓ Trust boundary (sanitize_email before executor ingestion) — Phase 5
- ✓ Cascade-scoped NOTIFY (stage_changed:{cascade_id}) — Phase 5
- ✓ Back office UI: cascades, gates, transcripts, costs, ledger, KG, metrics (React 19 + shadcn/ui) — Phase 6
- ✓ Self-calibration dashboard (8 metrics with Recharts) — Phase 6
- ✓ FastAPI REST API + WebSocket for live updates — Phase 6
- ✓ docker-compose full bootstrap (5 services + health checks) — Phase 6
- ✓ Software Construction Cascade (6-stage template: Refine→Match→Cohere→Formalize→Derive→Generate) — Phase 7
- ✓ GHC sidecar for Haskell constraint verification (ghc -fno-code, async subprocess) — Phase 7
- ✓ Claude Code harness type (external backend, proxy-mediated history capture) — Phase 7
- ✓ Fan-out intent validation between Refine and Match stages — Phase 7

### Active
- [ ] Stateless executor loop: poll ready stages, dispatch narrowings, surface gates
- [ ] Cascade as directed graph with branching, nesting, migration
- [ ] Work session lifecycle: start, proxy, pause, resume, swap, transfer
- [ ] Proxy layer for outbound call interception + artifact capture
- [ ] Harness support: native (Pydantic AI + direct DB) + Claude Code backend
- [ ] Model hot-swap between pause/resume (portable message history)
- [ ] Judgment pass dispatch: single API completion, no tools, prepared context
- [ ] Context preparation as a local stage (strip noise, summarize, foreground decisions)
- [ ] Fan-out evaluation: n models in parallel, convergence detection, divergence → gate
- [ ] Schema commons: pgvector-backed typed domain knowledge index
- [ ] Parser layer: OpenAPI, Prisma, SQL DDL, GraphQL SDL, protobuf → IR
- [ ] Software construction cascade template (6-stage: Refine → Match → Cohere → Formalize → Derive → Generate)
- [ ] Haskell constraint workflow: LLM drafts constraints, GHC verifies (ghc -fno-code)
- [ ] Test derivation from structure + constraints (BDD/E2E)
- [ ] Temporal knowledge graph: episode → entity → fact (bi-temporal) → community tiers
- [ ] Edge invalidation with t_valid/t_invalid/t_created/t_expired timestamps
- [ ] Hybrid search: cosine similarity + BM25 + BFS graph traversal, reranked
- [ ] Slack adapter: intent ingestion + gate surfacing
- [ ] WhatsApp adapter: intent ingestion + gate surfacing
- [ ] Email adapter: intent ingestion + gate surfacing
- [ ] Back office UI: active cascades, pending gates, session transcripts, cost dashboard, ledger queries
- [ ] Self-calibration dashboards: 8 metrics rendered with real data
- [ ] RBAC as decision delegation (who resolves which gates, spawns cascades, sees costs)
- [ ] `docker-compose up` boots full instance (db + executor + proxy + web + adapters)

### Out of Scope

- Multi-tenant SaaS — single tenant per instance by design
- External workflow framework dependency — DB is the execution engine
- Custom LLM training — uses off-the-shelf models with structured prompts
- Mobile native apps — web-first back office, integrations handle front office
- Real-time collaborative editing — not a document editor

## Context

Eclusa evolves from three prior generations:
1. **The .cog file (v1-v4):** Proved governance-as-spec works. Single YAML file readable by humans AND machines. Hit ceiling when needing multiple agents, multiple harnesses, queryable state.
2. **The pipeline spec (v5):** Six-stage narrowing pipeline. Qdrant schema commons. Haskell constraints verified by GHC. Proved schema-as-coordinate-space and structural gates.
3. **The platform (current):** .cog dissolves into DB. Governance primitives become platform entities. Cascade logic in durable execution (Postgres + stateless executor).

Key architectural principles:
- **The delta, always** — only genuinely novel information moves through the system
- **Ambiguity up, decisions down** — unresolvable items cascade upward to humans/smarter models
- **Three compute types** — work sessions (tools, cheap models), judgment passes (no tools, frontier models), executor (no model, graph traversal)
- **Migration, not mutation** — cascade shape evolution is a data migration, not runtime mutation
- **Code is the last output** — written after all ambiguity is resolved

Competitive frame: Jira, Linear, Notion — not LangGraph, CrewAI, or Cursor.

## Constraints

- **Infrastructure**: Single Postgres instance (+ pgvector) for everything — no external vector DB
- **Execution**: Stateless executor, all state in DB, crash-restart safe
- **Concurrency**: Postgres SKIP LOCKED for multi-executor, LISTEN/NOTIFY for event-driven dispatch
- **Storage**: Object storage for workspace snapshots (session pause/resume)
- **Deployment**: `docker-compose up` — single command bootstrap
- **Tech stack**: Python executor (~300-500 lines), Pydantic AI for native harness

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Postgres + pgvector over Neo4j + Qdrant | Operational simplicity, recursive CTEs feasible for graph traversal, defer until query patterns stabilize | — Pending |
| Append-only ledger, no UPDATE/DELETE | Sacred trace chain — if it's not in the ledger, it didn't happen | — Pending |
| Work/judgment separation is topological | No agent evaluates its own output — enforced by architecture, not policy | — Pending |
| Haskell for formal constraints | GHC doesn't hallucinate — compiler as structural gate, humans never see Haskell | — Pending |
| Migration not mutation for cascades | Running cascades complete on original shape or migrate explicitly, ledger records transition | — Pending |
| Fan-out for ambiguity detection | Model disagreement IS the ambiguity detector — convergence auto-resolves, divergence surfaces as gate | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/eclusa:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/eclusa:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Current Milestone: v2.0 Production Hardening

**Goal:** Make Eclusa trustworthy for multi-user, multi-agent operation. Fix every gap between "works for 1 agent + 1 human" and "runs 24/7 for a 50-person org." Every RFC claim that exists as code but was never exercised becomes real.

**Target features:**
- Real actor identity (per-user JWT, not hardcoded "operator")
- Data integrity (atomic gate resolution, correct trace chain SQL, proper ledger attribution)
- Auth boundaries (JWT on all mutation endpoints, session ownership checks)
- Concurrency safety (transaction-safe session writes, connection pool discipline)
- Interactive Refine agent (multi-turn conversation with tools, agent decides when to create cascade)
- SCC pipeline end-to-end (all stages resolve, fanout handles build-mode input)
- Dogfood: build a real app through the platform with full trace chain verified

---
*Last updated: 2026-04-06 — Milestone v2.0 started (production hardening)*
