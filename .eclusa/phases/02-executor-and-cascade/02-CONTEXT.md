# Phase 2: Executor and Cascade - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Stateless executor loop that reads ready stages via SKIP LOCKED, dispatches narrowing stages and surfaces gate stages, uses LISTEN/NOTIFY as a wake-hint only (not sole dispatch mechanism). Cascade is a directed graph of stages with branching, nesting, and migration semantics. Multiple concurrent executor instances must not double-dispatch. This phase builds the execution engine — no compute primitives (work sessions, judgment passes) yet, only the dispatch contract.

</domain>

<decisions>
## Implementation Decisions

### Polling strategy
- **D-01:** Executor main loop uses `SELECT ... FOR UPDATE SKIP LOCKED` to claim ready stages — the exact query pattern from eclusa.md 5.1
- **D-02:** LISTEN/NOTIFY is a wake-hint layered on top of polling — executor polls on a ~1s interval, NOTIFY shortcuts the wait but is never the sole dispatch trigger
- **D-03:** Exponential backoff when no ready stages found (1s → 2s → 4s, cap at 5s), reset to 1s on NOTIFY or successful dispatch
- **D-04:** Executor is a single async Python process (~300-500 lines) using asyncpg for the hot path

### Dispatch routing
- **D-05:** Stage type determines dispatch: `narrowing` → dispatch to compute backend (stub in Phase 2, real in Phase 3), `gate` → check auto-resolvability then surface
- **D-06:** Stage dispatch is a function call, not a message queue — executor calls dispatch_narrowing(stage) or surface_gate(stage) directly
- **D-07:** In Phase 2, dispatch_narrowing is a stub that marks the stage resolved immediately (real dispatch in Phase 3)
- **D-08:** surface_gate is a stub that logs the gate (real surfacing via adapters in Phase 5); auto-resolvable gates resolve immediately

### Cascade graph
- **D-09:** Cascade graph edges are `stage.depends_on: ulid[]` — a stage is ready when all depends_on stages are in terminal state (resolved/skipped)
- **D-10:** Branching is implicit: stages with no dependency on each other can dispatch in parallel
- **D-11:** Sub-cascades are regular cascades with a parent_stage_id linking back — the executor treats them identically
- **D-12:** A stage in state `blocked` is not ready until unblocked (e.g., gate resolution); sibling branches continue independently

### Cascade migration
- **D-13:** Migration is proposed by writing a pending migration record to the DB (new shape, reason, proposed_by actor)
- **D-14:** Executor checks for pending migrations at the start of each dispatch cycle — applies them before dispatching new stages
- **D-15:** Migration never interrupts a running work session — it applies on the next dispatch cycle after the current dispatch completes
- **D-16:** Migration is a ledger entry recording: cascade_id, old shape (snapshot), new shape (snapshot), reason, applied_at

### Error handling
- **D-17:** Stage failure policy is set at the cascade level: `on_stage_failure: retry | skip | fail_cascade`
- **D-18:** Default policy is `fail_cascade` — conservative; explicit opt-in for retry/skip
- **D-19:** Retry has a max count per stage (default 3); each retry is a new ledger entry
- **D-20:** When cascade fails, all pending stages are marked `skipped`, active stages are allowed to complete

### Concurrency
- **D-21:** No application-level locking — SKIP LOCKED is the only coordination mechanism
- **D-22:** Multiple executor instances are fully independent; they share nothing except the DB

### Claude's Discretion
- Exact asyncio event loop structure (single-task vs task-per-dispatch)
- Connection pool size and configuration
- Logging strategy (structured JSON vs plain text)
- Exact retry backoff for stage retries
- How to structure the executor as a Python module (single file vs package)
- LISTEN/NOTIFY channel scoping (D-23 deferred to Phase 5 — see Deferred Ideas)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Executor specification
- `eclusa.md` §5.1 — Executor pseudocode: SKIP LOCKED query, LISTEN/NOTIFY, stage dispatch loop
- `eclusa.md` §5.2 — Stage dispatch patterns for narrowing, judgment pass, fan-out, and gate resolution

### Cascade specification
- `eclusa.md` §3.3 — Cascade entity: directed graph, branching, nesting, migration, states
- `eclusa.md` §3.4 — Stage entity: narrowing vs gate, state machine, depends_on edges

### Existing schema (Phase 1 output)
- `db/models/domain.py` — Cascade, Stage, Intent, Actor, Artifact, LedgerEntry models with exact column names
- `db/models/compute.py` — WorkSession, JudgmentPass, FanOut models (tables exist but unpopulated until Phase 3)
- `alembic/versions/0001_initial_schema.py` — Full DDL including enum types (stage_state, cascade_state, stage_type)

### Research findings
- `.eclusa/research/PITFALLS.md` — LISTEN/NOTIFY scale limits (must be wake-hint only), recursive CTE cycle detection
- `.eclusa/research/ARCHITECTURE.md` — Build order, executor component boundaries

### Prior phase context
- `.eclusa/phases/01-db-foundation/01-CONTEXT.md` — D-06: direct SQL in executor hot path; D-13: pytest + testcontainers

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `db/models/domain.py` — Stage state enum (pending/active/blocked/resolved/skipped), cascade state enum (active/paused/completed/failed/evergreen), stage type enum (narrowing/gate)
- `db/queries/trace_chain.sql` — Recursive CTE pattern with CYCLE guard (reference for cascade graph traversal)
- `tests/conftest.py` — Testcontainers Postgres fixture with Alembic migration (reuse for executor tests)

### Established Patterns
- asyncpg for direct SQL queries (Phase 1 convention from D-06)
- ULID-based IDs stored as UUID (Phase 1 convention from D-01/D-02)
- Ledger entries for all state changes (Phase 1 convention from D-07/D-08/D-09)

### Integration Points
- Executor reads `stage` table via SKIP LOCKED query
- Executor writes to `stage` (state changes), `ledger_entry` (all transitions), `cascade` (migration)
- Phase 3 replaces dispatch stubs with real compute primitives
- Phase 5 replaces gate surfacing stubs with real adapter dispatch

</code_context>

<specifics>
## Specific Ideas

- The executor pseudocode in eclusa.md §5.1 is the authoritative reference — follow it closely, the real implementation should be recognizable as an elaboration of that pseudocode
- The RFC says ~300-500 lines for the executor — this is the target complexity; if it's growing beyond that, something is wrong
- "If it crashes, restart it — all state survives in Postgres" is the core design principle; zero in-memory state that isn't in the DB

</specifics>

<deferred>
## Deferred Ideas

- **D-23 (cascade_id-scoped NOTIFY channels):** Deferred to Phase 5. RESEARCH.md endorses selective channels as a Phase 5 optimization. Phase 2 uses a single generic `LISTEN stage_changed` channel — sufficient for correctness at this scale. Scoped channels (`pg_notify('stage_changed:{cascade_id}', ...)`) will be implemented when Phase 5 wires the real adapter dispatch layer.

</deferred>

---

*Phase: 02-executor-and-cascade*
*Context gathered: 2026-04-04*
