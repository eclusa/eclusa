# Stack Research

**Domain:** AI-powered organizational coordination platform (company operating system)
**Researched:** 2026-04-04
**Confidence:** HIGH (all versions verified via PyPI, npm, official docs)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12+ | Executor, API, adapters | 3.12 is the production sweet spot — 3.13 free-threading is still beta-adjacent for libraries. All core dependencies (pydantic-ai, asyncpg, FastAPI) support 3.10–3.14. |
| PostgreSQL | 17 | Primary data store | PG17 ships uni-temporal WITHOUT OVERLAPS for primary keys — first-class support for the temporal graph schema. PG18 adds full temporal constraints but is too new for production. PG17 is the safe current LTS target. |
| pgvector | 0.8.2 | Vector similarity search | Production-stable. HNSW iterative scans (added 0.8.0) prevent overfiltering on filtered queries — critical for schema_commons hybrid search. Supports Postgres 13+. |
| pydantic-ai | 1.77.0 | Native agent harness | Production/Stable as of April 2026. Type-safe, model-agnostic (Anthropic, OpenAI, Gemini, Mistral, etc.), built-in tool injection, durable execution for pause/resume. Directly aligned with the work_session harness model. |
| FastAPI | 0.135.3 | API layer (back office + adapter webhooks) | Async-first, Pydantic-native, auto-generated OpenAPI docs. Python 3.10+ required. Highest throughput among Python web frameworks. Powers both the back office REST API and adapter webhook receivers. |
| asyncpg | 0.31.0 | Async Postgres driver (executor hot path) | Fastest Python Postgres driver. Binary protocol, native asyncio. Use for the executor's SKIP LOCKED poll loop and fan-out dispatch where throughput matters. Supports PG 9.5–18. |
| psycopg | 3.3.3 | Async Postgres driver (general purpose) | Richer Postgres feature set than asyncpg. Native LISTEN/NOTIFY async — required for the executor's event-driven dispatch path. Pydantic row factories. Use as the primary driver everywhere except the innermost executor hot loop. |
| SQLAlchemy | 2.0.49 | ORM / schema declaration | Async-capable, Alembic integration, Pydantic-compatible. Use in declarative mode for schema definition; avoid ORM session for the executor (use raw psycopg/asyncpg there for predictability). |
| Alembic | 1.18.4 | Schema migrations | Standard companion to SQLAlchemy. Init with `-t async`. Handles the incremental schema evolution of all 9 domain entities without downtime. |
| React | 19 | Back office UI | Latest stable. shadcn/ui + Vite ecosystem targets React 18/19. Server components not needed — this is a SPA admin panel, not a content site. |
| Vite | 6.x | React build tooling | Fastest HMR. Standard pairing with shadcn/ui. No configuration overhead for a pure SPA. |
| TypeScript | 5.x | Type safety for UI | Non-negotiable for a data-dense admin panel with complex query responses. |

---

### Supporting Libraries

#### Data Layer

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pg_search (ParadeDB) | latest | BM25 full-text search in Postgres | Required for the hybrid search path in schema_commons: BM25 lexical + pgvector cosine + BFS graph, reranked with RRF. Install as a Postgres extension alongside pgvector. Production-stable. |
| pgqueuer | latest | Postgres-backed job queue | SKIP LOCKED semantics, asyncio-native, crash-safe. Use as the queue implementation backing the executor poll loop — or implement SKIP LOCKED directly if keeping the executor at ~300–500 lines matters more than a library. |

#### Python Backend

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 | Async HTTP client | Outbound calls from work sessions and judgment passes. Use AsyncClient with connection pooling. The proxy layer intercepts this traffic via mitmproxy. |
| mitmproxy | 11.x | Outbound call proxy | Python addon API for intercepting, logging, and capturing all LLM API calls from work sessions. Runs as a sidecar; agent harnesses route through it via HTTP_PROXY env variable. |
| slack-bolt | 1.27.x | Slack adapter | Bolt framework handles Events API, Socket Mode, and action callbacks. Native async support. The intent ingestion adapter is a Bolt app with event handlers that write to the Eclusa intents table. |
| twilio | 9.x | WhatsApp adapter | Twilio's Python SDK for WhatsApp Business API. Webhook-based: inbound messages POST to a FastAPI endpoint, which writes intents. Validate `X-Twilio-Signature` on all inbound webhooks. |
| aioimaplib | latest | Email ingestion (IMAP) | Async IMAP client for polling/pushing email intents. Use with aiosmtplib for outbound notifications. Alternative: configure an SMTP-to-webhook relay (simpler operationally). |
| aiosmtplib | 3.x | Email outbound notifications | Async SMTP send for gate surfacing via email. |
| pydantic | 2.x | Data validation | Already a transitive dependency of pydantic-ai and FastAPI. Use Pydantic models for all inter-layer DTOs, executor stage payloads, and API request/response schemas. |
| logfire | latest | Observability | Pydantic's observability product. First-class pydantic-ai integration — traces agent runs, tool calls, model tokens, latency. Use for the cost dashboard's raw data and for debugging fan-out convergence. |
| tenacity | 9.x | Retry logic | Exponential backoff for model API calls and outbound integrations. Lightweight, decorator-based. |

#### Front Office / UI

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn/ui | latest | UI component library | Unstyled, accessible, copy-owned components. Standard pairing with Vite + Tailwind. Use for all back office surfaces: cascade views, gate panels, ledger tables. |
| Tailwind CSS | 4.x | Styling | Zero-runtime CSS utility framework. v4 is the current stable. Works with shadcn/ui. |
| TanStack Query | 5.96.x | Server state management | Use for all back office data fetching: cascade list, pending gates, session transcripts, ledger queries. `manualPagination: true` for server-side paginated ledger views. |
| TanStack Table | 8.x | Data table | Server-side pagination and sorting for ledger queries and cost breakdowns. Headless — pairs cleanly with shadcn/ui table components. |
| Recharts | 3.8.x | Charts | Lightweight D3-backed SVG charts for the cost dashboard (token spend, gate latency, model convergence rate). No license cost. Composable components. |
| React Router | 6.x | SPA routing | Standard routing for the back office SPA. No SSR needed. |
| Zustand | 5.x | Local UI state | Lightweight global state for things that don't belong in TanStack Query (e.g., selected cascade, open panels). |

#### Infrastructure

| Library/Tool | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Docker Compose | v2.x | Single-command bootstrap | `docker-compose up` starts: postgres (+ pgvector + pg_search), executor, proxy (mitmproxy), web API, and adapter services. Health check with `pg_isready` gate before executor starts. |
| GHC (Haskell) | 9.10.x | Constraint compilation | Run via `ghc -fno-code` to type-check LLM-drafted Haskell constraint files without generating executables. Runs as a Docker sidecar — the executor invokes it via subprocess. Users never write Haskell; the LLM drafts it, GHC verifies it. |
| uv | latest | Python packaging | Fast, reproducible Python dependency management. Replace pip/venv. Use `uv add` (not `uv pip install`). |
| ruff | latest | Python linting/formatting | Replaces flake8, isort, black. Single tool, fast. |

---

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Dependency management, venv | `uv add pydantic-ai asyncpg fastapi` — never use `pip install` or `uv pip install` |
| ruff | Lint + format | `ruff check . && ruff format .` as pre-commit hook |
| pyright | Python type checking | Strict mode. pydantic-ai is fully typed; benefit is high. |
| alembic | Schema migrations | `alembic init -t async` for async-compatible env.py |
| pytest + pytest-asyncio | Test runner | `asyncio_mode = "auto"` in pytest.ini for async test functions |
| docker compose watch | Dev hot reload | `docker compose watch` for file-sync-based HMR without rebuilding images |

---

## Installation

```bash
# Python core (executor + API + adapters)
uv add pydantic-ai fastapi uvicorn[standard] asyncpg psycopg[binary,pool] sqlalchemy[asyncio] alembic httpx tenacity pydantic logfire

# Adapter SDKs
uv add slack-bolt twilio aioimaplib aiosmtplib

# Dev dependencies
uv add --dev pytest pytest-asyncio httpx ruff pyright

# mitmproxy (proxy sidecar — install separately or via Docker)
uv add mitmproxy

# React front office (in /ui directory)
npm create vite@latest ui -- --template react-ts
cd ui && npm install @tanstack/react-query @tanstack/react-table react-router-dom zustand recharts
npx shadcn@latest init
npm install tailwindcss @tailwindcss/vite
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| asyncpg (executor hot path) | psycopg (everywhere else) | Use asyncpg only in the inner executor poll loop for maximum throughput on SKIP LOCKED. Psycopg everywhere else for richer feature set. This is not either/or — both are used. |
| pg_search (ParadeDB) for BM25 | pg_textsearch (Timescale) | pg_textsearch is newer (early access Oct 2025) and may have better long-term Postgres alignment. ParadeDB pg_search is more mature and battle-tested. Revisit at Phase 4 (schema_commons hybrid search). |
| pgvector HNSW | IVFFlat | IVFFlat builds faster with lower memory but worse recall/speed tradeoff. Use HNSW for schema_commons (query-heavy). Use IVFFlat only if index build time is a blocker during early development. |
| pydantic-ai | LangChain / LangGraph | Never for this project. LangChain abstracts away the DB-as-execution-engine model; Eclusa's architecture IS the execution engine. Pydantic-ai is model-agnostic and stateless by default — correct fit. |
| FastAPI | Django / Flask | Flask is synchronous-first. Django adds too much ORM/admin overhead that conflicts with Eclusa's own DB model. FastAPI's async-first + Pydantic alignment is the right fit. |
| Vite + shadcn/ui (SPA) | Next.js | Next.js is correct for content sites and public-facing products needing SSR/SEO. The back office UI is internal, SPA, and data-dense — Vite wins on DX and simplicity. No SSR needed. |
| Twilio (WhatsApp) | Meta Cloud API (direct) | Direct Meta Cloud API requires more complex webhook handling and app review overhead. Twilio is the operational simplicity choice for a single-tenant deployment. Revisit if multi-tenant. |
| mitmproxy | Custom HTTPS proxy (aiohttp) | A custom proxy is ~300+ lines of careful TLS handling with no tooling. mitmproxy's addon API achieves the same in ~30 lines and handles TLS termination, connection reuse, and flow recording. |
| Recharts | Apache ECharts / Victory | ECharts is heavier; Victory has a smaller community. Recharts is the default shadcn/ui chart pairing and sufficient for a cost dashboard. |
| docker-compose | Kubernetes (k8s) | k8s is operationally out of scope. Single tenant, single instance — docker-compose is the right deployment primitive as stated in PROJECT.md constraints. |
| GHC sidecar (subprocess) | External verification service | Running GHC as a Docker sidecar invoked via subprocess keeps the architecture simple. A separate service would add a network boundary for no benefit. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| LangChain / LangGraph | Imposes its own execution engine (graph/chain abstractions) that conflicts with Eclusa's DB-as-execution-engine architecture. High abstraction leakage, difficult to audit traces, fast-moving breaking changes. | pydantic-ai for harness, raw FastAPI + asyncpg for executor |
| CrewAI / AutoGen | Designed for multi-agent autonomy without human-in-the-loop gates. Hardcodes role assumptions incompatible with Eclusa's topological work/judgment separation. | pydantic-ai with custom agent roles per stage type |
| Celery + Redis | Redis adds operational complexity that Postgres already handles via SKIP LOCKED. Celery's worker model is heavier than a 300–500 line stateless executor. | Native SKIP LOCKED executor with asyncpg/psycopg |
| Qdrant / Weaviate / Chroma | Separate vector DB services break the single-Postgres constraint from PROJECT.md. Operational complexity, synchronization risk, no ACID guarantees. | pgvector (already in Postgres) |
| Neo4j | Separate graph DB service. Recursive CTEs in Postgres handle the cascade graph traversal adequately at single-tenant scale. Adds operational overhead with no benefit until query patterns stabilize. | Postgres recursive CTEs + adjacency tables |
| Elasticsearch / OpenSearch | External dependency for BM25 search. Postgres with pg_search achieves the same with full ACID guarantees and no synchronization lag. | pg_search (ParadeDB) inside Postgres |
| psycopg2 | Deprecated in favor of psycopg3 (psycopg). psycopg2 is synchronous-only and lacks modern Postgres features. | psycopg 3.3.x |
| SQLModel | SQLModel merges SQLAlchemy and Pydantic in ways that create subtle issues with async sessions and Alembic migrations. Prefer explicit separation. | SQLAlchemy 2.0 (ORM) + Pydantic v2 (validation) separately |
| Flask | Synchronous-first, no native async, no Pydantic integration. In 2026 there is no reason to choose Flask for a new async-heavy project. | FastAPI |
| Temporal.io / Prefect | External durable execution frameworks. Eclusa's architecture deliberately places execution engine inside Postgres — the cascade graph IS the durable execution. These would duplicate/conflict with that. | Postgres SKIP LOCKED + LISTEN/NOTIFY |

---

## Stack Patterns by Layer

**Executor (the ~300–500 line core):**
- Raw asyncpg for the SKIP LOCKED poll loop
- psycopg for LISTEN/NOTIFY event subscription
- No SQLAlchemy in the executor hot path — direct SQL for predictability
- No pydantic-ai in the executor — it dispatches TO harnesses, it is not one

**Work session harness (Pydantic AI native):**
- pydantic-ai Agent with tool injection
- psycopg for direct DB access within the harness
- httpx AsyncClient routed through mitmproxy (set HTTP_PROXY env)
- logfire for tracing

**Judgment pass:**
- Direct model API call via pydantic-ai with `result_type` structured output
- No tools, no harness overhead
- Prepared context passed as single user message

**Fan-out evaluation:**
- N concurrent pydantic-ai calls (asyncio.gather)
- Convergence detection: compare structured outputs, hash or semantic diff
- Divergence threshold → write gate record to DB

**API layer (FastAPI):**
- AsyncSession (SQLAlchemy) for all query endpoints
- Pydantic response models
- Auth middleware (JWT, RBAC table in Postgres)
- WebSocket endpoint for live cascade updates

**Proxy layer (mitmproxy):**
- Python addon script (~30–50 lines)
- Intercepts all outbound HTTP from work sessions
- Writes request/response to artifact table via direct psycopg connection
- Runs on port 8080, set via HTTP_PROXY=http://proxy:8080 in session container env

**Bi-temporal knowledge graph:**
- Postgres 17 for uni-temporal WITHOUT OVERLAPS constraints (PK deduplication)
- Manual t_valid/t_invalid + t_created/t_expired columns for full bi-temporal (PG17 doesn't have system-time automation yet — that arrives in full form with PG18)
- Trigger-based system_time capture or application-level insert-only + effective_time columns
- Do not depend on temporal_tables extension — it has limited maintenance activity

**Hybrid search (schema_commons):**
- pgvector HNSW index for cosine similarity
- pg_search (ParadeDB) for BM25 lexical ranking
- Reciprocal Rank Fusion (RRF) in SQL for combining scores
- Optional BFS graph traversal via recursive CTE for community tier expansion
- No external reranker service — RRF + score blending is sufficient at single-tenant scale

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pydantic-ai 1.77.0 | pydantic 2.x, Python 3.10–3.14 | Do not mix pydantic v1 anywhere in the stack — pydantic-ai requires v2 |
| asyncpg 0.31.0 | Python 3.9–3.14, Postgres 9.5–18 | Use with uvloop for additional throughput gains |
| psycopg 3.3.3 | Python 3.10+, Postgres 10+ | psycopg[binary] for production, psycopg[c] for legacy C-extension path |
| SQLAlchemy 2.0.49 | Alembic 1.18.x, asyncpg, psycopg | Do NOT use SQLAlchemy 1.x — async support is SQLAlchemy 2.0 only |
| FastAPI 0.135.3 | Python 3.10+, Starlette 0.40.x, pydantic 2.x | Pin starlette version — FastAPI depends on specific Starlette versions |
| pgvector 0.8.2 | Postgres 13+ | Install via `CREATE EXTENSION vector` after pg_vector is compiled in |
| pg_search (ParadeDB) | Postgres 15+ | Not available for PG13/14 — PG17 target is fine |
| TanStack Query 5.96.x | React 18+ | v5 is a breaking change from v4 — do not mix |
| shadcn/ui | Tailwind CSS 4.x, React 18+/19 | Uses CSS variables for theming — requires Tailwind v4 for full support |

---

## Sources

- [pydantic-ai PyPI](https://pypi.org/project/pydantic-ai/) — version 1.77.0, Python >=3.10 confirmed (HIGH confidence)
- [pgvector GitHub](https://github.com/pgvector/pgvector) — version 0.8.2, Postgres 13+ confirmed (HIGH confidence)
- [FastAPI PyPI](https://pypi.org/project/fastapi/) — version 0.135.3, Python >=3.10 confirmed (HIGH confidence)
- [asyncpg PyPI](https://pypi.org/project/asyncpg/) — version 0.31.0, Postgres 9.5–18 confirmed (HIGH confidence)
- [psycopg PyPI](https://pypi.org/project/psycopg/) — version 3.3.3, Python >=3.10 confirmed (HIGH confidence)
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) — version 2.0.49 confirmed (HIGH confidence)
- [Alembic PyPI](https://pypi.org/project/alembic/) — version 1.18.4 confirmed (HIGH confidence)
- [TanStack Query npm](https://www.npmjs.com/package/@tanstack/react-query) — version 5.96.2 confirmed (HIGH confidence)
- [Recharts npm](https://www.npmjs.com/package/recharts) — version 3.8.1 confirmed (HIGH confidence)
- [ParadeDB pg_search](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) — BM25 in Postgres, PG15+ confirmed (MEDIUM confidence — production-stable but evolving)
- [PostgreSQL 17 temporal features](https://aiven.io/blog/two-dimensional-time-with-bitemporal-data) — WITHOUT OVERLAPS in PG17, full bi-temporal in PG18 (HIGH confidence)
- [mitmproxy docs](https://docs.mitmproxy.org/stable/) — Python addon API confirmed (HIGH confidence)
- [Slack Bolt Python](https://github.com/slackapi/bolt-python) — v1.27.x, async support confirmed (HIGH confidence)
- [Twilio WhatsApp Python](https://www.twilio.com/docs/whatsapp/api) — standard webhook pattern confirmed (HIGH confidence)
- [Psycopg3 vs asyncpg comparison](https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/) — LISTEN/NOTIFY advantage of psycopg3 (MEDIUM confidence — benchmark data varies)
- [shadcn/ui Vite templates](https://github.com/satnaing/shadcn-admin) — Vite + React + TypeScript + shadcn/ui confirmed as standard admin stack (HIGH confidence)
- [GHC Docker image](https://hub.docker.com/_/haskell/) — official Haskell/GHC Docker image confirmed (HIGH confidence); `-fno-code` flag is documented GHC behavior for type-check-only (MEDIUM confidence — verified via GHC docs search, not direct doc fetch)

---

*Stack research for: Eclusa — AI-powered organizational coordination platform*
*Researched: 2026-04-04*
