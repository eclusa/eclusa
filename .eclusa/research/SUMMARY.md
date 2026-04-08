# Project Research Summary

**Project:** Eclusa — AI-powered organizational coordination platform
**Domain:** Company operating system / AI orchestration platform
**Researched:** 2026-04-04
**Confidence:** HIGH

## Executive Summary

Eclusa is an AI-powered coordination substrate, not a project management tool. Where Jira, Linear, and Notion manage work as free-form tickets, Eclusa represents work as a directed graph (cascade) of typed computation stages — each stage dispatched as one of three compute primitives: work session (tool-using harness), judgment pass (frontier model, no tools, evaluator independence enforced topologically), or fan-out evaluation (n models in parallel, model disagreement as the ambiguity signal). The platform's defining constraint is that Postgres IS the execution engine: all state lives in the database, the executor is a stateless SKIP LOCKED polling loop, and a crash at any point is safe by design. This eliminates all external workflow orchestrators (Temporal, Dagster, Kafka) as dependencies and concentrates operational complexity in a single well-understood system.

The recommended stack is Python 3.12+ with pydantic-ai 1.77.0 as the harness layer, asyncpg/psycopg dual-driver strategy for the executor hot path vs. general DB access, FastAPI 0.135.3 for the API layer, and React 19 + Vite + shadcn/ui for the back office SPA. Postgres 17 with pgvector 0.8.2 and pg_search (ParadeDB) handles all storage: domain entities, append-only ledger, bi-temporal knowledge graph, and hybrid vector/BM25/BFS search. All versions are verified stable as of April 2026. The only non-Postgres external runtime is a GHC Docker sidecar for Haskell constraint verification — invoked via subprocess, never in the critical path.

The primary risk profile is architectural, not functional: five patterns must be correct from day one or recovery cost is HIGH. LISTEN/NOTIFY used as the sole executor dispatch mechanism causes global Postgres lock contention under concurrent load; it must be layered on top of SKIP LOCKED polling from the first executor commit. The append-only ledger must include a `schema_version` field in its first migration or AS OF TIMESTAMP queries break on first schema change with no clean recovery path. Self-calibration metric computability must be verified against the schema before the schema is frozen — metrics are a data modeling concern in an event-sourced system, not an observability afterthought. These three are Phase 1 constraints. Fan-out convergence detection and proxy streaming are Phase 2 constraints. The build order is non-negotiable: DB schema before executor, executor before compute primitives, compute primitives before adapters and gates.

## Key Findings

### Recommended Stack

The stack is fully async Python on the backend, with a deliberate dual-driver strategy: asyncpg exclusively in the executor's SKIP LOCKED inner loop for maximum throughput, psycopg everywhere else for richer Postgres features including LISTEN/NOTIFY async support and Pydantic row factories. SQLAlchemy 2.0 is used only for schema declaration and Alembic migrations — never in the executor hot path where direct SQL gives predictability. The proxy layer uses mitmproxy's Python addon API (~30 lines) rather than a custom HTTPS proxy implementation. GHC 9.10.x runs as a Docker sidecar, invoked via subprocess; operators and users never write Haskell.

Key version constraints to respect: pydantic-ai requires pydantic v2 (no mixing); SQLAlchemy 2.0 only (async is not available in 1.x); pg_search requires Postgres 15+ (PG17 target is fine); TanStack Query v5 is a breaking change from v4. Do not use LangChain, CrewAI, Celery+Redis, separate vector DB services, or external workflow frameworks — each conflicts with the DB-as-execution-engine architectural constraint.

**Core technologies:**
- Python 3.12+: executor, API, adapters — 3.12 is the production sweet spot; 3.13 free-threading too beta-adjacent
- PostgreSQL 17: primary data store — PG17 ships WITHOUT OVERLAPS for temporal primary keys; single source of truth
- pgvector 0.8.2: vector similarity search — HNSW iterative scans prevent overfiltering on hybrid search queries
- pydantic-ai 1.77.0: harness layer — type-safe, model-agnostic, durable execution for pause/resume
- FastAPI 0.135.3: API layer — async-first, Pydantic-native, auto OpenAPI
- asyncpg 0.31.0 + psycopg 3.3.3: dual-driver executor strategy
- mitmproxy 11.x: proxy sidecar for artifact capture
- React 19 + Vite 6 + shadcn/ui: back office SPA — internal tool, no SSR needed
- GHC 9.10.x (Docker sidecar): Haskell constraint verification via `-fno-code`

### Expected Features

Eclusa's differentiation is structural, not cosmetic. The table-stakes features (status tracking, search, notifications, RBAC, audit log) map directly to cascade lifecycle, hybrid search, gate surfacing via adapters, decision delegation, and the append-only ledger — so building the core substrate satisfies most table-stakes requirements automatically. The unique differentiators — fan-out convergence detection, formal Haskell constraint verification, self-calibration metrics, bi-temporal knowledge graph — are high-complexity features that belong in later phases after the coordination substrate is proven.

**Must have (table stakes, satisfied by core substrate):**
- Work item creation and status tracking — intent + stage lifecycle covers this
- Dependency mapping — cascade graph edges are dependencies by nature
- Activity feed / audit log — append-only ledger provides this structurally
- Notifications (Slack/email/WhatsApp) — gate surfacing via adapters
- RBAC / decision delegation — who resolves which gates
- Single-command deployment — `docker-compose up` is already the target

**Should have (differentiators, post-validation):**
- Fan-out evaluation with convergence detection — model disagreement as ambiguity signal
- Schema commons (pgvector + parsers) — semantic grounding for intents
- Bi-temporal knowledge graph — "what was true on date X" queries
- Self-calibration metrics (8 signals) — system measures its own gate quality
- Cost dashboard per cascade/session — no PM tool offers this
- Model hot-swap between pause/resume — cost optimization via portable message history

**Defer (v2+):**
- GitHub/GitLab PR linkage — expected by software teams, not core to coordination semantics
- Roadmap / timeline view — useful but not blocking
- General analytics dashboards beyond cost
- Inbound webhook triggers for external intent origination

**Anti-features (explicitly excluded):**
- Real-time collaborative document editing — not a document editor
- Free-form ticket creation — bypasses ambiguity resolution pipeline
- External workflow framework dependency (Temporal, Dagster) — conflicts with DB-as-engine
- "AI autopilot" (no human gates) — removes the structural quality check

### Architecture Approach

Eclusa's architecture is defined by a single invariant: Postgres is the execution engine, not a backing store. The executor is a stateless poll loop that reads ready stages via SKIP LOCKED, classifies each into one of three compute types, and dispatches — nothing else. All coordination, all state transitions, all durability live in DB rows. This makes the system crash-safe at every point without an external coordination layer. The proxy layer (mitmproxy sidecar) intercepts all outbound LLM calls from harnesses, recording full request/response pairs as immutable artifacts and holding portable message history to enable model hot-swap between pause and resume. The integration layer (Slack, WhatsApp, email adapters) is a trust boundary — raw input never reaches the executor without an intermediate structuring step.

**Major components:**
1. Executor loop — stateless SKIP LOCKED poll, classifies and dispatches stages; ~300-500 lines; no framework
2. Work session harness — pydantic-ai agent with tool injection, proxy-mediated outbound calls
3. Judgment pass — single frontier model completion, no tools, topologically separated from work sessions
4. Fan-out evaluation — n parallel judgment passes, structured convergence detection, divergence surfaces as gate
5. Proxy layer — mitmproxy sidecar; artifact capture, model-swap support, SSE streaming pass-through required
6. Cascade graph — directed graph stored in Postgres; shape migrations are data writes, not runtime mutations
7. Gate mechanism — stage suspension with DB-backed state; resolves via adapter or back office UI
8. Temporal knowledge graph — four-timestamp bi-temporal facts (t_valid, t_invalid, t_created, t_expired)
9. Schema commons — pgvector HNSW + pg_search BM25 + Postgres recursive CTE BFS + RRF rerank
10. Back office UI — React SPA; active cascades, pending gates, session transcripts, cost dashboard, ledger queries

### Critical Pitfalls

1. **LISTEN/NOTIFY as sole executor dispatch** — causes global Postgres lock contention under concurrent write load; use SKIP LOCKED polling as the reliable baseline with NOTIFY as a wake-hint only; never issue NOTIFY inside a high-frequency write transaction. Address in Phase 1; impossible to retrofit cleanly.

2. **Ledger schema without `schema_version`** — AS OF TIMESTAMP queries silently produce wrong historical answers after any schema change; there is no clean recovery path on an append-only table; add `schema_version` to the first migration and all metric formulas must be verified computably against the schema before it is frozen. Address in Phase 1.

3. **Fan-out convergence on unstructured prose** — embedding similarity produces both false-positive gates (same answer, different words) and false-negative auto-resolves (different answers, similar phrasing); judgment pass outputs must have an enforced JSON schema; convergence detection compares structured fields, not full text. Address in Phase 2.

4. **Proxy artifact write in the critical request path** — adds latency on every LLM call and becomes a single point of failure; artifact DB write must be async (non-blocking); proxy must handle SSE streaming without buffering; test with 10 concurrent sessions before connecting to production harnesses. Address in Phase 2.

5. **Recursive CTEs without cycle guards** — a single malformed cascade record causes executor to hang indefinitely; every recursive CTE touching the graph must include a `CYCLE` clause (Postgres 14+) and a hard depth limit parameter from day one. Address in Phase 1.

## Implications for Roadmap

Based on combined research, the build order is a strict dependency DAG. There is no discretion in the ordering: DB schema must precede executor, executor must precede compute primitives, compute primitives must precede adapters and gates. The knowledge layer (schema commons, temporal KG) can proceed in parallel with compute primitives since it uses separate schema tables with no runtime dependency on the executor. The back office UI is last because it is a reader of every other layer.

### Phase 1: DB Foundation and Ledger

**Rationale:** All other components are readers or writers of Postgres rows. Nothing can be built or meaningfully tested until the schema exists and its invariants are enforced. Three day-one correctness decisions live here with no clean retroactive fix: `schema_version` on the ledger, CYCLE guards on all recursive CTEs, and metric computability verification before the schema is frozen.
**Delivers:** 9-entity domain schema with Alembic migrations; append-only ledger with UPDATE/DELETE grant revocation; trace chain and AS OF TIMESTAMP queries; basic SKIP LOCKED proof-of-concept; all 8 self-calibration metric formulas verified as SQL-computable against seeded test data; temporal KG and schema commons schema DDL.
**Addresses:** Activity feed/audit log (structural); status tracking (via stage lifecycle schema); dependency mapping (cascade graph schema).
**Avoids:** LISTEN/NOTIFY lock contention (Pitfall 1); ledger schema evolution fidelity loss (Pitfall 4); self-calibration metric computability failure (Pitfall 10); recursive CTE infinite loops (Pitfall 2).

### Phase 2: Executor and Cascade

**Rationale:** Executor is the dispatch contract that all compute primitives implement. Without it, work sessions and judgment passes have no caller. The executor loop is also where the LISTEN/NOTIFY hybrid pattern must be correct — polling as baseline, NOTIFY as hint.
**Delivers:** Stateless executor loop (~300-500 lines) with SKIP LOCKED; cascade graph traversal via recursive CTEs with CYCLE guards; cascade migration as data migration; LISTEN/NOTIFY as wake-hint layered on polling.
**Addresses:** Work item status tracking (stage lifecycle transitions); dependency resolution (cascade graph readiness detection).
**Avoids:** LISTEN/NOTIFY as sole dispatch (Pitfall 1); state in executor process (Architecture anti-pattern 2); cascade runtime mutation (Architecture anti-pattern 3).

### Phase 3: Compute Primitives

**Rationale:** The three compute types are independent implementations that share the executor dispatch contract. They can be built and tested in parallel. The proxy layer belongs here because work sessions cannot run without it — and the proxy's async write path and SSE streaming support must be correct before any real session load.
**Delivers:** Work session lifecycle (start, pause, resume, model hot-swap, transfer); pydantic-ai native harness; judgment pass dispatch (single frontier model completion, structured output schema); fan-out evaluation (n parallel passes, structured convergence detection, gate on divergence); mitmproxy proxy layer with async artifact write and SSE streaming pass-through; canonical internal message format for model-provider portability.
**Addresses:** Fan-out evaluation (differentiator P1); judgment pass dispatch (P1); proxy artifact capture (P2); model hot-swap (P2).
**Avoids:** Fan-out convergence on unstructured prose (Pitfall 5); proxy as synchronous bottleneck (Pitfall 6); message history portability breaking on hot-swap (Pitfall 8); fan-out passes with tool access (Architecture anti-pattern 5).

### Phase 4: Knowledge Layer

**Rationale:** Schema commons and temporal KG enhance semantic grounding but do not block the coordination substrate. Their schema DDL is laid in Phase 1; this phase implements the runtime ingestion, parsers, and hybrid search pipeline. Runs in parallel with Phase 3 if capacity allows (no runtime dependency between them), but must follow Phase 1.
**Delivers:** Parser layer for five schema formats (OpenAPI, Prisma, SQL DDL, GraphQL SDL, protobuf) producing a canonical IR; temporal KG ingestion with four-timestamp bi-temporal facts and edge invalidation; hybrid search pipeline (pgvector HNSW cosine + pg_search BM25 + Postgres recursive CTE BFS + RRF rerank); pgvector HNSW index benchmarked at 1M vectors before hybrid search pipeline is declared production-ready.
**Addresses:** Search across work (table stakes); schema commons hybrid search (differentiator P2); temporal knowledge graph (differentiator P2).
**Avoids:** pgvector HNSW memory pressure (Pitfall 3); schema commons embedding backfill on schema revision (Performance Traps).

### Phase 5: Adapters and Gates

**Rationale:** Adapters are the primary user interface (80% of users never open the back office). They require compute primitives to exist because gate surfacing pauses real stages. This is also the widest attack surface — adapters are the first trust boundary for raw external input and must treat all incoming messages as minimum-privilege raw text with a sanitization step before executor ingestion.
**Delivers:** Gate mechanism (suspension, escalation tiers, DB-backed state, resolution signal); Slack adapter (intent ingestion + gate surfacing via Bolt SDK); WhatsApp adapter (webhook with signature verification, idempotent ingestion); email adapter (IMAP polling or SMTP webhook); adapter-level prompt injection defenses (structured extraction step, rate limiting, injection-aware system prompt); RBAC / decision delegation (who resolves which gates).
**Addresses:** Gate surfacing (P1); Slack adapter (P1); RBAC (P1); WhatsApp/email adapters (P2).
**Avoids:** Adapter prompt injection (Pitfall 9); adapter treating Slack threads as cascade nesting (Integration Gotcha); WhatsApp duplicate delivery creating duplicate intents (Integration Gotcha).

### Phase 6: Back Office UI and Self-Calibration

**Rationale:** The UI is a reader of every prior layer. Building it last avoids stubs for unbuilt layers and ensures the data model is stable before UI contracts are set. Self-calibration metrics require ledger history, fan-out data, and gate history — all of which only exist after Phases 1-5 have accumulated real run data.
**Delivers:** React 19 + Vite + shadcn/ui back office SPA (active cascades, pending gates, session transcripts, cost dashboard, ledger queries with pre-built AS OF templates, self-calibration metrics dashboard); docker-compose single-command deployment with all services; all 8 self-calibration metrics computed and displayed; cost dashboard showing cost per cascade/session/model with trend graphs; WebSocket endpoint for live cascade updates.
**Addresses:** Back office UI (P1); `docker-compose up` bootstrap (P1); cost dashboard (P2); self-calibration metrics (P2).
**Avoids:** Ledger query UI requiring SQL knowledge (UX Pitfall); cost dashboard showing raw token counts (UX Pitfall); gate resolution UI showing full transcripts without structured decision highlight (UX Pitfall).

### Phase 7 (Optional): Software Construction Cascade + Haskell Verification

**Rationale:** The software construction cascade (Refine → Match → Cohere → Formalize → Derive → Generate) is Eclusa's primary dogfood use case. The Haskell GHC constraint gate adds formal verification to the Formalize stage. Both are high-value but narrow-use-case features that belong after the platform is proven on general coordination work.
**Delivers:** Six-stage software construction cascade template; Haskell constraint verification via async GHC subprocess (with semaphore cap, timeout, and error-verbatim retry); Claude Code backend harness adapter.
**Addresses:** Software construction cascade template (P2); Haskell constraint verification (P3).
**Avoids:** GHC gate blocking executor (Pitfall 7); LLM retry loop on compilation failure without verbatim error inclusion.

### Phase Ordering Rationale

- DB schema before everything: executor, harnesses, and adapters are all DB readers/writers; they cannot be built or meaningfully tested against stubs
- Executor before compute primitives: executor is the dispatch contract; primitives implement it; inverting this order means primitives have no caller to test against
- Compute primitives before adapters: adapters write intents, but gates require compute primitives to suspend real stages; building adapters first means testing against stubs that cannot produce real gate behavior
- Knowledge layer parallel to compute primitives: schema commons and temporal KG are separate schema tables with no runtime dependency on executor dispatch; they can be built concurrently if team capacity allows, but must follow Phase 1
- Back office last: it reads from every other layer; building earlier requires stubs that obscure integration bugs
- Three pitfalls have no recovery path if missed in Phase 1: LISTEN/NOTIFY dispatch model, `schema_version` on ledger, metric computability verification — these are listed explicitly in Phase 1 deliverables, not as suggestions

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Compute Primitives):** Proxy SSE streaming pass-through with mitmproxy and pydantic-ai concurrent session behavior have limited production documentation; recommend `/eclusa:research-phase` before implementation planning
- **Phase 4 (Knowledge Layer):** pg_search (ParadeDB) BM25 integration and RRF reranking in Postgres have medium-confidence documentation; benchmark characteristics at target scale need validation before pipeline is designed
- **Phase 5 (Adapters):** Prompt injection defenses for LLM-mediated adapter ingestion are an active research area with evolving best practices; adversarial testing plan needs specification before implementation
- **Phase 7 (Haskell/GHC):** GHC LLM first-pass compile success rate under real constraint prompts is a single low-confidence community source; measure before committing to this phase

Phases with standard patterns (skip research-phase):
- **Phase 1 (DB Foundation):** Postgres SKIP LOCKED, Alembic async migrations, pgvector schema — all well-documented with HIGH-confidence sources
- **Phase 2 (Executor):** Stateless SKIP LOCKED executor is a well-established pattern; Armin Ronacher's reference implementation is detailed and high-confidence
- **Phase 6 (Back Office UI):** Vite + React + shadcn/ui + TanStack Query SPA stack is fully standard; no novel patterns; skip research-phase

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via PyPI, npm, official docs; version compatibility table cross-checked |
| Features | MEDIUM-HIGH | Table stakes well-documented via Jira/Linear/Notion official sources; novel AI coordination differentiators have fewer analogues; competitive frame is solid |
| Architecture | HIGH | Core patterns (SKIP LOCKED executor, bi-temporal KG, fan-out evaluation) all grounded in peer-reviewed or official sources; Eclusa-specific topology is novel but each component has verified precedent |
| Pitfalls | HIGH | Most critical pitfalls cross-verified via multiple sources; LISTEN/NOTIFY contention verified via production incident + pgdog + community; HNSW memory via Crunchy Data (official pgvector contributor); ledger schema evolution via multiple event-sourcing post-mortems |

**Overall confidence:** HIGH

### Gaps to Address

- **pg_search (ParadeDB) production scale characteristics:** Confidence is MEDIUM; hybrid search pipeline design should include a benchmark target (1M entities, realistic write/read ratio) before committing to BM25 implementation details. Flag for Phase 4 planning.
- **GHC LLM first-pass compile success rate:** Single low-confidence community discussion; measure empirically with the actual constraint prompt template before deciding whether Haskell verification is worth the complexity. Flag for Phase 7 specification.
- **Fan-out cost at frontier model pricing:** Fan-out with 3+ frontier models is expensive; the cost optimization strategy (start with 2 models, escalate to 3 on borderline divergence) needs a concrete policy before Phase 3 implementation. Cross-reference with self-calibration "fan-out necessity" metric.
- **Multi-executor concurrency under real load:** SKIP LOCKED behavior with 3+ concurrent executor replicas is documented but not benchmarked for this specific schema shape; include a multi-executor load test as a Phase 2 exit criterion.
- **Canonical message format spec:** The internal message format that enables provider-agnostic model hot-swap must be designed before any harness integration (Phase 3). This is an underdocumented area — the solution is clear (canonical format with translation shims) but the specific schema needs to be specified in Phase 3 planning.

## Sources

### Primary (HIGH confidence)
- [pydantic-ai PyPI](https://pypi.org/project/pydantic-ai/) — version 1.77.0, Python >=3.10
- [pgvector GitHub](https://github.com/pgvector/pgvector) — version 0.8.2, HNSW iterative scans
- [FastAPI PyPI](https://pypi.org/project/fastapi/) — version 0.135.3
- [asyncpg PyPI](https://pypi.org/project/asyncpg/) — version 0.31.0
- [psycopg PyPI](https://pypi.org/project/psycopg/) — version 3.3.3
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) — version 2.0.49
- [Postgres docs: WITH Queries (CYCLE clause)](https://www.postgresql.org/docs/current/queries-with.html) — recursive CTE cycle detection
- [Crunchy Data: HNSW Indexes with pgvector](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector) — HNSW memory and write characteristics
- [Zep: Temporal Knowledge Graph Architecture (arXiv 2501.13956)](https://arxiv.org/abs/2501.13956) — bi-temporal four-timestamp model
- [Absurd Workflows: Durable Execution With Just Postgres — Armin Ronacher](https://lucumr.pocoo.org/2025/11/3/absurd-workflows/) — Postgres-only durable execution reference
- [AI Agent Orchestration Patterns — Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) — sequential, concurrent, fan-out/fan-in patterns
- [Pydantic AI: Multi-Agent Patterns](https://ai.pydantic.dev/multi-agent-applications/) — harness architecture
- [Jira Software Features](https://www.atlassian.com/software/jira/features) — competitive baseline
- [Notion Product Overview](https://www.notion.com/product/ai) — competitive baseline
- [Slack Bolt Python](https://github.com/slackapi/bolt-python) — async support, Events API
- [PostgreSQL 17 temporal features](https://aiven.io/blog/two-dimensional-time-with-bitemporal-data) — WITHOUT OVERLAPS in PG17
- [mitmproxy docs](https://docs.mitmproxy.org/stable/) — Python addon API

### Secondary (MEDIUM confidence)
- [Why Postgres is Good for Durable Workflow Execution — DBOS](https://www.dbos.dev/blog/why-postgres-durable-execution) — SKIP LOCKED, checkpointing
- [Recall.ai: Postgres LISTEN/NOTIFY does not scale](https://www.recall.ai/blog/postgres-listen-notify-does-not-scale) — production incident confirming lock contention
- [PgDog: Scaling Postgres LISTEN/NOTIFY](https://pgdog.dev/blog/scaling-postgres-listen-notify) — lock contention corroboration
- [Alex Jacobs: The Case Against pgvector](https://alex-jacobs.com/posts/the-case-against-pgvector/) — HNSW scale thresholds
- [Chris Kiehl: Event Sourcing is Hard](https://chriskiehl.com/article/event-sourcing-is-hard) — ledger schema evolution pitfalls
- [Event Sourcing Production Anti-Patterns: Schema Evolution](https://www.youngju.dev/blog/architecture/2026-03-07-architecture-event-sourcing-cqrs-production-patterns.en) — schema_version pattern
- [Psycopg3 vs asyncpg comparison](https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/) — LISTEN/NOTIFY advantage
- [ParadeDB pg_search: Hybrid Search in PostgreSQL](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) — BM25 in Postgres, PG15+
- [Orq.ai: Why Multi-Agent LLM Systems Fail](https://orq.ai/blog/why-do-multi-agent-llm-systems-fail) — fan-out and convergence failure modes
- [Kinde: LLM Fan-Out 101](https://www.kinde.com/learn/ai-for-software-engineering/workflows/llm-fan-out-101-self-consistency-consensus-and-voting-patterns/) — convergence/divergence handling
- [ISACA: The Looming Authorization Crisis](https://www.isaca.org/resources/news-and-trends/industry-news/2025/the-looming-authorization-crisis-why-traditional-iam-fails-agentic-ai) — agentic AI permission escalation
- [Human-in-the-Loop Architecture — Agent Patterns](https://www.agentpatterns.tech/en/architecture/human-in-the-loop-architecture) — gate suspension, escalation tiers
- [Linear Features](https://linear.app/features) — competitive baseline
- [shadcn/ui Vite admin templates](https://github.com/satnaing/shadcn-admin) — standard admin SPA stack

### Tertiary (LOW confidence)
- [Haskell Community: GHC type errors and LLMs](https://discourse.haskell.org/t/the-fastest-way-to-feed-ghc-type-errors-to-llm/13827) — GHC first-pass compile success rate; community discussion, not production data; measure empirically

---
*Research completed: 2026-04-04*
*Ready for roadmap: yes*
