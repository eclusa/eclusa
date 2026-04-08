# Roadmap: Eclusa

## Milestones

- **v1.0 Genesis** - Phases 1-7 (shipped 2026-04-06)
- **v1.1 Platform Verification** - Phases 8-14 (in progress)
- **v1.2 Dogfood** - Phases 15-19 (planned)
- **v2.0 Production Hardening** - Phases 20-24 (planned)
- **v2.1 Ship Stage** - Phase 25 (complete)
- **v2.2 Dynamic Agent Tooling** - Phase 26 (planned)

## Phases

<details>
<summary>v1.0 Genesis (Phases 1-7) - SHIPPED 2026-04-06</summary>

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: DB Foundation** - Postgres schema, append-only ledger, and three day-one correctness invariants locked before any other component is built (completed 2026-04-04)
- [x] **Phase 2: Executor and Cascade** - Stateless SKIP LOCKED executor with LISTEN/NOTIFY as wake-hint; cascade graph with migration semantics
- [x] **Phase 3: Compute Primitives** - Work sessions, judgment passes, fan-out evaluation, and the proxy layer that enables model hot-swap (completed 2026-04-05)
- [x] **Phase 4: Knowledge Layer** - Schema commons parsers, embedding pipeline, temporal knowledge graph, and hybrid search (completed 2026-04-05)
- [x] **Phase 5: Adapters and Gates** - Gate mechanism, Slack/WhatsApp/email adapters, RBAC, and the adapter trust boundary (completed 2026-04-05)
- [x] **Phase 6: Back Office UI and Self-Calibration** - React SPA, cost dashboard, ledger explorer, self-calibration metrics, and docker-compose bootstrap
- [x] **Phase 7: Software Construction Cascade** - Six-stage SCC template, Haskell/GHC constraint verification, and Claude Code harness

### Phase 1: DB Foundation
**Goal**: The full domain schema exists, append-only invariants are enforced at the DB layer, and the three correctness invariants with no retroactive fix path are verified before the schema is frozen
**Depends on**: Nothing (first phase)
**Requirements**: SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05, SCHEMA-06, SCHEMA-07, SCHEMA-08, INFRA-02, INFRA-04
**Success Criteria** (what must be TRUE):
  1. All 9 domain entities exist as Postgres tables with Alembic migration history; `docker-compose up` seeds a clean DB from zero
  2. Application roles cannot issue UPDATE or DELETE on the ledger_entry table — the DB rejects such statements at the permission layer
  3. Every ledger_entry row carries a `schema_version` field populated from the migration that created it
  4. A trace chain query can walk from any artifact row back to its session, stage, cascade, and intent in a single query using recursive CTEs with CYCLE guards
  5. AS OF TIMESTAMP query returns ledger state at any historical moment; all 8 self-calibration metric formulas are verified as SQL-computable against seeded test data before the schema is frozen
**Plans**: 5 plans
Plans:
- [x] 01-01-PLAN.md — Project scaffold: pyproject.toml, Alembic async init, docker-compose (paradedb), pytest conftest
- [x] 01-02-PLAN.md — SQLAlchemy models (13 tables) + initial Alembic migration with full DDL, ledger enforcement, HNSW, pg_search
- [x] 01-03-PLAN.md — Named SQL files: trace_chain, as_of, and all 8 self-calibration metric queries
- [x] 01-04-PLAN.md — Full test suite: test_schema, test_ledger, test_trace_chain, test_as_of, test_metrics
- [x] 01-05-PLAN.md — Exit criteria verification and human sign-off checkpoint

### Phase 2: Executor and Cascade
**Goal**: A stateless executor loop reads ready stages via SKIP LOCKED, dispatches them, and uses LISTEN/NOTIFY only as a wake-hint layered on top of polling — multiple concurrent executor instances do not double-dispatch
**Depends on**: Phase 1
**Requirements**: EXEC-01, EXEC-02, EXEC-03, EXEC-04, EXEC-05, EXEC-06, EXEC-07, CASC-01, CASC-02, CASC-03, CASC-04, CASC-05, CASC-06, CASC-07
**Success Criteria** (what must be TRUE):
  1. Executor can be killed mid-run and restarted; it recovers to correct state from DB with no manual intervention and no duplicate dispatches
  2. Three concurrent executor instances process a seeded cascade with 20 parallel stages without any stage executing twice
  3. A cascade with branching stages completes; one branch's gate does not block sibling branches from progressing
  4. A cascade shape can be migrated while a work session is mid-execution; the ledger entry for the migration records old shape, new shape, and reason
  5. Every stage reaches a terminal state (resolved, skipped, failed) and the executor does not hang on any cascade shape including deeply nested sub-cascades
**Plans**: 5 plans
Plans:
- [x] 02-01-PLAN.md — Alembic migration 0002: failure_policy, parent_stage_id, retry_count, cascade_migration_proposal table
- [x] 02-02-PLAN.md — Wave 0 test scaffolds: test stubs + topology seeding helpers (parallel with 02-01)
- [x] 02-03-PLAN.md — executor/cascade.py: SKIP LOCKED claim, migration apply, cascade completion check
- [x] 02-04-PLAN.md — executor/dispatch.py + recovery.py: narrowing stub, gate surfacing stub, stale recovery
- [x] 02-05-PLAN.md — executor/loop.py: main poll loop, LISTEN/NOTIFY wake, backoff, end-to-end integration

### Phase 3: Compute Primitives
**Goal**: Work sessions run with proxy-mediated artifact capture, judgment passes deliver structured evaluations with topological independence enforced, and fan-out fires n parallel passes whose convergence or divergence is detected from structured output — model hot-swap between pause and resume works
**Depends on**: Phase 2
**Requirements**: WORK-01, WORK-02, WORK-03, WORK-04, WORK-05, WORK-06, WORK-07, WORK-08, PROXY-01, PROXY-02, PROXY-03, PROXY-04, JUDG-01, JUDG-02, JUDG-03, JUDG-04, JUDG-05, JUDG-06, FAN-01, FAN-02, FAN-03, FAN-04, FAN-05
**Note**: WORK-07 (Claude Code harness type) is deferred to Phase 7 per REQUIREMENTS.md traceability — it depends on the full SCC infrastructure. Plans 03-01 through 03-05 cover all other Phase 3 requirements.
**Success Criteria** (what must be TRUE):
  1. A work session paused on model A resumes on model B with identical message history; the harness does not observe the swap
  2. A proxy-intercepted LLM call creates an artifact record linked to intent, cascade, stage, and session — the artifact DB write is non-blocking and the request completes at normal latency even under 10 concurrent sessions
  3. A judgment pass receives a structured context document and returns a JSON-schema-validated verdict; it cannot issue write operations to work outputs
  4. A fan-out with 3 judgment passes on shared prepared context auto-resolves when all models converge and creates a gate with each model's reasoning when they diverge
  5. Token costs, API call counts, and wall time are recorded per session and queryable by cascade
**Plans**: 5 plans
Plans:
- [x] 03-01-PLAN.md — Phase 3 deps, Nyquist Wave 0 test stubs, proxy/addon.py ArtifactCaptureAddon
- [x] 03-02-PLAN.md — harness/ module: work session lifecycle, pause/resume, model hot-swap, cost tracking
- [x] 03-03-PLAN.md — judgment/ module: VerdictModel, context_prep, single completion, DB record
- [x] 03-04-PLAN.md — fan_out/convergence.py + fan_out/dispatcher.py: parallel firing and convergence matrix
- [x] 03-05-PLAN.md — fan_out/db.py: fan-out DB persistence, auto-resolve on convergence, gate on divergence; all fan-out tests green

### Phase 4: Knowledge Layer
**Goal**: Schema commons ingests and normalizes five schema formats into a vector-indexed IR, the temporal knowledge graph stores bi-temporal facts with edge invalidation, and hybrid search returns ranked results across cosine similarity, BM25, and graph traversal
**Depends on**: Phase 1
**Requirements**: COMMONS-01, COMMONS-02, COMMONS-03, COMMONS-04, COMMONS-05, KG-01, KG-02, KG-03, KG-04, KG-05, KG-06, INFRA-03
**Success Criteria** (what must be TRUE):
  1. An OpenAPI spec, a Prisma schema, a SQL DDL file, a GraphQL SDL, and a protobuf definition each parse to the canonical IR with entities, fields, relations, operations, and constraints populated
  2. A hybrid search query with 50+ seeded entities returns ranked results; cosine similarity, BM25, and BFS graph traversal all contribute to the reranked output with per-signal score transparency (the 3-signal RRF SQL is identical at any scale)
  3. A contradicting fact sets t_invalid on the prior fact while preserving the old fact row; an AS OF query before the contradiction returns the old fact; an AS OF query after returns the new fact
  4. A matching stage query against schema commons returns ranked matches for a domain concept from the ingested sources
**Plans**: 8 plans
Plans:
- [x] 04-01-PLAN.md — SchemaIR Pydantic model + LocalObjectStore (INFRA-03) + parser deps install (Wave 1)
- [x] 04-01b-PLAN.md — Wave 0 test stubs (12 files) + schema fixtures (5 files) (Wave 1, parallel with 04-01)
- [x] 04-02-PLAN.md — Parsers: OpenAPI, SQL DDL, GraphQL SDL (Wave 2, parallel with 04-03 and 04-04)
- [x] 04-03-PLAN.md — Parsers: Prisma (hand-rolled) + Protobuf (Wave 2, parallel with 04-02 and 04-04)
- [x] 04-04-PLAN.md — Embedding pipeline: embed_texts + embed_schema_ir into entity table (Wave 2, parallel with 04-02 and 04-03)
- [x] 04-05-PLAN.md — KG ingestion: episode ingest + entity extraction + entity resolution + entity persistence (Wave 3)
- [x] 04-06-PLAN.md — KG facts: create_fact_with_invalidation + run_label_propagation (Wave 4)
- [x] 04-07-PLAN.md — Hybrid search: cosine + BM25 + BFS + RRF SQL with per-signal scores + search_schema_commons + human sign-off (Wave 5)

### Phase 5: Adapters and Gates
**Goal**: Gate stages suspend cascade execution, surface to humans via email (v1 external adapter), and unblock downstream stages on resolution — RBAC defines who resolves which gates and the adapter layer treats all inbound messages as untrusted raw text before executor ingestion
**Depends on**: Phase 3
**Requirements**: ADAPT-03, ADAPT-04, EXEC-06, EXEC-07, SCHEMA-08
**Success Criteria** (what must be TRUE):
  1. A gate stage suspends its cascade branch; sibling branches continue; downstream stages remain blocked until the gate resolves
  2. An email message creates an intent via the email adapter with Message-ID deduplication; gate is surfaced as an email thread; reply resolves the gate and unblocks downstream
  3. An actor with resolver permissions for gate type X can resolve gates of type X but not type Y; cost visibility is restricted to actors with cost_view permission
  4. All inbound email is sanitized at the trust boundary before reaching the executor
**Plans**: 7 plans
Plans:
- [x] 05-01-PLAN.md — Deps install (aioimaplib, aiosmtplib, fastapi) + migration 0003 (resolve_token) + adapters/ skeleton + Wave 0 test stubs
- [x] 05-02-PLAN.md — adapters/sanitize.py: trust boundary sanitize_email (TDD, ADAPT-04)
- [x] 05-03-PLAN.md — AdapterRegistry + replace surface_gate/resolve_gate stubs + scoped NOTIFY (D-05) (EXEC-06, EXEC-07)
- [x] 05-04-PLAN.md — Email inbound: IMAP poller + process_message + Message-ID dedup (ADAPT-03, ADAPT-04)
- [x] 05-05-PLAN.md — Email outbound: templates + send_gate_email + EmailAdapter.surface_gate (ADAPT-03)
- [x] 05-06-PLAN.md — RBAC: check_resolve_permission + FastAPI resolve endpoint (SCHEMA-08, EXEC-07)
- [x] 05-07-PLAN.md — Full suite green + human sign-off checkpoint

### Phase 6: Back Office UI and Self-Calibration
**Goal**: The React back office provides operators a single interface for active cascades, pending gates, session transcripts, cost tracking, ledger exploration, and knowledge graph browsing — all 8 self-calibration metrics are computed and displayed — the full instance boots from a single command
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, CAL-01, CAL-02, CAL-03, CAL-04, CAL-05, CAL-06, CAL-07, CAL-08, INFRA-01
**Success Criteria** (what must be TRUE):
  1. `docker-compose up` on a clean host with no prior state boots db, executor, proxy, web, and email adapter; a test intent created via email completes a cascade and appears in the back office
  2. The pending gates view shows context, model recommendations, and resolution controls; an operator resolves a gate from the UI and the cascade unblocks within 5 seconds
  3. All 8 self-calibration metrics render with real values after 10+ gate resolutions and fan-out evaluations have accumulated in the ledger
  4. The cost dashboard shows cost per cascade, per session, and per model; the ledger query interface returns correct results for AS OF queries with pre-built timestamp templates
  5. The knowledge graph explorer displays entities, facts, and community clusters; the session transcript viewer shows full message history for any work session
**Plans**: 9 plans
Plans:
- [x] 06-01-PLAN.md — Backend API foundation: JWT auth, cascades endpoints, gates list endpoint (Wave 1)
- [x] 06-02-PLAN.md — UI scaffold: Vite + React 19 + shadcn/ui, AppShell/Sidebar, Dockerfile, nginx (Wave 1, parallel)
- [x] 06-03-PLAN.md — Backend API part 2: sessions, costs, ledger, knowledge, metrics, WebSocket (Wave 2)
- [x] 06-04-PLAN.md — Dashboard (UI-01) + Gates view (UI-02) with TanStack Query hooks (Wave 2, parallel)
- [x] 06-05-PLAN.md — Session transcript viewer (UI-03) + Cost dashboard (UI-04) with WebSocket stream (Wave 3)
- [x] 06-06-PLAN.md — Ledger AS OF explorer (UI-05) + Knowledge graph browser (UI-06) (Wave 3, parallel)
- [x] 06-07-PLAN.md — Self-calibration metrics dashboard (CAL-01..08) with all 8 metric cards (Wave 3, parallel)
- [x] 06-08-PLAN.md — docker-compose full bootstrap: 5 services, health checks, entrypoint (INFRA-01) (Wave 4)
- [x] 06-09-PLAN.md — Full test suite + exit gate checkpoint (Wave 5)

### Phase 7: Software Construction Cascade
**Goal**: The six-stage SCC template (Refine -> Match -> Cohere -> Formalize -> Derive -> Generate) runs end-to-end on the platform, Haskell constraints are verified by GHC via async subprocess, and the Claude Code harness type is supported
**Depends on**: Phase 6
**Requirements**: SCC-01, SCC-02, SCC-03, SCC-04, SCC-05, SCC-06, SCC-07, SCC-08, WORK-07
**Success Criteria** (what must be TRUE):
  1. A software intent flows through all six SCC stages in order; Refine produces a scope doc, Match returns ranked schema commons results, Cohere flags composition issues, Formalize produces GHC-verified constraints, Derive produces BDD/E2E tests, Generate produces code that passes the derived tests
  2. The Formalize stage submits Haskell constraints to a GHC sidecar via async subprocess; GHC type errors are returned verbatim to the LLM for retry; the executor is not blocked during GHC compilation
  3. A Claude Code backend harness runs a work session with proxy-mediated history capture; the message history is portable to the canonical format for hot-swap
  4. Fan-out evaluation fires between Refine and Match stages for intent validation; divergence creates a gate before proceeding
**Plans**: 6 plans
Plans:
- [x] 07-01-PLAN.md — SCC cascade template (create_scc_cascade 7 stages) + GHC sidecar in docker-compose.yml
- [x] 07-02-PLAN.md — SCC routing in dispatch_narrowing + Refine/Match/Cohere handlers
- [x] 07-03-PLAN.md — Formalize handler: GHC async subprocess + retry loop (harness/formalize.py)
- [x] 07-04-PLAN.md — Derive/Generate handlers + fan-out intent validation (SCC-06, SCC-07, SCC-08)
- [x] 07-05-PLAN.md — Claude Code harness type (harness/claude_code.py, WORK-07)
- [x] 07-06-PLAN.md — Full suite verification + human exit gate

### Phase 07.1: Dependency Upgrade + Type Safety (INSERTED)
**Goal:** Dependency upgrade and type safety improvements
**Requirements**: TBD
**Depends on:** Phase 7
**Plans:** Complete

### Phase 07.1.1: Chat Interface -- Intent Creation via Agent Session (INSERTED)
**Goal:** Chat front door for intent creation
**Requirements**: TBD
**Depends on:** Phase 7.1
**Plans:** Complete

</details>

---

## v1.1 Platform Verification

**Milestone Goal:** Prove every v1.0 component works against the live running system -- executor dispatches real cascades, gates resolve, fan-out detects convergence/divergence, SCC runs end-to-end, knowledge graph answers queries, and self-calibration metrics compute from real data.

### v1.1 Phases

- [ ] **Phase 8: Executor Bootfix & Cascade E2E** - Fix executor container startup crash, prove multi-stage cascades dispatch in correct dependency order, verify crash-recovery
- [ ] **Phase 9: Gate Lifecycle E2E** - Gates block downstream stages, resolve via API within 5 seconds, resolution visible in back office
- [x] **Phase 10: Compute Primitives E2E** - Judgment passes return structured verdicts, fan-out detects convergence/divergence, session hot-swap preserves history (completed 2026-04-06)
- [ ] **Phase 11: SCC Pipeline E2E** - Full 6-stage SCC cascade runs end-to-end, GHC sidecar verifies Haskell constraints with retry on type errors
- [x] **Phase 12: Knowledge & Trace E2E** - Schema commons ingestion + hybrid search, trace chain walks to root intent, AS OF queries return correct historical state (completed 2026-04-06)
- [x] **Phase 13: Self-Calibration E2E** - All 8 metric SQL queries return computable values from accumulated test data, metrics dashboard renders real numbers (completed 2026-04-06)
- [x] **Phase 14: Sessions UI Polish** - Submenu pattern, status-as-color, generated titles replace raw UUIDs (completed 2026-04-06)

## v1.1 Phase Details

### Phase 8: Executor Bootfix & Cascade E2E
**Goal**: The executor container starts cleanly against the docker-compose Postgres instance, polls for ready stages, and dispatches a multi-stage cascade with dependencies in correct topological order -- crash-recovery produces no duplicate dispatches
**Depends on**: v1.0 complete (Phase 7)
**Requirements**: EXEC-E2E-01, EXEC-E2E-02, EXEC-E2E-03
**Success Criteria** (what must be TRUE):
  1. `docker-compose up` starts the executor container and it remains running for 60+ seconds with no crash loops -- logs show successful DB connection and poll loop heartbeat
  2. A seeded 5-stage cascade with dependencies (A -> B -> C, A -> D -> E) dispatches stages in topological order; B does not start before A completes; D starts independently of B
  3. The executor container is killed via `docker kill` and restarted; no stage executes twice, and all stages that were pending resume without manual intervention
**Plans**: 2 plans
Plans:
- [x] 08-01-PLAN.md — Fix executor startup: actor UUID resolution, heartbeat logging, docker-compose restart policy
- [x] 08-02-PLAN.md — E2E tests: executor boot, topological cascade dispatch, crash recovery without duplicates

### Phase 9: Gate Lifecycle E2E
**Goal**: Gate stages suspend their downstream branch, resolve via the back office API, and unblock downstream stages within seconds -- the full gate lifecycle is visible in the Gates UI view
**Depends on**: Phase 8
**Requirements**: GATE-E2E-01, GATE-E2E-02, GATE-E2E-03
**Success Criteria** (what must be TRUE):
  1. A cascade with a gate stage between two narrowing stages blocks the downstream stage; the upstream stage completes but the downstream stage stays in `pending` until the gate resolves
  2. A POST to the gate resolution API endpoint unblocks the downstream stage and the executor dispatches it within 5 seconds -- the cascade continues to completion
  3. The back office Gates view lists the pending gate with its context and recommendation; after resolution, the gate shows as resolved with the resolution payload and timestamp
**Plans**: 2 plans
Plans:
- [x] 09-01-PLAN.md — Backend E2E: gate blocks downstream, resolution unblocks and cascade completes
- [x] 09-02-PLAN.md — Playwright E2E: gate visible in Gates UI, disappears from blocked list after resolution

### Phase 10: Compute Primitives E2E
**Goal**: Judgment passes receive prepared context and return structured verdicts stored in the DB, fan-out fires parallel passes with convergence auto-resolving and divergence creating gates, and a work session paused on one model resumes on another with identical message history
**Depends on**: Phase 9
**Requirements**: COMP-E2E-01, COMP-E2E-02, COMP-E2E-03
**Success Criteria** (what must be TRUE):
  1. A judgment pass stage receives a prepared context document, calls the model API, and returns a JSON-schema-validated VerdictModel stored in the judgment_pass DB table -- the verdict is queryable via the back office API
  2. A fan-out with 3 passes using the same model with different seeds fires all 3 in parallel; when verdicts converge, the fan-out auto-resolves; when verdicts diverge (forced via conflicting seed prompts), a gate is created with each pass's reasoning attached
  3. A work session started on model A is paused (snapshot to object storage), then resumed on model B; the resumed session sees identical message history and continues from where model A left off
**Plans**: 2 plans
Plans:
- [x] 10-01-PLAN.md — Fix executor LLM env vars, judgment pass E2E, session hot-swap E2E (COMP-E2E-01, COMP-E2E-03)
- [x] 10-02-PLAN.md — Fan-out convergence/divergence E2E (COMP-E2E-02)

### Phase 11: SCC Pipeline E2E
**Goal**: A software construction cascade runs all 6 stages end-to-end (Refine through Generate) against the live system, and the GHC sidecar verifies Haskell constraints with type errors returned for LLM retry
**Depends on**: Phase 10
**Requirements**: SCC-E2E-01, SCC-E2E-02
**Success Criteria** (what must be TRUE):
  1. An intent submitted to a SCC cascade template flows through Refine, Match, Cohere, Formalize, Derive, and Generate in order; each stage produces its expected output artifact (scope doc, matched sources, coherence report, Haskell constraints, derived tests, generated code)
  2. The Formalize stage sends Haskell source to the GHC sidecar container via async subprocess; a well-typed constraint file passes verification; a deliberately ill-typed constraint file returns GHC type errors that are stored as stage output for retry
**Plans**: 2 plans
Plans:
- [ ] 11-01-PLAN.md — Wire formalize stub to handle_formalize + full SCC pipeline E2E test (SCC-E2E-01)
- [ ] 11-02-PLAN.md — GHC sidecar E2E: well-typed passes, ill-typed returns errors (SCC-E2E-02)

### Phase 12: Knowledge & Trace E2E
**Goal**: An OpenAPI spec ingested into schema commons is queryable via hybrid search, trace chain queries walk from any artifact to root intent, and AS OF TIMESTAMP queries return correct historical state -- all verified against the live running Postgres instance
**Depends on**: Phase 8
**Requirements**: KG-E2E-01, KG-E2E-02, TRACE-E2E-01, TRACE-E2E-02
**Success Criteria** (what must be TRUE):
  1. An OpenAPI spec is ingested into schema commons via the parser pipeline; a hybrid search query against the live DB returns ranked results from the ingested spec with cosine, BM25, and RRF scores visible
  2. A fact is created in the knowledge graph; a contradicting fact is then created; the old fact has t_invalid set; an AS OF query before the contradiction returns the old fact; an AS OF query after returns the new fact
  3. A trace chain query starting from a work session artifact walks back through session, stage, cascade, and intent -- returning the full provenance path in a single query against live data
  4. An AS OF TIMESTAMP query against the ledger returns the exact state at a historical moment; a second query at a different timestamp returns a different (correct) state reflecting changes between the two timestamps
**Plans**: 2 plans
Plans:
- [x] 12-01-PLAN.md — OpenAPI ingestion + hybrid search + fact invalidation + AS OF on facts (KG-E2E-01, KG-E2E-02)
- [x] 12-02-PLAN.md — Trace chain provenance walk + AS OF temporal ledger queries (TRACE-E2E-01, TRACE-E2E-02)

### Phase 13: Self-Calibration E2E
**Goal**: After gates have been resolved and fan-out evaluations have accumulated from prior phases, all 8 self-calibration metric SQL queries return computable non-null values and the metrics dashboard renders them
**Depends on**: Phase 10, Phase 12
**Requirements**: CAL-E2E-01, CAL-E2E-02
**Success Criteria** (what must be TRUE):
  1. Each of the 8 self-calibration SQL queries (gate necessity rate, orchestrator absorption rate, resolution latency, decision durability, cascade rework rate, model convergence rate, minority model accuracy, fan-out necessity rate) returns a non-null numeric value when run against the live DB after test data from prior phases has accumulated
  2. The self-calibration metrics dashboard page in the back office renders all 8 metric cards with real computed values (not placeholder zeros) -- each card shows the metric name, current value, and a visual indicator
**Plans**: 2 plans
Plans:
- [x] 13-01-PLAN.md — Backend E2E: seed metric data, verify all 8 SQL queries return non-null via GET /api/metrics (CAL-E2E-01)
- [x] 13-02-PLAN.md — Playwright E2E: seed metric data, verify metrics dashboard renders 8 cards with real values (CAL-E2E-02)

### Phase 14: Sessions UI Polish
**Goal**: The Sessions page adopts the two-level submenu layout pattern, encodes status as color instead of text badges, removes cost pills from list items, and displays generated human-readable titles instead of raw UUIDs
**Depends on**: Phase 8
**Requirements**: UI-E2E-01, UI-E2E-02, UI-E2E-03
**Success Criteria** (what must be TRUE):
  1. The Sessions page renders with three columns: navigation sidebar | session list submenu | transcript content -- matching the layout pattern established by the Chat page
  2. Session status (running, complete, failed) is encoded as a colored dot or border tint on each list item; no text badges are used for status; the cost pill is removed from the session list
  3. Each session in the list displays a generated human-readable title (derived from session content or intent) instead of a raw UUID; the UUID is still accessible but not the primary display
**Plans**: 2 plans
Plans:
- [x] 14-01-PLAN.md — Sessions UI refactor: submenu layout, status-as-color, generated titles (UI-E2E-01, UI-E2E-02, UI-E2E-03)
- [x] 14-02-PLAN.md — Playwright E2E: verify Sessions UI Polish requirements (UI-E2E-01, UI-E2E-02, UI-E2E-03)

## v1.1 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXEC-E2E-01 | Phase 8 | Pending |
| EXEC-E2E-02 | Phase 8 | Pending |
| EXEC-E2E-03 | Phase 8 | Pending |
| GATE-E2E-01 | Phase 9 | Pending |
| GATE-E2E-02 | Phase 9 | Pending |
| GATE-E2E-03 | Phase 9 | Pending |
| COMP-E2E-01 | Phase 10 | Pending |
| COMP-E2E-02 | Phase 10 | Pending |
| COMP-E2E-03 | Phase 10 | Pending |
| SCC-E2E-01 | Phase 11 | Pending |
| SCC-E2E-02 | Phase 11 | Pending |
| KG-E2E-01 | Phase 12 | Pending |
| KG-E2E-02 | Phase 12 | Pending |
| TRACE-E2E-01 | Phase 12 | Pending |
| TRACE-E2E-02 | Phase 12 | Pending |
| CAL-E2E-01 | Phase 13 | Pending |
| CAL-E2E-02 | Phase 13 | Pending |
| UI-E2E-01 | Phase 14 | Pending |
| UI-E2E-02 | Phase 14 | Pending |
| UI-E2E-03 | Phase 14 | Pending |

**Coverage:** 20/20 v1.1 requirements mapped. No orphans.

---

## v1.2 Dogfood

**Milestone Goal:** Use Eclusa to build a real app end-to-end, proving the full journey: intent enters as chat, SCC cascade dispatches through all 7 stages, each stage's output feeds the next, gates surface and resolve, code is generated, and every artifact traces back to the root intent through the UI.

### v1.2 Phases

- [x] **Phase 15: Model Configuration** - SCC handlers read model from env/config; per-stage model overrides configurable; model selection available when triggering an SCC cascade from the UI (completed 2026-04-06)
- [x] **Phase 16: Stage Output Propagation** - Executor injects upstream stage output as next stage input; each stage receives accumulated context from all prior stages; cascade tracks per-stage status for UI consumption (completed 2026-04-06)
- [x] **Phase 17: SCC Trigger** - Operator can switch chat to Build mode creating a 7-stage SCC cascade; platform auto-classifies intent; POST /api/scc/create endpoint available programmatically (completed 2026-04-06)
- [ ] **Phase 17.1: SCC Refine Redesign (INSERTED)** - Build mode becomes a Refine conversation; the SCC cascade (6 stages, 2-7) is the output of that conversation; the Refine agent has tools to search knowledge and schemas before creating the cascade
- [x] **Phase 18: Cascade Pipeline UI** - Pipeline view shows stage-by-stage progress with visual status; resolved stage outputs inspectable; trace chain navigable in UI; active stage streams output in real-time (completed 2026-04-06)
- [ ] **Phase 19: Dogfood Run** - A simple todo app (React + FastAPI) is built end-to-end through the platform with full trace chain verified

## v1.2 Phase Details

### Phase 15: Model Configuration
**Goal**: SCC stage handlers read model identifiers from environment variables and configuration instead of hardcoded values, with per-stage overrides supported and model selection available when triggering an SCC from the UI
**Depends on**: Phase 14 (v1.1 complete)
**Requirements**: MODEL-01, MODEL-02, MODEL-03
**Success Criteria** (what must be TRUE):
  1. Changing the `SCC_MODEL_DEFAULT` env var causes all SCC stage handlers to use the configured model on next dispatch -- no code change required
  2. A per-stage model override (e.g., `SCC_MODEL_GENERATE=gpt-5.4-mini`) causes only that stage to use the override model while other stages continue using the default
  3. The SCC trigger UI panel shows a model configuration section; the operator can select a model before launching a cascade, and the selection is persisted to the cascade record
**Plans**: 2 plans
Plans:
- [ ] 15-01-PLAN.md — Backend model config: env-var _resolve_model() helper in scc_handlers.py + docker-compose SCC_MODEL_* vars (MODEL-01, MODEL-02)
- [ ] 15-02-PLAN.md — Migration 0004 + API model_config wiring + ChatPage SCC model config panel (MODEL-03)

### Phase 16: Stage Output Propagation
**Goal**: The executor reads each resolved stage's output and injects it as structured input to the next stage before dispatch, giving every stage access to the accumulated context from all prior stages in the cascade
**Depends on**: Phase 15
**Requirements**: PROP-01, PROP-02, PROP-03
**Success Criteria** (what must be TRUE):
  1. A stage handler receives its input document containing the output of its direct upstream stage -- the input is injected by the executor before dispatch, not assembled by the handler
  2. A stage at position 4 in the SCC pipeline (e.g., Formalize) receives a context document that includes outputs from stages 1, 2, and 3 (Refine, Match, Cohere) -- not just its direct parent
  3. The cascade record (or a queryable view) exposes per-stage status (pending / active / resolved / failed) that a polling UI can read to track pipeline progress
**Plans**: 2 plans
Plans:
- [ ] 16-01-PLAN.md — Executor upstream output injection + accumulated context (PROP-01, PROP-02)
- [ ] 16-02-PLAN.md — Per-stage status API endpoint GET /cascades/{id}/stages (PROP-03)

### Phase 17: SCC Trigger
**Goal**: An operator can switch the chat interface into Build mode to create a 7-stage SCC cascade instead of a simple chat session, the platform auto-classifies intent to route appropriately, and a programmatic API endpoint exists for cascade creation
**Depends on**: Phase 16
**Requirements**: TRIGGER-01, TRIGGER-02, TRIGGER-03
**Success Criteria** (what must be TRUE):
  1. The chat interface has a Build mode toggle; submitting a message in Build mode creates a new SCC cascade (7 stages visible in the DB) rather than a single chat work session
  2. With auto-classification enabled, a message like "build me a todo app" routes to SCC cascade creation while "what is a cascade?" routes to a simple chat session -- without the operator manually switching modes
  3. POST /api/scc/create with intent text and optional model config creates a complete 7-stage SCC cascade and returns the cascade ID -- testable without the UI
**Plans**: 2 plans
Plans:
- [ ] 17-01-PLAN.md — Backend: mode field in chat API + SCC routing + POST /api/scc/create (TRIGGER-01, TRIGGER-03)
- [ ] 17-02-PLAN.md — Frontend: Build mode toggle + auto-classification UI (TRIGGER-01, TRIGGER-02)

### Phase 17.1: SCC Refine Redesign (INSERTED)
**Goal**: Build mode becomes the Refine stage itself — a pydantic-ai Agent with tools (search_knowledge, search_schemas, create_scc_cascade) that converses with the operator until scope is clear, then creates a 6-stage cascade (stages 2-7) as the output
**Depends on**: Phase 17
**Requirements**: REFINE-01, REFINE-02, REFINE-03
**Success Criteria** (what must be TRUE):
  1. Sending "hi" in Build mode starts a conversation where the agent asks clarifying questions — it does NOT create a cascade
  2. The Refine agent can call search_knowledge and search_schemas tools during the conversation to gather context before proposing a cascade
  3. When the agent calls create_scc_cascade, a 6-stage cascade is created (fanout, match, cohere, formalize, derive, generate — Refine already happened as the conversation); the cascade_id surfaces in the chat and a link appears in the UI
**Plans**: 3 plans
Plans:
- [ ] 17.1-01-PLAN.md — Refine agent harness + build chat bootstrap (REFINE-01)
- [ ] 17.1-02-PLAN.md — 6-stage cascade factory + chat.py build-mode streaming rewire (REFINE-02)
- [ ] 17.1-03-PLAN.md — Frontend: cascade link detection + remove JSON branch + updated labels (REFINE-03)

### Phase 18: Cascade Pipeline UI
**Goal**: The back office provides a pipeline view where operators can watch SCC stages progress in real-time, inspect the output of any resolved stage, navigate the full trace chain from generated artifact back to root intent, and see active stage output streaming live
**Depends on**: Phase 17
**Requirements**: CASCADE-UI-01, CASCADE-UI-02, CASCADE-UI-03, CASCADE-UI-04
**Success Criteria** (what must be TRUE):
  1. The cascade detail page shows all 7 SCC stages (Refine, Fan-out, Match, Cohere, Formalize, Derive, Generate) as a visual pipeline; each stage displays its current status (pending / active / resolved / failed) with a distinct visual treatment
  2. Clicking a resolved stage opens a panel showing that stage's output artifact (scope doc, matched sources, coherence report, Haskell constraints, derived tests, or generated code) -- the content is the actual artifact stored in the DB
  3. The trace chain viewer navigates from any artifact (e.g., generated code) back through session, stage, cascade, and intent -- each hop is a clickable link that opens the corresponding detail view
  4. While a stage is active, its output streams into the UI in real-time via SSE or WebSocket -- the operator sees the model's output appear incrementally without manual refresh
**Plans**: 3 plans
Plans:
- [ ] 18-01-PLAN.md -- SccPipelineView + useCascadeStages (CASCADE-UI-01)
- [ ] 18-02-PLAN.md -- StageOutputPanel + stage output API route (CASCADE-UI-02)
- [ ] 18-03-PLAN.md -- TraceChainViewer + live WebSocket streaming (CASCADE-UI-03, CASCADE-UI-04)

### Phase 19: Dogfood Run
**Goal**: A complete, real software construction run through the platform -- a todo app (React + FastAPI) built from a single intent through all 7 SCC stages, with every artifact traceable back to the root intent
**Depends on**: Phase 18
**Requirements**: DOGFOOD-01
**Success Criteria** (what must be TRUE):
  1. An intent "Build a simple todo app with a React frontend and FastAPI backend" is submitted via the chat Build mode and creates a 7-stage SCC cascade that runs to completion without manual stage intervention beyond required gates
  2. The Generate stage produces React and FastAPI code files stored as artifacts in the DB; the code reflects constraints and tests derived in prior stages
  3. The trace chain viewer walks from any generated code artifact back to the original intent in 5 hops (artifact -> session -> stage -> cascade -> intent) with no broken links
  4. The full run is documented as a UAT report capturing: intent submitted, each stage's output summary, gates encountered and resolved, final artifacts, and trace chain verification
**Plans**: 3 plans
Plans:
- [ ] 25-01-PLAN.md — Ship stage handler (parse, object store, git, Docker build/run)
- [ ] 25-02-PLAN.md — Pipeline wiring (cascade template, dispatch, propagation, docker-compose)
- [ ] 25-03-PLAN.md — E2E test: simple blog intent through full pipeline

## v1.2 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| MODEL-01 | Phase 15 | Pending |
| MODEL-02 | Phase 15 | Pending |
| MODEL-03 | Phase 15 | Pending |
| PROP-01 | Phase 16 | Pending |
| PROP-02 | Phase 16 | Pending |
| PROP-03 | Phase 16 | Pending |
| TRIGGER-01 | Phase 17 | Pending |
| TRIGGER-02 | Phase 17 | Pending |
| TRIGGER-03 | Phase 17 | Pending |
| REFINE-01 | Phase 17.1 | Pending |
| REFINE-02 | Phase 17.1 | Pending |
| REFINE-03 | Phase 17.1 | Pending |
| CASCADE-UI-01 | Phase 18 | Pending |
| CASCADE-UI-02 | Phase 18 | Pending |
| CASCADE-UI-03 | Phase 18 | Pending |
| CASCADE-UI-04 | Phase 18 | Pending |
| DOGFOOD-01 | Phase 19 | Pending |

**Coverage:** 17/17 v1.2 requirements mapped. No orphans.

## Progress

### v1.0 Genesis

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. DB Foundation | 5/5 | Complete | 2026-04-04 |
| 2. Executor and Cascade | 5/5 | Complete | 2026-04-05 |
| 3. Compute Primitives | 5/5 | Complete | 2026-04-05 |
| 4. Knowledge Layer | 8/8 | Complete | 2026-04-05 |
| 5. Adapters and Gates | 7/7 | Complete | 2026-04-05 |
| 6. Back Office UI and Self-Calibration | 9/9 | Complete | 2026-04-06 |
| 7. Software Construction Cascade | 6/6 | Complete | 2026-04-06 |
| 07.1 Dependency Upgrade (INSERTED) | - | Complete | 2026-04-06 |
| 07.1.1 Chat Interface (INSERTED) | - | Complete | 2026-04-06 |

### v1.1 Platform Verification

**Execution Order:**
Phases execute in dependency order: 8 -> 9 -> 10 -> 11 (and 12 parallel after 8) -> 13 (after 10+12) -> 14 (after 8)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 8. Executor Bootfix & Cascade E2E | 0/2 | Not started | - |
| 9. Gate Lifecycle E2E | 0/2 | Not started | - |
| 10. Compute Primitives E2E | 2/2 | Complete   | 2026-04-06 |
| 11. SCC Pipeline E2E | 0/2 | Not started | - |
| 12. Knowledge & Trace E2E | 2/2 | Complete   | 2026-04-06 |
| 13. Self-Calibration E2E | 2/2 | Complete   | 2026-04-06 |
| 14. Sessions UI Polish | 2/2 | Complete   | 2026-04-06 |

### v1.2 Dogfood

**Execution Order:**
Phases execute sequentially: 15 -> 16 -> 17 -> 18 -> 19

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 15. Model Configuration | 0/2 | Complete    | 2026-04-06 |
| 16. Stage Output Propagation | 0/TBD | Complete    | 2026-04-06 |
| 17. SCC Trigger | 0/TBD | Complete    | 2026-04-06 |
| 17.1. SCC Refine Redesign (INSERTED) | 0/3 | Not started | - |
| 18. Cascade Pipeline UI | 0/TBD | Complete    | 2026-04-06 |
| 19. Dogfood Run | 0/TBD | Not started | - |


---

## v2.0 Production Hardening

**Milestone Goal:** Make Eclusa trustworthy for multi-user, multi-agent operation. Fix every gap between "works for 1 agent + 1 human" and "runs 24/7 for a 50-person org." Real actor identity, correct data integrity invariants, enforced auth boundaries, a working interactive pipeline, and a complete dogfood run that proves the full trace chain.

### v2.0 Phases

- [x] **Phase 20: Actor Identity** - Per-user JWT carries real identity; user registration creates actor records; actor types carry distinct permission sets enforced at token issuance (completed 2026-04-07)
- [x] **Phase 21: Data Integrity** - Gate resolution is atomic; trace chain SQL returns correct cascade_id at every hop; ledger entries record real actor_id; session cost writes are transaction-safe (completed 2026-04-07)
- [x] **Phase 22: Auth Boundaries** - Gate resolution endpoint requires JWT; WebSocket subscriptions verify ownership; build-mode chat holds DB connections only for short writes; health endpoints check pool and dependencies (completed 2026-04-07)
- [x] **Phase 23: Pipeline Hardening** - Refine agent is a pydantic-ai Agent with tools; fanout handler branches on input type; ambiguityUp() tool available to all work session agents (completed 2026-04-07)
- [x] **Phase 24: Dogfood** - A real app is built end-to-end through the platform with all SCC stages resolved and full trace chain verified (completed 2026-04-07)

## v2.0 Phase Details

### Phase 20: Actor Identity
**Goal**: Every JWT carries a real authenticated user identity, user registration creates a proper actor record, and actor types (human, agent, system, webhook) carry enforced permission sets -- no hardcoded "operator" anywhere in the system
**Depends on**: Phase 19
**Requirements**: ID-01, ID-02, ID-03
**Success Criteria** (what must be TRUE):
  1. A registered user receives a JWT whose `sub` claim is derived from their authenticated email/identity -- a token with `sub: "operator"` is rejected by the auth middleware
  2. Registering a new user creates an actor record in the DB with real email, name, and `actor_type` set to `human`; the actor_id from that record is the identity used in all subsequent actions
  3. Issuing a token for an `agent` actor type produces a token with the agent permission set (not the human permission set); the type is stored on the actor record and cannot be overridden by the token holder
  4. Attempting to call a mutation endpoint with a token whose actor_type does not have the required permission returns 403
**Plans**: 2 plans
Plans:
- [ ] 20-01-PLAN.md — Backend: register endpoint, email+password token, per-type permissions, verify_token guard (ID-01, ID-02, ID-03)
- [ ] 20-02-PLAN.md — Frontend: LoginPage email+password, RegisterPage, /register route (ID-01, ID-02)

### Phase 21: Data Integrity
**Goal**: Gate resolution cannot double-fire, the trace chain SQL returns the correct entity at every hop, ledger entries record who actually performed each action, and session cost updates are transaction-safe under concurrency
**Depends on**: Phase 20
**Requirements**: INTEG-01, INTEG-02, INTEG-03, INTEG-04
**Success Criteria** (what must be TRUE):
  1. Two concurrent requests to resolve the same gate return: first request 200 with resolution payload, second request 409 Conflict -- the gate is resolved exactly once and only one ledger entry is written
  2. A trace chain query starting from any artifact walks artifact -> session -> stage -> cascade -> intent with the correct entity type at each hop; the `cascade` slot contains a `cascade_id`, not an `intent_id`
  3. After a work session is paused and resumed, the pause and resume ledger entries each carry the `actor_id` of the authenticated user who triggered the action -- not a hardcoded system value
  4. Under 10 concurrent sessions each completing a turn simultaneously, no session ends up with a stale cost total; all per-session cost fields reflect the actual accumulated values
**Plans**: 1 plan
Plans:
- [ ] 21-01-PLAN.md — All four integrity fixes: atomic gate resolution (INTEG-01), trace_chain SQL cascade_id (INTEG-02), real actor_id in pause/resume ledger (INTEG-03), SELECT FOR UPDATE cost write (INTEG-04)

### Phase 22: Auth Boundaries
**Goal**: Every mutation endpoint is protected by JWT bearer auth with actor_id derived from the token, WebSocket session access is verified against the token holder's permissions, DB connections are held only as long as needed, and health endpoints expose real pool and dependency status
**Depends on**: Phase 21
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. A POST to the gate resolution endpoint without a JWT returns 401; with a JWT whose actor lacks resolver permission returns 403; with a valid token returns 200 and uses the `actor_id` from the token (not from the request body)
  2. Opening a WebSocket subscription to a `session_id` that belongs to a different user returns a 403 close frame immediately; a user can only subscribe to their own sessions (or sessions they have explicit read permission for)
  3. Submitting a build-mode chat message triggers an LLM stream; the DB connection used for the initial write is released before the LLM stream begins -- it is not held open for the duration of the model response
  4. GET /healthz returns 200 with DB pool stats when healthy; returns 503 with error detail when the DB pool is exhausted or unreachable; GET /readyz returns 200 only when all core dependencies (DB, executor connectivity) are confirmed up
**Plans**: 1 plan
Plans:
- [ ] 22-01-PLAN.md — All four auth boundary fixes: JWT gate guard, WebSocket ownership, build-stream connection release, healthz/readyz endpoints (AUTH-01, AUTH-02, AUTH-03, AUTH-04)
**UI hint**: yes

### Phase 23: Pipeline Hardening
**Goal**: The Refine stage runs as a real pydantic-ai Agent with tools that converses interactively before creating a cascade, the fanout handler correctly branches on input type, and any work session agent can call `ambiguityUp()` to surface a gate and pause itself
**Depends on**: Phase 22
**Requirements**: PIPE-01, PIPE-02, PIPE-03
**Success Criteria** (what must be TRUE):
  1. Sending a message in Build mode starts a Refine agent conversation; the agent asks at least one clarifying question before creating a cascade; calling `search_knowledge` or `search_schemas` tools returns results from the live knowledge base
  2. A fanout stage with a direct `scope_doc` payload (build-mode v2) executes correctly; a fanout stage with a `refine_stage_id` pointer (legacy v1) also executes correctly by fetching the scope doc from the referenced stage
  3. A work session agent calling `ambiguityUp("unclear requirement")` creates a gate stage, writes a pause ledger entry for the current session, and the gate appears in the pending gates view -- the session does not continue until the gate is resolved
**Plans**: 3 plans
Plans:
- [ ] 23-01-PLAN.md — Fanout fix: branch on scope_doc (build-mode v2) vs refine_stage_id (legacy v1) (PIPE-02)
- [ ] 23-02-PLAN.md — ambiguityUp tool: gate creation, session pause, gate surfacing (PIPE-03)
- [ ] 23-03-PLAN.md — Refine agent integration: questioning philosophy, live DB search tests, error handling (PIPE-01)

### Phase 24: Dogfood
**Goal**: A real application is built end-to-end through the hardened platform -- intent submitted, all SCC stages resolve, artifacts are generated, and every artifact traces back to the root intent through the verified trace chain
**Depends on**: Phase 23
**Requirements**: PIPE-04
**Success Criteria** (what must be TRUE):
  1. An intent is submitted via the authenticated Build mode and a 6-stage SCC cascade (fanout, match, cohere, formalize, derive, generate) runs to completion -- each stage produces its expected artifact stored in the DB
  2. The generated code artifact traces back to the root intent in exactly 5 hops (artifact -> session -> stage -> cascade -> intent) with no broken links; the trace chain SQL returns the correct entity type at every hop
  3. All gates encountered during the run are surfaced to the authenticated user and resolved; each resolution ledger entry carries the real `actor_id` of the user who resolved it
  4. A UAT report captures: intent submitted, each stage's output summary, gates encountered and resolved, final artifacts, trace chain verification -- the report references real artifact IDs from the live DB
**Plans**: 2 plans
Plans:
- [x] 24-01-PLAN.md — pytest E2E: register user -> create SCC cascade -> poll all stages resolved -> verify Generate output -> 5-hop trace chain (PIPE-04)
- [x] 24-02-PLAN.md — Playwright E2E: registration -> /chat Build mode -> Refine agent responds with question -> cascade visible in /cascades list (PIPE-04)

## v2.0 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| ID-01 | Phase 20 | Pending |
| ID-02 | Phase 20 | Pending |
| ID-03 | Phase 20 | Pending |
| INTEG-01 | Phase 21 | Pending |
| INTEG-02 | Phase 21 | Pending |
| INTEG-03 | Phase 21 | Pending |
| INTEG-04 | Phase 21 | Pending |
| AUTH-01 | Phase 22 | Pending |
| AUTH-02 | Phase 22 | Pending |
| AUTH-03 | Phase 22 | Pending |
| AUTH-04 | Phase 22 | Pending |
| PIPE-01 | Phase 23 | Pending |
| PIPE-02 | Phase 23 | Pending |
| PIPE-03 | Phase 23 | Pending |
| PIPE-04 | Phase 24 | Pending |

**Coverage:** 15/15 v2.0 requirements mapped. No orphans.

## v2.0 Progress

**Execution Order:**
Phases execute strictly sequentially: 20 -> 21 -> 22 -> 23 -> 24

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 20. Actor Identity | 0/2 | Complete    | 2026-04-07 |
| 21. Data Integrity | 0/TBD | Complete    | 2026-04-07 |
| 22. Auth Boundaries | 0/TBD | Complete    | 2026-04-07 |
| 23. Pipeline Hardening | 3/3 | Complete    | 2026-04-07 |
| 24. Dogfood | 2/2 | Complete   | 2026-04-07 |

</details>

<details>
<summary>v2.1 Ship Stage (Phase 25) - IN PROGRESS</summary>

- [ ] **Phase 25: Ship Stage** - Generated code flows from SCC pipeline through object store and git into a running Docker container exposed via HTTP

## v2.1 Phase Details

### Phase 25: Ship Stage
**Goal**: The SCC Generate stage output flows through object store, git commit, and Docker build into a running application container — a "simple blog" intent produces a working blog accessible via HTTP
**Depends on**: Phase 24
**Requirements**: SHIP-01, SHIP-02, SHIP-03, SHIP-04
**Success Criteria** (what must be TRUE):
  1. Generate stage output is parsed into individual files and written to LocalObjectStore; each file's content-addressed key is recorded in an artifact row with type='file_created'
  2. A per-cascade git repository is initialized under a workspace directory; generated files are committed with a message referencing the cascade_id; an artifact of type='git_commit' is created with external_ref=commit_hash
  3. A Dockerfile is generated (or a default template used) and the code is built into a Docker image; a container runs the app and exposes it on a dynamic port; health check confirms HTTP 200
  4. A "simple blog" intent submitted through the full SCC pipeline produces a running blog that serves HTML over HTTP — the blog is reachable from the host machine
**Plans**: 3 plans
Plans:
- [ ] 25-01-PLAN.md — Ship stage handler (parse, object store, git, Docker build/run)
- [ ] 25-02-PLAN.md — Pipeline wiring (cascade template, dispatch, propagation, docker-compose)
- [ ] 25-03-PLAN.md — E2E test: simple blog intent through full pipeline

## v2.1 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| SHIP-01 | Phase 25 | Pending |
| SHIP-02 | Phase 25 | Pending |
| SHIP-03 | Phase 25 | Pending |
| SHIP-04 | Phase 25 | Pending |

**Coverage:** 4/4 v2.1 requirements mapped. No orphans.

## v2.1 Progress

**Execution Order:**
Phases execute strictly sequentially: 25

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 25. Ship Stage | 3/3 | Complete | 2026-04-07 |

</details>

<details>
<summary>v2.2 Dynamic Agent Tooling (Phase 26) - IN PROGRESS</summary>

- [ ] **Phase 26: Dynamic Agent Tooling** - Derive/Generate/Ship stages use pydantic-ai agents with real workspace tools instead of blind LLM calls; agents write, test, and iterate code in a real filesystem before deployment

## v2.2 Phase Details

### Phase 26: Dynamic Agent Tooling
**Goal**: Derive and Generate stages dispatch to pydantic-ai agents with real workspace tools (write_file, read_file, run_command, list_files) that write, compile, and test code in a per-cascade workspace — Ship deploys from the real workspace, not parsed text — a "simple blog" intent produces a working blog where the agent iterated on real code
**Depends on**: Phase 25
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04
**Success Criteria** (what must be TRUE):
  1. Derive and Generate stages create a workspace at workspaces/{cascade_id}/ and dispatch pydantic-ai agents with write_file, read_file, run_command, list_files tools — the agent produces files on disk, not code as text
  2. The agent's system prompt includes the stage position in the pipeline, upstream outputs (scope doc, constraints, test suite), and available tools — the agent knows what it's building and what's already been decided
  3. Ship stage reads files directly from the workspace directory created by Generate — no text blob parsing, no parse_generated_code()
  4. A "simple blog" intent submitted through the full SCC pipeline produces a Flask blog that serves HTML — the generate agent wrote the code, ran it, fixed errors, and confirmed it works before Ship deployed it
**Plans**: 3 plans
Plans:
- [ ] 26-01-PLAN.md — Workspace tools module + rewrite Derive/Generate handlers with pydantic-ai workspace agents (AGENT-01, AGENT-02)
- [ ] 26-02-PLAN.md — Rewrite Ship stage to read from workspace filesystem (AGENT-03)
- [ ] 26-03-PLAN.md — E2E test: simple blog intent through workspace agent pipeline + human verification (AGENT-04)

## v2.2 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| AGENT-01 | Phase 26 | Pending |
| AGENT-02 | Phase 26 | Pending |
| AGENT-03 | Phase 26 | Pending |
| AGENT-04 | Phase 26 | Pending |

**Coverage:** 4/4 v2.2 requirements mapped. No orphans.

## v2.2 Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 26. Dynamic Agent Tooling | 0/3 | Planning | — |
