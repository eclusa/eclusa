# Phase 3: Compute Primitives - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Three compute types that serve cascade stages: work sessions (agent harness with tools, managed lifecycle, proxy-mediated artifact capture), judgment passes (single API completion, no tools, prepared context, structured verdict), and fan-out evaluation (n parallel judgment passes with convergence/divergence detection). Model hot-swap between pause/resume. Cost tracking per session. This phase replaces the dispatch stubs from Phase 2 with real compute primitives.

</domain>

<decisions>
## Implementation Decisions

### Work session lifecycle
- **D-01:** Native harness type: model API + pydantic-ai tools + direct DB writes — no container, no PTY
- **D-02:** Work session lifecycle: start → running → (pause → paused → resume → running) → completed/failed
- **D-03:** Message history stored in platform format (JSONB) on work_session.message_history — updated in real-time during session
- **D-04:** Workspace snapshot on pause: serialize session state to object storage (keyed by session_id), read on resume
- **D-05:** On pause, the harness doesn't know it was paused — from its perspective, ambiguityUp returned an answer (could be 200ms or 48 hours)
- **D-06:** pydantic-ai 1.77.0 as the harness layer — type-safe, model-agnostic, supports pause/resume via message history

### Proxy layer
- **D-07:** mitmproxy Python addon (~30 lines) running as a local sidecar process — not a container
- **D-08:** Proxy intercepts all outbound HTTP calls from harness, creates artifact records automatically
- **D-09:** Artifact write path is async with circuit-breaker fallback — proxy never blocks the request
- **D-10:** Each artifact record links to intent_id, cascade_id, stage_id, session_id (full trace chain)
- **D-11:** Proxy registers with the executor on session start, deregisters on session end

### Judgment pass contract
- **D-12:** Single API completion — one request, one response, no agent loop, no tools
- **D-13:** Prepared context document — not raw session history; platform transforms before judgment
- **D-14:** Context preparation is itself a local stage in the cascade (cheap narrowing, runs locally)
- **D-15:** Response must be JSON-schema-validated — structured verdict, not prose
- **D-16:** Judgment passes cannot modify work outputs — topological enforcement, read-only access
- **D-17:** context_hash (blake3) enables dedup of identical evaluations

### Fan-out evaluation
- **D-18:** Fan-out fires n judgment passes in parallel against shared prepared context (prepared once, reused)
- **D-19:** Convergence detection via field-by-field comparison of structured JSON verdicts
- **D-20:** Where all models agree on all fields → converged → auto-resolve with consensus verdict
- **D-21:** Where models disagree on any field → diverged → create gate with each model's reasoning and divergence points
- **D-22:** Fan-out verdict states: converged, diverged, partial (some fields agree, some don't)

### Model hot-swap
- **D-23:** Between pause and resume, platform can swap to a different model
- **D-24:** Message history is in platform format — harness-specific adapters translate on ingress/egress
- **D-25:** For native sessions, platform format IS the session format (no adapter needed)
- **D-26:** Model swaps recorded in work_session.model_swaps JSONB array: [{from, to, reason, swapped_at}]

### Cost tracking
- **D-27:** work_session.cost JSONB updated on each API call: tokens_in, tokens_out, api_calls, tool_calls, wall_time_ms, estimated_usd
- **D-28:** judgment_pass.cost JSONB: tokens_in, tokens_out, estimated_usd (single call, simpler)
- **D-29:** Cost queryable by cascade: SUM across all sessions/passes linked to a cascade

### Claude's Discretion
- mitmproxy addon implementation details (request/response hooks)
- Circuit-breaker thresholds and fallback behavior
- Object storage backend for workspace snapshots (local filesystem vs S3-compatible)
- Exact pydantic-ai tool registration patterns
- Context preparation algorithm (what to strip, what to summarize)
- Convergence comparison algorithm (exact match vs semantic similarity threshold)
- blake3 vs sha256 for context_hash

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Compute type specifications
- `eclusa.md` §3.5.1 — Work session entity, harness types, managed lifecycle, model swaps, cost tracking
- `eclusa.md` §3.5.2 — Judgment pass entity, prepared context, structured response, context_hash
- `eclusa.md` §3.5.3 — Fan-out evaluation, convergence matrix, verdict states
- `eclusa.md` §3.6 — Artifact entity, artifact_type enum, proxy layer behavior

### Existing code (Phase 2 output)
- `executor/dispatch.py` — Contains stub `dispatch_narrowing()` and `surface_gate()` to be replaced
- `executor/cascade.py` — `claim_ready_stages()` returns stages for dispatch
- `executor/loop.py` — Main poll loop that calls dispatch
- `db/models/compute.py` — WorkSession, JudgmentPass, FanOut SQLAlchemy models (tables exist)
- `db/models/domain.py` — Artifact, LedgerEntry models

### Research findings
- `.eclusa/research/STACK.md` — pydantic-ai 1.77.0, mitmproxy 11.x, asyncpg dual-driver
- `.eclusa/research/PITFALLS.md` — Proxy synchronous write bottleneck, fan-out convergence on prose
- `.eclusa/research/ARCHITECTURE.md` — Component boundaries, proxy-mediated artifact capture pattern

### Prior phase context
- `.eclusa/phases/01-db-foundation/01-CONTEXT.md` — D-06: direct SQL in hot path; D-13: pytest+testcontainers
- `.eclusa/phases/02-executor-and-cascade/02-CONTEXT.md` — D-07/D-08: dispatch stubs to replace

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `executor/dispatch.py` — `dispatch_narrowing()` stub to replace with real work session start
- `executor/dispatch.py` — `dispatch_stage()` routing by stage type already works
- `db/models/compute.py` — WorkSession, JudgmentPass, FanOut tables with all columns ready
- `tests/conftest.py` — Testcontainers Postgres fixture with Alembic migration
- `tests/helpers/topology.py` — Cascade seeding helpers

### Established Patterns
- asyncpg for direct SQL (Phase 1/2 convention)
- ULID-based IDs as UUID (Phase 1 convention)
- Ledger entries for all state changes (Phase 1/2 convention)
- TDD: write test stubs → red → implement → green (Phase 2 convention)

### Integration Points
- `executor/dispatch.py:dispatch_narrowing()` — replace stub with work session start
- `executor/loop.py` — already calls dispatch, no changes needed to loop
- `work_session` table — write session records, update message_history, cost
- `judgment_pass` table — write pass records with structured response
- `fan_out` table — write fan-out records with convergence results
- `artifact` table — proxy writes artifact records on intercepted calls

</code_context>

<specifics>
## Specific Ideas

- The RFC says "no agent evaluates its own output" — this is topology, not policy. Judgment passes physically cannot modify work. The code must enforce this structurally (separate DB connections, no write tools).
- Fan-out is cheap: each pass is a single API call, context preparation is shared. The cost is in the model, not infrastructure.
- Context preparation (stripping tool call noise, summarizing long middles, foregrounding decisions) is a local stage — it runs on the executor, no model needed.
- mitmproxy addon is ~30 lines per research — keep it simple, artifact write is the only job.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-compute-primitives*
*Context gathered: 2026-04-04*
