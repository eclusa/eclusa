# Phase 1: DB Foundation - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Postgres schema for all 9 domain entities, append-only ledger enforcement at the DB layer, trace chain queries via recursive CTEs, pgvector + pg_search extension setup, and three day-one correctness invariants verified before schema is frozen: (1) LISTEN/NOTIFY as wake-hint only, (2) `schema_version` on every ledger entry from first migration, (3) all 8 self-calibration metric formulas SQL-computable against the schema.

</domain>

<decisions>
## Implementation Decisions

### ID strategy
- **D-01:** All entity IDs are ULIDs — sortable by creation time, no coordination needed for generation
- **D-02:** ULIDs stored as `char(26)` or native UUID (ULID is UUID-compatible) — prefer native UUID type for index efficiency, generate as ULID for sortability

### Migration approach
- **D-03:** SQLAlchemy 2.0 declarative models for schema declaration only — never in executor hot path
- **D-04:** Alembic async for migration management with explicit migration history
- **D-05:** Every migration carries a version identifier used to populate `schema_version` on ledger entries created under that schema
- **D-06:** Direct SQL (asyncpg/psycopg) in the executor hot path, not ORM queries

### Ledger enforcement
- **D-07:** Dedicated application role (e.g., `eclusa_app`) with no UPDATE/DELETE grants on `ledger_entry` table
- **D-08:** Defense-in-depth trigger on `ledger_entry` that raises an exception on UPDATE/DELETE attempts, catching misuse even from privileged connections
- **D-09:** No soft-delete pattern — ledger entries are truly immutable; corrections are new entries with references to what they supersede

### Temporal column design
- **D-10:** Bi-temporal facts use four separate `timestamptz` columns: `t_valid`, `t_invalid`, `t_created`, `t_expired`
- **D-11:** PG17's WITHOUT OVERLAPS used for uni-temporal primary keys where applicable (e.g., entity validity periods)
- **D-12:** Range types (`tstzrange`) considered for future optimization but start with separate columns for clarity and portability

### Testing strategy
- **D-13:** pytest with real Postgres via testcontainers — no mocks for DB tests
- **D-14:** Seeded test data fixtures for verifying trace chain queries, ledger invariants, and metric computability
- **D-15:** All 8 self-calibration metric formulas expressed as SQL queries and verified to return correct results against seeded test data before schema is frozen

### Schema layout
- **D-16:** All 9 domain entities in a single `public` schema — no schema-per-domain until proven necessary
- **D-17:** Knowledge graph tables (episode, entity, fact, community) also in `public` — laid in Phase 1 for DDL completeness even though they are populated in Phase 4
- **D-18:** pgvector HNSW indexes on embedding columns created in Phase 1 DDL, even though embeddings are written in later phases

### Claude's Discretion
- Exact column naming conventions (snake_case assumed)
- Index strategy beyond HNSW (B-tree, GIN for JSONB columns)
- Constraint naming conventions
- Test fixture data generation approach
- Alembic migration naming convention

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain model specification
- `eclusa.md` 3 — Full domain model: all 9 entities with field definitions, types, relationships, and constraints
- `eclusa.md` 3.5 — Three compute types: work_session, judgment_pass, fan_out entity definitions
- `eclusa.md` 3.7 — Ledger entry: append-only invariant, no UPDATE/DELETE grants, ledger_type enum

### Temporal knowledge graph
- `eclusa.md` 4 — Temporal knowledge layer: episode/entity/fact/community tiers, bi-temporal model, edge invalidation
- `eclusa.md` 4.1 — Fact entity with t_valid/t_invalid/t_created/t_expired timestamps

### Executor contract
- `eclusa.md` 5.1 — Executor pseudocode: SKIP LOCKED query, LISTEN/NOTIFY, stage dispatch logic
- `eclusa.md` 5.2 — Stage dispatch patterns for all compute types

### Self-calibration metrics
- `eclusa.md` 9 — All 8 self-calibration metrics with definitions and what they feed back to

### Research findings
- `.eclusa/research/STACK.md` — Technology recommendations: PostgreSQL 17, pgvector 0.8.2, pg_search, asyncpg 0.31.0 + psycopg 3.3.3 dual-driver, SQLAlchemy 2.0 + Alembic
- `.eclusa/research/ARCHITECTURE.md` — Component boundaries, data flow, build order DAG
- `.eclusa/research/PITFALLS.md` — Day-one correctness invariants: LISTEN/NOTIFY dispatch, ledger schema_version, metric computability

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None — this phase establishes the foundational patterns

### Integration Points
- Phase 2 (Executor) will read the schema directly via asyncpg SKIP LOCKED queries
- Phase 3 (Compute Primitives) will write to work_session, judgment_pass, fan_out, artifact tables
- Phase 4 (Knowledge Layer) will write to episode, entity, fact, community tables
- Phase 6 (Self-Calibration) will run the 8 metric SQL queries against ledger data

</code_context>

<specifics>
## Specific Ideas

- The RFC defines exact entity schemas — follow them as specified in eclusa.md 3, not as abstract ERDs
- The executor pseudocode in eclusa.md 5.1 defines the exact SQL query pattern the schema must support
- The 8 self-calibration metrics in eclusa.md 9 define what aggregations the schema must support — their SQL-computability is an exit criterion, not a nice-to-have

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-db-foundation*
*Context gathered: 2026-04-04*
