# Architecture Research

**Domain:** AI-powered organizational coordination platform (company operating system)
**Researched:** 2026-04-04
**Confidence:** HIGH (core patterns well-established; Eclusa-specific topology is novel but grounded in verifiable components)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      INTEGRATION LAYER                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Slack   │  │ WhatsApp │  │  Email   │  │  Webhooks/API    │  │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │  │  (REST ingest)   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │              │             │                  │            │
│       └──────────────┴─────────────┴──────────────────┘           │
│                              │                                     │
│                     Intent normalization                           │
└──────────────────────────────┬───────────────────────────────────-┘
                                │
┌──────────────────────────────▼───────────────────────────────────-┐
│                        CORE PLATFORM                               │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    EXECUTOR LOOP                             │  │
│  │  poll ready stages → classify compute type → dispatch       │  │
│  │  (stateless, crash-restart safe, SKIP LOCKED concurrency)   │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                              │ dispatches to                       │
│              ┌───────────────┼────────────────┐                   │
│              ▼               ▼                ▼                   │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │ WORK SESSION  │  │  JUDGMENT    │  │      FAN-OUT        │    │
│  │   HARNESS     │  │    PASS      │  │    EVALUATION       │    │
│  │ (tools+proxy) │  │ (no tools,   │  │ (n models parallel, │    │
│  │               │  │  frontier)   │  │  convergence check) │    │
│  └──────┬────────┘  └──────┬───────┘  └─────────┬───────────┘    │
│         │                  │                     │                │
│         └──────────────────┴─────────────────────┘               │
│                              │ writes artifacts                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   PROXY LAYER                                │  │
│  │  intercept outbound LLM calls → capture I/O → artifact      │  │
│  │  model-swap on resume, portable message history             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
└──────────────────────────────┬───────────────────────────────────-┘
                                │
┌──────────────────────────────▼───────────────────────────────────-┐
│                         DATA LAYER                                 │
│                                                                    │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │             POSTGRES (single instance)                     │    │
│  │  ┌───────────────┐  ┌─────────────────┐  ┌─────────────┐  │    │
│  │  │  Domain model  │  │ Append-only     │  │  Temporal   │  │    │
│  │  │  (9 entities)  │  │ ledger          │  │  KG (bi-    │  │    │
│  │  │                │  │ (trace chain)   │  │  temporal)  │  │    │
│  │  └───────────────┘  └─────────────────┘  └─────────────┘  │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │  Schema commons (pgvector — typed domain knowledge)  │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌───────────────────────┐                                         │
│  │   OBJECT STORAGE      │                                         │
│  │  (workspace snapshots │                                         │
│  │   for pause/resume)   │                                         │
│  └───────────────────────┘                                         │
└──────────────────────────────────────────────────────────────────-┘

                        Surfaces gates/activity via
┌──────────────────────────────────────────────────────────────────┐
│                      BACK OFFICE UI                               │
│  active cascades · pending gates · session transcripts ·         │
│  cost dashboard · ledger queries · self-calibration metrics      │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation Notes |
|-----------|---------------|----------------------|
| Integration adapters | Normalize external intent signals (Slack, WhatsApp, email, webhooks) into platform entities | Thin translation layer; no business logic; async queue to avoid blocking external acks |
| Executor loop | Poll ready stages from DB, classify compute type, dispatch to correct compute primitive, mark completion | Stateless Python (~300-500 lines); SKIP LOCKED for multi-executor safety; crash at any point is safe |
| Work session harness | Run tool-using agents (Pydantic AI native or Claude Code); gate outbound calls through proxy | Two harness flavors with shared proxy; cheap/fast models; long-running with tools |
| Judgment pass | Single LLM completion with no tools; receives prepared context; returns structured verdict | Frontier models; context preparation as a preceding local stage; separate from work sessions by topology |
| Fan-out evaluation | Dispatch n models in parallel to same prompt; detect convergence vs divergence | Convergence auto-resolves; divergence surfaces as gate; model disagreement IS the ambiguity signal |
| Proxy layer | Intercept every outbound LLM call from harnesses; capture request/response as artifact; enable model-swap | Sits between harness and LLM API; stores portable message history; enables pause/resume across models |
| Cascade graph | Directed graph of stages; branching, nesting, migration support; executor reads this | Stored in Postgres; shape changes are data migrations not runtime mutations |
| Gate mechanism | Surface unresolvable items to humans or higher-authority models | Pauses stage execution; waits for external resolution signal; escalation tiers by risk level |
| Postgres (domain model) | 9 core entities; all execution state; crash-safe single source of truth | LISTEN/NOTIFY for event-driven dispatch; no UPDATE/DELETE on ledger table |
| Postgres (temporal KG) | Episode → entity → fact (bi-temporal); community tiers; edge invalidation | Four timestamps per fact: t_valid, t_invalid, t_created, t_expired; hybrid search over this |
| Postgres (schema commons) | pgvector-backed typed domain knowledge index; parser IR output lands here | Cosine similarity + BM25 + BFS traversal + rerank |
| Object storage | Workspace snapshots for session pause/resume; binary/large blobs not suited to Postgres | Referenced from session records; restored on resume |
| Parser layer | OpenAPI, Prisma, SQL DDL, GraphQL SDL, protobuf → intermediate representation | Feeds schema commons; upstream of Cohere/Formalize stages in software cascade |
| Back office UI | Operators view active state, pending gates, costs, and ledger | Read-heavy; gates require write path back to resolution; web-first |

## Recommended Project Structure

```
eclusa/
├── db/
│   ├── schema/             # Postgres DDL migrations (ordered, append-only)
│   │   ├── 001_domain.sql  # 9 core entities
│   │   ├── 002_ledger.sql  # append-only enforcement (no UPDATE/DELETE grants)
│   │   ├── 003_temporal_kg.sql
│   │   └── 004_schema_commons.sql
│   └── queries/            # Named SQL queries (no ORM — direct SQL)
│       ├── executor/       # ready stage polling, SKIP LOCKED claims
│       ├── ledger/         # trace chain queries, AS OF TIMESTAMP
│       └── temporal_kg/    # hybrid search, BFS traversal
│
├── executor/               # Stateless executor loop (~300-500 lines)
│   ├── loop.py             # poll → classify → dispatch → mark complete
│   ├── compute_types.py    # work_session | judgment_pass | fan_out routing
│   └── gate.py             # stage suspension, escalation
│
├── harness/
│   ├── native/             # Pydantic AI harness (direct DB access)
│   │   └── agent.py
│   └── claude_code/        # Claude Code backend harness adapter
│       └── adapter.py
│
├── proxy/                  # Outbound LLM call interceptor
│   ├── interceptor.py      # capture I/O, write artifact, forward call
│   └── model_swap.py       # portable message history, resume logic
│
├── cascade/
│   ├── graph.py            # cascade graph traversal, readiness detection
│   ├── templates/          # software construction cascade (6-stage), etc.
│   └── migration.py        # cascade shape migration as data migration
│
├── fan_out/
│   ├── dispatcher.py       # parallel dispatch to n models
│   └── convergence.py      # agreement detection → auto-resolve or gate
│
├── parsers/                # Schema parsers → intermediate representation
│   ├── openapi.py
│   ├── prisma.py
│   ├── sql_ddl.py
│   ├── graphql.py
│   └── protobuf.py
│
├── adapters/               # Integration layer
│   ├── slack.py
│   ├── whatsapp.py
│   └── email.py
│
├── search/                 # Hybrid search over temporal KG + schema commons
│   ├── cosine.py           # pgvector cosine similarity
│   ├── bm25.py             # full-text ranking
│   ├── bfs.py              # Postgres recursive CTE graph traversal
│   └── rerank.py           # result fusion
│
├── web/                    # Back office UI
│   ├── src/
│   │   ├── pages/
│   │   └── components/
│   └── vite.config.ts
│
└── docker-compose.yml      # db + executor + proxy + web + adapters
```

### Structure Rationale

- **db/**: DDL and named queries colocated; no ORM because Postgres recursive CTEs and SKIP LOCKED require direct SQL control
- **executor/**: Self-contained entry point; stateless by design; nothing here holds state between loop iterations
- **harness/ + proxy/**: Separated because two harness types share a single proxy contract; proxy is the artifact boundary
- **cascade/**: Graph logic separated from execution logic; cascade is a data structure, executor is a reader of it
- **fan_out/**: Separate from executor dispatch because convergence detection is a non-trivial operation with its own state (n in-flight completions)
- **adapters/**: Thin translation; any adapter failure should be isolated from core execution

## Architectural Patterns

### Pattern 1: DB-as-Execution-Engine (Postgres-Durable Execution)

**What:** All execution state lives in Postgres. The executor is a stateless polling loop. Crash at any point leaves the DB in a consistent state. On restart, the loop picks up where it left off by re-polling ready stages.

**When to use:** Always — this is Eclusa's foundational constraint. The DB is not a backing store for a workflow engine; it IS the workflow engine.

**Trade-offs:** Eliminates Temporal/Kafka/Redis as dependencies (high operational simplicity). Postgres SKIP LOCKED handles multi-executor contention without a coordination layer. The constraint is that stage transitions must be transactional DB writes — no in-memory state counts.

**Example:**
```sql
-- Claim a ready stage atomically; other executors skip locked rows
SELECT id, stage_type, cascade_id
FROM stage
WHERE status = 'ready'
  AND scheduled_at <= NOW()
ORDER BY scheduled_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

### Pattern 2: Three Compute Types (Topological Separation)

**What:** The system enforces three and only three compute primitives: work sessions (harness + tools), judgment passes (single completion, no tools), fan-out (n parallel passes). The executor classifies each stage into exactly one type before dispatch.

**When to use:** Every stage dispatch. The classification is topological — it comes from the cascade graph structure, not from runtime heuristics.

**Trade-offs:** Forces explicit up-front design of which stages use which models and tool access. Prevents the common anti-pattern of giving judgment passes tool access (which destroys evaluator independence). Fan-out stages cannot do tool calls mid-evaluation (concurrency hazard).

**Example:**
```python
def dispatch(stage):
    match stage.compute_type:
        case "work_session":
            harness.run(stage)          # tools allowed, cheap model, long-running
        case "judgment_pass":
            judgment.evaluate(stage)    # no tools, frontier model, single completion
        case "fan_out":
            fan_out.run(stage)          # n models, no tools, convergence check after
```

### Pattern 3: Proxy-Mediated Artifact Capture

**What:** Every outbound LLM call from a harness passes through a proxy that records the full request/response pair as an immutable artifact. The proxy also holds portable message history, enabling model swap between pause and resume without loss of context.

**When to use:** All harness-initiated LLM calls. Direct model calls (judgment passes) bypass the harness proxy but still record their completion via the executor's ledger write.

**Trade-offs:** Adds one network hop per LLM call (negligible vs. LLM latency). Enables post-hoc inspection, cost accounting, and model-swap — these are non-negotiable for the platform's audit requirements.

### Pattern 4: Gate-as-Suspension (Human-in-the-Loop)

**What:** When a stage cannot be resolved — ambiguity too high, fan-out diverged, risk threshold exceeded — the executor writes a gate record and suspends stage execution. The gate surfaces in the back office or adapter (Slack, etc.) for resolution. On resolution, the gate record is closed and the stage transitions to ready.

**When to use:** Whenever the system reaches a resolution boundary: fan-out models disagree, confidence below threshold, or a stage explicitly yields a gate.

**Trade-offs:** Introduces asynchronous latency (human response time). This is correct behavior — the system is designed to surface ambiguity upward, not paper over it.

### Pattern 5: Append-Only Ledger as Trace Chain

**What:** Every state transition writes to an append-only ledger table. No UPDATE or DELETE is permitted on this table (enforced via Postgres grant revocation, not application-level convention). Trace chain queries walk artifact → session → stage → cascade → intent using foreign key chains.

**When to use:** Every meaningful state change. The ledger is the authoritative record; domain entity tables are derived views of ledger state.

**Trade-offs:** Write amplification (every change = two writes: entity update + ledger insert). The operational cost is low; the auditability gain is essential.

```sql
-- AS OF TIMESTAMP query: what was the system state at a given moment?
SELECT *
FROM ledger_entry
WHERE entity_id = $1
  AND created_at <= $2::timestamptz
ORDER BY created_at DESC
LIMIT 1;
```

### Pattern 6: Bi-Temporal Knowledge Graph

**What:** The temporal KG stores facts with four timestamps: t_valid (when fact became true in the world), t_invalid (when fact ceased to be true), t_created (when Eclusa ingested this fact), t_expired (when Eclusa invalidated this ingestion). This enables retroactive corrections and historical queries independent of ingestion timing.

**When to use:** All domain knowledge that changes over time — team structure, project decisions, constraint history, capability evolution.

**Trade-offs:** Query complexity increases. Hybrid search (cosine + BM25 + BFS) over this structure requires careful index design. Simpler than maintaining a separate Neo4j graph while keeping Postgres as the operational DB.

## Data Flow

### Intent Ingestion Flow

```
External signal (Slack message / webhook / email)
    │
    ▼
Adapter (normalize to intent payload)
    │
    ▼
Postgres: INSERT intent + INSERT ledger_entry
    │
    ▼
Executor loop (LISTEN/NOTIFY wakes executor, or next poll cycle)
    │
    ▼
Executor: find or create cascade for intent
    │
    ▼
Executor: evaluate cascade graph → find ready stages
    │
    ▼
Executor: SELECT FOR UPDATE SKIP LOCKED → claim stage
    │
    ▼
Dispatch to compute primitive (work_session / judgment_pass / fan_out)
```

### Work Session Flow

```
Executor claims stage → creates work_session record
    │
    ▼
Harness starts (Pydantic AI or Claude Code backend)
    │
    ▼
Agent reasons → tool call → Proxy intercepts
    │                             │
    ▼                             ▼
LLM API call            artifact INSERT (request + response)
    │
    ▼
Tool result returned to agent
    │
    ▼
Agent produces output artifact
    │
    ▼
Session: status=complete, artifact_id recorded
    │
    ▼
Executor: stage status=complete → evaluate downstream readiness
```

### Fan-Out Evaluation Flow

```
Executor claims fan_out stage
    │
    ▼
Spawn n judgment passes in parallel (separate DB rows)
    │
    ▼
Each pass: single LLM completion, no tools, writes result
    │
    ▼
Convergence check: do n responses agree?
    │
    ├── YES → auto-resolve, write convergence artifact, mark stage complete
    │
    └── NO  → write divergence artifact, create GATE record, suspend stage
                    │
                    ▼
              Gate surfaces to human or higher-authority model
                    │
                    ▼
              Resolution recorded in ledger → stage resumes
```

### Cascade Shape Migration Flow

```
Intent: "evolve cascade shape while stages are running"
    │
    ▼
Write migration record (not runtime mutation)
    │
    ▼
In-flight stages: complete on original shape
    │
    ▼
Ledger records: transition epoch, both shapes preserved
    │
    ▼
New stages created under migrated shape
```

### Key Data Flows

1. **Ambiguity up:** Unresolvable items always flow upward — from work session to judgment pass, from judgment pass to fan-out, from fan-out divergence to human gate.
2. **Artifacts down:** Every compute primitive writes artifacts that downstream stages consume. Artifacts never flow laterally without passing through the ledger.
3. **State in DB only:** The executor carries no in-memory state between iterations. All coordination is via DB rows.
4. **Events via LISTEN/NOTIFY:** Gate resolutions, session completions, and external adapter events wake the executor via Postgres LISTEN/NOTIFY rather than requiring tight polling loops.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-10 concurrent cascades | Single executor process, single Postgres instance, docker-compose as specified — no changes needed |
| 10-100 concurrent cascades | Add executor replicas (SKIP LOCKED handles contention); connection pooling via PgBouncer; object storage scales independently |
| 100-1000 concurrent cascades | Read replicas for back office UI queries; partition ledger table by month; cache schema commons search results; consider Postgres read replicas for temporal KG queries |
| 1000+ concurrent cascades | Vertical Postgres scaling first (Postgres handles this range well); evaluate sharding only if single-instance saturates; DB-as-engine constraint means horizontal sharding requires careful transaction boundary analysis |

### Scaling Priorities

1. **First bottleneck:** LLM API rate limits and latency — not Postgres. Fan-out stages hit model provider limits before DB contention appears. Mitigation: model provider load balancing, fan-out size caps.
2. **Second bottleneck:** Hybrid search on temporal KG and schema commons at high read volume. Mitigation: pgvector HNSW index, BM25 via pg_search or tsvector, query result caching.
3. **Third bottleneck:** Executor poll interval at low stage volume wastes CPU; LISTEN/NOTIFY reduces this before it becomes an issue.

## Anti-Patterns

### Anti-Pattern 1: Agent Evaluates Its Own Output

**What people do:** Use the same model instance (or same session) to both produce and evaluate an artifact.

**Why it's wrong:** Confirmation bias is structural — the model has already committed to the output. Evaluation becomes rationalization. This is why judgment passes are topologically separated from work sessions.

**Do this instead:** Judgment passes receive only the artifact and prepared context. They have no tool access, no prior session history, and are dispatched by a separate executor claim. The evaluator literally cannot know it produced the input.

### Anti-Pattern 2: State in the Executor Process

**What people do:** Hold session state, running counts, or pending gate lists in executor memory between loop iterations.

**Why it's wrong:** A crashed executor loses this state permanently. The platform's crash-restart safety guarantee breaks. Under multi-executor deployment, two instances diverge silently.

**Do this instead:** Every piece of state that matters is a DB row. The executor is allowed to hold state only within a single transaction boundary — and even then, the DB row is written before any side effect.

### Anti-Pattern 3: Cascade Mutation at Runtime

**What people do:** Modify a running cascade's shape in-place — add stages, remove branches, change topology.

**Why it's wrong:** In-flight stages completed under the old shape write artifacts that downstream stages (now under a new shape) may not correctly consume. Trace chains break. The ledger records a shape that no longer matches what actually ran.

**Do this instead:** Write a migration record. In-flight stages complete on their original shape. The ledger records both shapes and the transition epoch. New stages are created under the migrated shape.

### Anti-Pattern 4: Relying on LISTEN/NOTIFY Alone for Durability

**What people do:** Treat Postgres LISTEN/NOTIFY as the reliable delivery mechanism for stage dispatch; skip the polling loop.

**Why it's wrong:** NOTIFY messages are lost if no listener is connected at emit time. An executor restart during a quiescent period will miss events that fired while it was down.

**Do this instead:** LISTEN/NOTIFY is a wake mechanism only. The executor always has a polling fallback. A stage that became ready while the executor was offline will be discovered on the next poll cycle regardless of whether a NOTIFY was delivered.

### Anti-Pattern 5: Giving Fan-Out Passes Tool Access

**What people do:** Allow fan-out evaluation passes to call tools (search, DB queries, external APIs) mid-evaluation.

**Why it's wrong:** Tool calls create side effects. N parallel passes calling the same tools create N×side effects, possible race conditions, and evaluation results that depend on which pass ran first rather than on independent model judgment.

**Do this instead:** Context preparation is a local stage that runs before the fan-out stage. All necessary context is assembled, stripped of noise, and written as an artifact. Fan-out passes receive only this prepared artifact.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM APIs (Anthropic, etc.) | Proxy-mediated HTTP; proxy sits between harness and API | Proxy captures I/O; model swap requires only message history portability |
| Slack | Bolt SDK webhook receiver; async queue before DB write | Immediate 200 OK to Slack; processing is async to avoid webhook timeout |
| WhatsApp | WhatsApp Business API webhook; same async pattern as Slack | Meta's webhook requires HTTPS and signature verification |
| Email | IMAP polling or SMTP webhook (SendGrid/Mailgun inbound); normalize to intent payload | Email threading maps to cascade continuation |
| Object storage (S3/compatible) | SDK client from harness; reference stored in session record | Only large blobs — LLM message histories, tool output files, workspace snapshots |
| Haskell GHC (constraint verification) | Shell subprocess from a stage; ghc -fno-code on LLM-drafted constraint file | GHC as structural gate; humans never see Haskell; stage captures stdout/stderr as artifact |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Adapter → Core | Postgres INSERT (intent + ledger_entry) | Adapters have DB write access only to intent and ledger tables |
| Executor → Harness | In-process function call (same Python process) or subprocess | Native harness is in-process; Claude Code backend is subprocess/API |
| Harness → LLM API | HTTP through proxy | Proxy is a local HTTP server or middleware intercept |
| Executor → DB | Direct psycopg (no ORM) | SKIP LOCKED requires direct SQL; recursive CTEs for cascade graph traversal |
| Back office UI → DB | Read-only Postgres connection + narrow write API for gate resolution | UI never writes directly to ledger; gate resolution goes through a validated API endpoint |
| Fan-out → Convergence | Postgres rows (each pass writes result); convergence check reads all n rows after completion | Convergence check is a local stage following the fan-out; not in the fan-out itself |

## Build Order (Phase Dependencies)

The components form a strict dependency DAG. Each phase must be buildable and testable independently before the next.

```
Phase 1: DB Foundation
  └── Schema DDL (9 entities, ledger, temporal KG, schema commons)
  └── Append-only enforcement (grants, triggers)
  └── Trace chain queries (validate via SQL)
  └── Basic SKIP LOCKED polling proof-of-concept

Phase 2: Executor + Cascade
  └── Depends on: Phase 1 (DB)
  └── Stateless executor loop (poll → claim → mark complete)
  └── Cascade graph traversal (recursive CTE readiness detection)
  └── Cascade migration as data migration

Phase 3: Compute Primitives
  └── Depends on: Phase 2 (executor dispatches to these)
  └── Work session lifecycle (start, pause, resume, swap, transfer)
  └── Judgment pass dispatch
  └── Fan-out + convergence detection
  └── Proxy layer (artifact capture, model-swap support)
  └── Native harness (Pydantic AI + direct DB)

Phase 4: Knowledge Layer
  └── Depends on: Phase 1 (pgvector schema)
  └── Parser layer (OpenAPI → IR, Prisma → IR, etc.)
  └── Temporal KG ingestion and edge invalidation
  └── Hybrid search (cosine + BM25 + BFS + rerank)

Phase 5: Adapters + Gates
  └── Depends on: Phase 3 (gates need compute primitives to suspend)
  └── Gate mechanism (suspension, escalation, resolution)
  └── Slack adapter (intent ingestion + gate surfacing)
  └── WhatsApp adapter
  └── Email adapter

Phase 6: Back Office + Self-Calibration
  └── Depends on: All prior phases (reads from all layers)
  └── Back office UI (cascades, gates, transcripts, costs, ledger queries)
  └── Self-calibration metrics (8 metrics)
  └── RBAC (gate resolution delegation)
  └── docker-compose single-command deployment
```

**Ordering rationale:**
- DB schema before all else — executor and harness are readers/writers of DB rows
- Executor before compute primitives — executor provides the dispatch contract; primitives implement it
- Compute primitives before adapters — adapters produce intents but only gates need resolving via adapters, which requires primitives to exist
- Knowledge layer can proceed in parallel with compute primitives (separate schema tables, no runtime dependency)
- Back office UI is last because it reads from every other layer; building it earlier would require stubs for unbuilt layers

## Sources

- [Why Postgres is a Good Choice for Durable Workflow Execution — DBOS](https://www.dbos.dev/blog/why-postgres-durable-execution) — SKIP LOCKED, checkpointing, exactly-once semantics (MEDIUM confidence — official blog post)
- [Absurd Workflows: Durable Execution With Just Postgres — Armin Ronacher](https://lucumr.pocoo.org/2025/11/3/absurd-workflows/) — minimal Postgres-only durable execution reference (HIGH confidence — detailed technical post, 2025)
- [AI Agent Orchestration Patterns — Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) — sequential, concurrent, fan-out/fan-in patterns (HIGH confidence — Microsoft official docs, updated 2026-02-12)
- [Zep: A Temporal Knowledge Graph Architecture for Agent Memory](https://arxiv.org/abs/2501.13956) — bi-temporal model with four timestamps (HIGH confidence — peer-reviewed arxiv paper, 2025)
- [Human-in-the-Loop Architecture — Agent Patterns](https://www.agentpatterns.tech/en/architecture/human-in-the-loop-architecture) — gate suspension, escalation tiers (MEDIUM confidence — community reference)
- [Kinde LLM Fan-Out 101: Self-Consistency, Consensus, and Voting Patterns](https://www.kinde.com/learn/ai-for-software-engineering/workflows/llm-fan-out-101-self-consistency-consensus-and-voting-patterns/) — fan-out implementation tactics, convergence/divergence handling (MEDIUM confidence)
- [Pydantic AI — Multi-Agent Patterns](https://ai.pydantic.dev/multi-agent-applications/) — harness architecture, stateful session management (HIGH confidence — official docs)

---
*Architecture research for: AI coordination platform (company operating system)*
*Researched: 2026-04-04*
