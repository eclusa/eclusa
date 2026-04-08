# Requirements: Eclusa

**Defined:** 2026-04-04
**Core Value:** Every artifact traces back to the root intent through an append-only ledger, and every decision is structurally separated from the work it evaluates.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Domain Schema

- [x] **SCHEMA-01**: Postgres schema for all 9 domain entities (intent, actor, cascade, stage, work_session, judgment_pass, fan_out, artifact, ledger_entry)
- [x] **SCHEMA-02**: Ledger table has no UPDATE/DELETE grants for application roles (append-only enforcement)
- [x] **SCHEMA-03**: Every ledger_entry carries a `schema_version` field from first migration
- [x] **SCHEMA-04**: Trace chain query returns full path: artifact -> session -> stage -> cascade -> intent
- [x] **SCHEMA-05**: AS OF TIMESTAMP queries return ledger state at any historical moment
- [x] **SCHEMA-06**: All self-calibration metric formulas are computable from the schema before it is frozen
- [x] **SCHEMA-07**: pgvector extension installed with HNSW indexes on embedding columns
- [x] **SCHEMA-08**: RBAC as decision delegation -- actor permissions define who resolves which gates, spawns cascades, sees costs

### Executor

- [x] **EXEC-01**: Stateless executor loop polls ready stages via SKIP LOCKED and dispatches them
- [x] **EXEC-02**: LISTEN/NOTIFY used as wake-hint layered on top of SKIP LOCKED polling (not sole dispatch mechanism)
- [x] **EXEC-03**: Multiple executor instances can run concurrently without double-dispatch
- [x] **EXEC-04**: Executor crash-restart recovers cleanly from DB state (no in-memory state lost)
- [x] **EXEC-05**: Executor dispatches narrowing stages to work sessions or judgment passes based on stage config
- [x] **EXEC-06**: Executor surfaces gate stages to appropriate channels (Slack, email, webhook, back office)
- [x] **EXEC-07**: Gate resolution callbacks write to DB and fire NOTIFY to unblock downstream stages

### Cascade

- [x] **CASC-01**: Cascade is a directed graph of stages with typed edges (depends_on)
- [x] **CASC-02**: Cascade supports branching (parallel work) -- ambiguity in one branch doesn't block siblings
- [x] **CASC-03**: Cascade supports nesting (sub-cascades spawned from stages)
- [x] **CASC-04**: Cascade migration changes shape via data migration -- running work sessions not interrupted mid-execution
- [x] **CASC-05**: Cascade migration is a ledger entry with old shape, new shape, and reason
- [x] **CASC-06**: Cascade states: active, paused, completed, failed, evergreen
- [x] **CASC-07**: Stage states: pending, active, blocked, resolved, skipped

### Work Sessions

- [ ] **WORK-01**: Work session starts a harness with stage input and registered proxy
- [ ] **WORK-02**: Message history streams to DB in real time (platform format, not harness-native)
- [ ] **WORK-03**: Work session can be paused (workspace snapshot to object storage)
- [ ] **WORK-04**: Work session can be resumed from snapshot (harness doesn't know it was paused)
- [ ] **WORK-05**: Model hot-swap between pause and resume -- different model, same portable history
- [ ] **WORK-06**: Native harness type: model API + Pydantic AI tools + direct DB writes (no container)
- [ ] **WORK-07**: Claude Code harness type: external backend with proxy and history capture
- [ ] **WORK-08**: Cost tracking per session: tokens_in, tokens_out, api_calls, tool_calls, wall_time_ms, estimated_usd

### Proxy Layer

- [x] **PROXY-01**: Proxy intercepts all outbound calls from harnesses
- [x] **PROXY-02**: Proxy automatically creates artifact records for every intercepted call
- [x] **PROXY-03**: Artifact records link to intent_id, cascade_id, stage_id, session_id (full trace chain)
- [x] **PROXY-04**: Proxy write path is async with circuit-breaker fallback (not synchronous bottleneck)

### Judgment Passes

- [x] **JUDG-01**: Judgment pass is a single API completion -- no harness, no tools, no agent loop
- [x] **JUDG-02**: Judgment pass receives prepared context document (not raw session history)
- [x] **JUDG-03**: Context preparation is itself a stage in the cascade (strip noise, summarize, foreground decisions)
- [x] **JUDG-04**: Judgment pass response is structured (JSON schema enforced for convergence detection)
- [x] **JUDG-05**: Judgment pass cannot modify work -- read and evaluate only (topological enforcement)
- [x] **JUDG-06**: Context preparation shared across fan-out passes (prepared once, reused)

### Fan-out Evaluation

- [x] **FAN-01**: Fan-out fires n judgment passes in parallel against shared prepared context
- [x] **FAN-02**: Fan-out computes convergence matrix from structured verdicts
- [x] **FAN-03**: Where models converge, auto-resolve with consensus verdict
- [x] **FAN-04**: Where models diverge, create gate with each model's reasoning and divergence points
- [x] **FAN-05**: Fan-out verdict states: converged, diverged, partial

### Schema Commons

- [x] **COMMONS-01**: pgvector-backed index of typed domain knowledge with HNSW indexes
- [x] **COMMONS-02**: Parser layer normalizes sources to intermediate representation (entities, fields, relations, operations, constraints)
- [x] **COMMONS-03**: Parsers for: OpenAPI specs, Prisma schemas, SQL DDL, GraphQL SDL, protobuf definitions
- [x] **COMMONS-04**: Embedding pipeline stores normalized IR with vector embeddings
- [x] **COMMONS-05**: Matching stage queries schema commons and returns ranked matches for domain concepts

### Software Construction Cascade

- [ ] **SCC-01**: Six-stage cascade template: Refine -> Match -> Cohere -> Formalize -> Derive -> Generate
- [ ] **SCC-02**: Stage 1 (Refine): multi-turn conversation narrows noisy intent to refined scope doc
- [ ] **SCC-03**: Stage 2 (Match): embedding lookup against schema commons returns matched source set
- [ ] **SCC-04**: Stage 3 (Cohere): check matched sources for composition issues (type boundaries, auth models, data friction)
- [ ] **SCC-05**: Stage 4 (Formalize): LLM drafts Haskell constraints, GHC verifies via `ghc -fno-code`
- [ ] **SCC-06**: Stage 5 (Derive): derive BDD/E2E tests from structure + compiled constraints
- [ ] **SCC-07**: Stage 6 (Generate): cheapest capable model generates code that passes all derived tests
- [ ] **SCC-08**: Fan-out evaluation between stages (intent validation after Refine, gate pre-evaluation)

### Knowledge Graph

- [x] **KG-01**: Episode tier: raw ingested data preserved exactly as received with reference timestamp
- [x] **KG-02**: Entity tier: durable concepts extracted from episodes via LLM, with entity resolution
- [x] **KG-03**: Fact tier: edges between entities with bi-temporal timestamps (t_valid, t_invalid, t_created, t_expired)
- [x] **KG-04**: Edge invalidation: new contradicting fact sets t_invalid on old fact (old fact preserved, not deleted)
- [x] **KG-05**: Community tier: clusters of strongly connected entities via label propagation
- [x] **KG-06**: Hybrid search: cosine similarity + BM25 full-text + BFS graph traversal, reranked

### Adapters

- [x] **ADAPT-03**: Email adapter: ingest intents from email, surface gates as email threads
- [x] **ADAPT-04**: Adapter layer treats inbound messages as trust boundary (structured before reaching judgment passes)

### Back Office UI

- [ ] **UI-01**: Dashboard showing active cascades with stage status
- [ ] **UI-02**: Pending gates view with context, recommendation, and resolution controls
- [ ] **UI-03**: Session transcript viewer (work session message history)
- [ ] **UI-04**: Cost dashboard: token/cost per cascade, session, model
- [ ] **UI-05**: Ledger query interface (AS OF TIMESTAMP explorer)
- [ ] **UI-06**: Knowledge graph explorer (entities, facts, communities)

### Self-Calibration

- [ ] **CAL-01**: Gate necessity rate: % where human chose different from system recommendation
- [ ] **CAL-02**: Orchestrator absorption rate: % of ambiguityUp resolved without human
- [ ] **CAL-03**: Resolution latency: time from gate creation to resolution
- [ ] **CAL-04**: Decision durability: how often gate resolution leads to rework in same cascade
- [ ] **CAL-05**: Cascade rework rate: how often completed cascades are reopened
- [ ] **CAL-06**: Model convergence rate: % of fan-outs where all n models agree
- [ ] **CAL-07**: Minority model accuracy: when human picks minority verdict, which model was it
- [ ] **CAL-08**: Fan-out necessity rate: how often multi-model verdict differed from single-model

### Infrastructure

- [ ] **INFRA-01**: `docker-compose up` boots full working instance (db, executor, proxy, web, adapters)
- [x] **INFRA-02**: Single Postgres instance for all data (domain entities, embeddings, knowledge graph, ledger)
- [x] **INFRA-03**: Object storage for workspace snapshots (keyed by session_id)
- [x] **INFRA-04**: pg_search (ParadeDB) for BM25 full-text search inside Postgres

## v1.1 Requirements

Requirements for platform verification milestone. Prove v1.0 code works end-to-end against the live running system.

### Executor & Cascade E2E

- [x] **EXEC-E2E-01**: Executor container starts and polls for ready stages without crashing
- [x] **EXEC-E2E-02**: A multi-stage cascade with dependencies dispatches stages in correct order
- [x] **EXEC-E2E-03**: Executor can be killed and restarted; recovers from DB with no duplicate dispatches

### Gates E2E

- [x] **GATE-E2E-01**: A gate stage blocks its downstream stages until resolved
- [x] **GATE-E2E-02**: Gate resolution via API unblocks downstream and cascade continues within 5 seconds
- [x] **GATE-E2E-03**: Gate resolution is visible in the back office Gates view

### Compute Primitives E2E

- [x] **COMP-E2E-01**: A judgment pass receives prepared context and returns structured verdict stored in DB
- [x] **COMP-E2E-02**: Fan-out fires n judgment passes in parallel; convergence auto-resolves, divergence creates gate
- [x] **COMP-E2E-03**: A work session can be paused on model A and resumed on model B with identical message history

### Knowledge Layer E2E

- [x] **KG-E2E-01**: An OpenAPI spec is ingested into schema commons and queryable via hybrid search
- [x] **KG-E2E-02**: A contradicting fact sets t_invalid on prior fact; AS OF queries before/after return correct versions

### Trace & Ledger E2E

- [x] **TRACE-E2E-01**: Trace chain query walks from any work session artifact back to root intent
- [x] **TRACE-E2E-02**: AS OF TIMESTAMP query returns ledger state at a historical moment

### SCC Pipeline E2E

- [ ] **SCC-E2E-01**: Full SCC cascade (Refine->Match->Cohere->Formalize->Derive->Generate) runs end-to-end
- [ ] **SCC-E2E-02**: GHC sidecar verifies Haskell constraints via async subprocess; type errors returned for retry

### Self-Calibration E2E

- [ ] **CAL-E2E-01**: After gates resolved, all 8 self-calibration metric SQL queries return computable values
- [x] **CAL-E2E-02**: Metrics dashboard renders real values after test data accumulates

### UI Polish

- [x] **UI-E2E-01**: Sessions page uses submenu pattern (nav | session list | transcript)
- [x] **UI-E2E-02**: Session status encoded as color, cost pill removed from list
- [x] **UI-E2E-03**: Sessions display generated titles instead of raw UUIDs

## v1.2 Requirements

Requirements for dogfood milestone. Prove the full journey works: intent → SCC cascade → all stages → gates → artifacts → trace.

### SCC Trigger

- [ ] **TRIGGER-01**: Operator can switch chat to "Build" mode, creating a 7-stage SCC cascade instead of a simple chat session
- [ ] **TRIGGER-02**: Platform auto-classifies intent as chat question vs build request and routes to appropriate cascade type
- [ ] **TRIGGER-03**: POST /api/scc/create endpoint creates an SCC cascade programmatically with intent text and model config

### Stage Propagation

- [ ] **PROP-01**: Executor reads upstream stage output and injects it as the next stage's input before dispatch
- [ ] **PROP-02**: Each stage receives accumulated context from all upstream stages, not just its direct parent
- [ ] **PROP-03**: Cascade record tracks per-stage status (pending/active/resolved) for UI consumption

### Cascade UI

- [ ] **CASCADE-UI-01**: Pipeline view shows stage-by-stage progress (refine → fanout → match → cohere → formalize → derive → generate) with visual status
- [ ] **CASCADE-UI-02**: Clicking a resolved stage shows its output (scope doc, matched sources, coherence report, constraints, tests, code)
- [ ] **CASCADE-UI-03**: Trace chain viewer navigates artifact → session → stage → cascade → intent in the UI
- [ ] **CASCADE-UI-04**: Active stage output streams in real-time via SSE/WebSocket (like the chat stream)

### Model Configuration

- [ ] **MODEL-01**: SCC handlers read model from env vars / config instead of hardcoded Anthropic endpoints
- [ ] **MODEL-02**: Per-stage model override configurable (e.g., cheap model for generate, frontier for cohere)
- [ ] **MODEL-03**: Model configuration selectable in UI when triggering an SCC cascade

### Dogfood

- [ ] **DOGFOOD-01**: A simple todo app (React + FastAPI) is built end-to-end through the platform — intent submitted, all 7 SCC stages complete, code generated, full trace chain verified

## v2.0 Requirements

Requirements for production hardening milestone. Make every RFC claim real under multi-user, multi-agent operation.

### Identity

- [ ] **ID-01**: JWT carries real user identity (sub claim derived from authenticated user, not hardcoded "operator")
- [ ] **ID-02**: User registration creates actor record from real identity (email/name) with appropriate type and permissions
- [ ] **ID-03**: Actor types (human, agent, system, webhook) carry distinct default permission sets; type is enforced at token issuance

### Data Integrity

- [ ] **INTEG-01**: Gate resolution is atomic — UPDATE WHERE state='blocked' RETURNING prevents double resolution; duplicate attempts return 409
- [ ] **INTEG-02**: trace_chain.sql recursive CTE returns correct cascade_id at every hop (not intent_id in the cascade slot)
- [ ] **INTEG-03**: Pause/resume ledger entries record the actual actor_id who performed the action
- [ ] **INTEG-04**: run_session_turn wraps cost read-modify-write in a transaction with SELECT FOR UPDATE

### Auth Boundaries

- [ ] **AUTH-01**: Gate resolution endpoint requires JWT bearer auth; actor_id derived from token, not trusted from request body
- [ ] **AUTH-02**: WebSocket session subscription verifies JWT holder has permission to read the requested session
- [ ] **AUTH-03**: Build-mode chat stream acquires DB connection only for short writes, not held for LLM stream duration
- [ ] **AUTH-04**: /healthz and /readyz endpoints check DB pool connectivity and core dependencies

### Pipeline

- [x] **PIPE-01**: Refine agent is a pydantic-ai Agent with tools (search_knowledge, search_schemas, create_cascade) that converses interactively before creating a cascade
- [x] **PIPE-02**: Fanout handler branches on direct scope_doc (build-mode v2) vs refine_stage_id pointer (legacy v1)
- [x] **PIPE-03**: ambiguityUp() is a tool available to any work session agent — creates a gate stage, pauses session, surfaces the gate
- [x] **PIPE-04**: A real app is built end-to-end through the platform with all SCC stages resolved and full trace chain verified

## v3 Requirements

Deferred to future release. Tracked but not in current roadmap.

### External Adapters (deferred from v1)

- **ADAPT-01**: Slack adapter: ingest intents from messages, surface gates as interactive messages
- **ADAPT-02**: WhatsApp adapter: ingest intents, surface gates as messages

### Integrations

- **INT-01**: GitHub/GitLab adapter: PR linkage, commit artifact tracking
- **INT-02**: Figma comment adapter: intent ingestion from design tools
- **INT-03**: Notion page adapter: intent ingestion from wiki
- **INT-04**: Lark message adapter: intent ingestion + gate surfacing

### Advanced Features

- **ADV-01**: Roadmap / timeline view in back office UI
- **ADV-02**: General analytics dashboards beyond cost
- **ADV-03**: Cascade template marketplace (share reusable cascade shapes)
- **ADV-04**: Orchestrator learning from past resolutions (policy auto-tuning)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multi-tenant SaaS | Single tenant per instance by design -- multi-tenancy is a separate product problem |
| External workflow framework (Temporal, Dagster, Kafka) | DB is the execution engine -- external frameworks conflict with core architecture |
| Custom LLM training / fine-tuning | Off-the-shelf models with structured prompts; schema commons achieves the benefit |
| Native mobile apps | 80% interact through Slack/WhatsApp -- adapters provide mobile access |
| Real-time collaborative editing | Not a document editor -- judgment pass transcripts cover content capture |
| Free-form ticket creation | Bypasses ambiguity resolution -- all work enters through intent -> cascade |
| Visual no-code workflow builder | Cascade is a typed graph, not a flowchart -- templates are the abstraction |
| "AI autopilot" mode (no human gates) | Gates exist because ambiguity is real -- self-calibration reduces unnecessary gates |
| Inline mutation of ledger entries | Destroys immutability guarantee -- migration cascades are the correct pattern |
| Sprint ceremonies tooling | Gate surfacing provides factual basis for ceremonies; ceremony tooling is separate |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

### v1.0 Genesis

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCHEMA-01 | Phase 1 | Complete |
| SCHEMA-02 | Phase 1 | Complete |
| SCHEMA-03 | Phase 1 | Complete |
| SCHEMA-04 | Phase 1 | Complete |
| SCHEMA-05 | Phase 1 | Complete |
| SCHEMA-06 | Phase 1 | Complete |
| SCHEMA-07 | Phase 1 | Complete |
| SCHEMA-08 | Phase 5 | Complete |
| EXEC-01 | Phase 2 | Complete |
| EXEC-02 | Phase 2 | Complete |
| EXEC-03 | Phase 2 | Complete |
| EXEC-04 | Phase 2 | Complete |
| EXEC-05 | Phase 2 | Complete |
| EXEC-06 | Phase 5 | Complete |
| EXEC-07 | Phase 5 | Complete |
| CASC-01 | Phase 2 | Complete |
| CASC-02 | Phase 2 | Complete |
| CASC-03 | Phase 2 | Complete |
| CASC-04 | Phase 2 | Complete |
| CASC-05 | Phase 2 | Complete |
| CASC-06 | Phase 2 | Complete |
| CASC-07 | Phase 2 | Complete |
| WORK-01 | Phase 3 | Pending |
| WORK-02 | Phase 3 | Pending |
| WORK-03 | Phase 3 | Pending |
| WORK-04 | Phase 3 | Pending |
| WORK-05 | Phase 3 | Pending |
| WORK-06 | Phase 3 | Pending |
| WORK-07 | Phase 7 | Pending |
| WORK-08 | Phase 3 | Pending |
| PROXY-01 | Phase 3 | Complete |
| PROXY-02 | Phase 3 | Complete |
| PROXY-03 | Phase 3 | Complete |
| PROXY-04 | Phase 3 | Complete |
| JUDG-01 | Phase 3 | Complete |
| JUDG-02 | Phase 3 | Complete |
| JUDG-03 | Phase 3 | Complete |
| JUDG-04 | Phase 3 | Complete |
| JUDG-05 | Phase 3 | Complete |
| JUDG-06 | Phase 3 | Complete |
| FAN-01 | Phase 3 | Complete |
| FAN-02 | Phase 3 | Complete |
| FAN-03 | Phase 3 | Complete |
| FAN-04 | Phase 3 | Complete |
| FAN-05 | Phase 3 | Complete |
| COMMONS-01 | Phase 4 | Complete |
| COMMONS-02 | Phase 4 | Complete |
| COMMONS-03 | Phase 4 | Complete |
| COMMONS-04 | Phase 4 | Complete |
| COMMONS-05 | Phase 4 | Complete |
| SCC-01 | Phase 7 | Pending |
| SCC-02 | Phase 7 | Pending |
| SCC-03 | Phase 7 | Pending |
| SCC-04 | Phase 7 | Pending |
| SCC-05 | Phase 7 | Pending |
| SCC-06 | Phase 7 | Pending |
| SCC-07 | Phase 7 | Pending |
| SCC-08 | Phase 7 | Pending |
| KG-01 | Phase 4 | Complete |
| KG-02 | Phase 4 | Complete |
| KG-03 | Phase 4 | Complete |
| KG-04 | Phase 4 | Complete |
| KG-05 | Phase 4 | Complete |
| KG-06 | Phase 4 | Complete |
| ADAPT-01 | v2 | Deferred |
| ADAPT-02 | v2 | Deferred |
| ADAPT-03 | Phase 5 | Complete |
| ADAPT-04 | Phase 5 | Complete |
| UI-01 | Phase 6 | Pending |
| UI-02 | Phase 6 | Pending |
| UI-03 | Phase 6 | Pending |
| UI-04 | Phase 6 | Pending |
| UI-05 | Phase 6 | Pending |
| UI-06 | Phase 6 | Pending |
| CAL-01 | Phase 6 | Pending |
| CAL-02 | Phase 6 | Pending |
| CAL-03 | Phase 6 | Pending |
| CAL-04 | Phase 6 | Pending |
| CAL-05 | Phase 6 | Pending |
| CAL-06 | Phase 6 | Pending |
| CAL-07 | Phase 6 | Pending |
| CAL-08 | Phase 6 | Pending |
| INFRA-01 | Phase 6 | Pending |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 4 | Complete |
| INFRA-04 | Phase 1 | Complete |

**v1.0 Coverage:**
- v1 requirements: 86 total
- Mapped to phases: 86
- Unmapped: 0

### v1.1 Platform Verification

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXEC-E2E-01 | Phase 8 | Complete |
| EXEC-E2E-02 | Phase 8 | Complete |
| EXEC-E2E-03 | Phase 8 | Complete |
| GATE-E2E-01 | Phase 9 | Complete |
| GATE-E2E-02 | Phase 9 | Complete |
| GATE-E2E-03 | Phase 9 | Complete |
| COMP-E2E-01 | Phase 10 | Complete |
| COMP-E2E-02 | Phase 10 | Complete |
| COMP-E2E-03 | Phase 10 | Complete |
| SCC-E2E-01 | Phase 11 | Pending |
| SCC-E2E-02 | Phase 11 | Pending |
| KG-E2E-01 | Phase 12 | Complete |
| KG-E2E-02 | Phase 12 | Complete |
| TRACE-E2E-01 | Phase 12 | Complete |
| TRACE-E2E-02 | Phase 12 | Complete |
| CAL-E2E-01 | Phase 13 | Pending |
| CAL-E2E-02 | Phase 13 | Complete |
| UI-E2E-01 | Phase 14 | Complete |
| UI-E2E-02 | Phase 14 | Complete |
| UI-E2E-03 | Phase 14 | Complete |

**v1.1 Coverage:**
- v1.1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0

### v1.2 Dogfood

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
| CASCADE-UI-01 | Phase 18 | Pending |
| CASCADE-UI-02 | Phase 18 | Pending |
| CASCADE-UI-03 | Phase 18 | Pending |
| CASCADE-UI-04 | Phase 18 | Pending |
| DOGFOOD-01 | Phase 19 | Pending |

**v1.2 Coverage:**
- v1.2 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

### v2.0 Production Hardening

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
| PIPE-01 | Phase 23 | Complete |
| PIPE-02 | Phase 23 | Complete |
| PIPE-03 | Phase 23 | Complete |
| PIPE-04 | Phase 24 | Complete |

**v2.0 Coverage:**
- v2.0 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

## v2.1 Requirements

### Ship Stage

- [ ] **SHIP-01**: Generate stage output is written to object store as content-addressed files via existing LocalObjectStore
- [ ] **SHIP-02**: A git repository is initialized per cascade with generated code committed; artifact records of type `git_commit` are created with `external_ref` pointing to the commit hash
- [ ] **SHIP-03**: Generated code is built and run in a Docker container exposed on a dynamic port; the running app is reachable via HTTP
- [ ] **SHIP-04**: The full chain (intent -> cascade -> generate stage -> object store -> git commit -> running container) is verified end-to-end with a "simple blog" intent producing a working blog accessible in a browser

### v2.1 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| SHIP-01 | Phase 25 | Pending |
| SHIP-02 | Phase 25 | Pending |
| SHIP-03 | Phase 25 | Pending |
| SHIP-04 | Phase 25 | Pending |

**v2.1 Coverage:**
- v2.1 requirements: 4 total
- Mapped to phases: 4
- Unmapped: 0

## v2.2 Requirements

### Dynamic Agent Tooling

- [ ] **AGENT-01**: Derive and Generate stages dispatch to pydantic-ai agents with real workspace tools (write_file, read_file, run_command, list_files) operating on a per-cascade workspace directory — not blind single-turn LLM calls
- [ ] **AGENT-02**: Stage agents receive upstream context (scope doc, matched sources, constraints, test suite) via propagation injection and structured system prompt — the agent knows what stage it's at and what's been narrowed
- [ ] **AGENT-03**: Ship stage deploys directly from the workspace filesystem (already tested/compiled by the generate agent) instead of parsing text blobs
- [ ] **AGENT-04**: A "simple blog" intent produces a working Flask blog accessible via HTTP where the generate agent wrote, tested, and iterated the code in a real workspace before ship deployed it

### v2.2 Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| AGENT-01 | Phase 26 | Pending |
| AGENT-02 | Phase 26 | Pending |
| AGENT-03 | Phase 26 | Pending |
| AGENT-04 | Phase 26 | Pending |

**v2.2 Coverage:**
- v2.2 requirements: 4 total
- Mapped to phases: 4
- Unmapped: 0

---
*Requirements defined: 2026-04-04*
*Last updated: 2026-04-07 after v2.2 roadmap created (phase 26)*
