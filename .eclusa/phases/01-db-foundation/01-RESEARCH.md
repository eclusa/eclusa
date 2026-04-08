# Phase 1: DB Foundation - Research

**Researched:** 2026-04-04
**Domain:** PostgreSQL 17 schema design, append-only ledger enforcement, recursive CTE trace chains, bi-temporal knowledge graph, pgvector + pg_search extension setup, Alembic async migrations
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**ID strategy**
- D-01: All entity IDs are ULIDs — sortable by creation time, no coordination needed for generation
- D-02: ULIDs stored as `char(26)` or native UUID (ULID is UUID-compatible) — prefer native UUID type for index efficiency, generate as ULID for sortability

**Migration approach**
- D-03: SQLAlchemy 2.0 declarative models for schema declaration only — never in executor hot path
- D-04: Alembic async for migration management with explicit migration history
- D-05: Every migration carries a version identifier used to populate `schema_version` on ledger entries created under that schema
- D-06: Direct SQL (asyncpg/psycopg) in the executor hot path, not ORM queries

**Ledger enforcement**
- D-07: Dedicated application role (e.g., `eclusa_app`) with no UPDATE/DELETE grants on `ledger_entry` table
- D-08: Defense-in-depth trigger on `ledger_entry` that raises an exception on UPDATE/DELETE attempts, catching misuse even from privileged connections
- D-09: No soft-delete pattern — ledger entries are truly immutable; corrections are new entries with references to what they supersede

**Temporal column design**
- D-10: Bi-temporal facts use four separate `timestamptz` columns: `t_valid`, `t_invalid`, `t_created`, `t_expired`
- D-11: PG17's WITHOUT OVERLAPS used for uni-temporal primary keys where applicable (e.g., entity validity periods)
- D-12: Range types (`tstzrange`) considered for future optimization but start with separate columns for clarity and portability

**Testing strategy**
- D-13: pytest with real Postgres via testcontainers — no mocks for DB tests
- D-14: Seeded test data fixtures for verifying trace chain queries, ledger invariants, and metric computability
- D-15: All 8 self-calibration metric formulas expressed as SQL queries and verified to return correct results against seeded test data before schema is frozen

**Schema layout**
- D-16: All 9 domain entities in a single `public` schema — no schema-per-domain until proven necessary
- D-17: Knowledge graph tables (episode, entity, fact, community) also in `public` — laid in Phase 1 for DDL completeness even though they are populated in Phase 4
- D-18: pgvector HNSW indexes on embedding columns created in Phase 1 DDL, even though embeddings are written in later phases

### Claude's Discretion
- Exact column naming conventions (snake_case assumed)
- Index strategy beyond HNSW (B-tree, GIN for JSONB columns)
- Constraint naming conventions
- Test fixture data generation approach
- Alembic migration naming convention

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHEMA-01 | Postgres schema for all 9 domain entities (intent, actor, cascade, stage, work_session, judgment_pass, fan_out, artifact, ledger_entry) | Field-by-field schema from RFC eclusa.md §3 + §3.5–3.7; entities cross-referenced with executor query contract in §5.1 |
| SCHEMA-02 | Ledger table has no UPDATE/DELETE grants for application roles (append-only enforcement) | D-07 + D-08 locked: REVOKE grants + defense-in-depth trigger; PITFALLS.md §Pitfall 4 details exact trigger pattern |
| SCHEMA-03 | Every ledger_entry carries a `schema_version` field from first migration | D-05 locked; PITFALLS.md §Pitfall 4 warns this cannot be retrofitted; must be in the first Alembic revision |
| SCHEMA-04 | Trace chain query returns full path: artifact → session → stage → cascade → intent | Foreign key chain is explicit in §3.6 artifact schema; recursive CTE pattern in ARCHITECTURE.md |
| SCHEMA-05 | AS OF TIMESTAMP queries return ledger state at any historical moment | `created_at` ordering on ledger_entry; example query in ARCHITECTURE.md §Pattern 5 |
| SCHEMA-06 | All self-calibration metric formulas are computable from the schema before it is frozen | 8 metric definitions in eclusa.md §9; D-15 requires SQL queries verified against seeded data |
| SCHEMA-07 | pgvector extension installed with HNSW indexes on embedding columns | D-18 locked; pgvector 0.8.2 on PG17; HNSW on all `vector(1024)` columns |
| SCHEMA-08 | RBAC as decision delegation — actor permissions define who resolves which gates | Note: traceability table shows SCHEMA-08 is Phase 5; actor.permissions (jsonb) is laid in Phase 1 DDL |
| INFRA-02 | Single Postgres instance for all data (domain entities, embeddings, knowledge graph, ledger) | All 9 domain + 4 KG tables in same DB; pg_search + pgvector extensions in same instance |
| INFRA-04 | pg_search (ParadeDB) for BM25 full-text search inside Postgres | STACK.md confirms ParadeDB pg_search on PG17; extension install in docker-compose |

</phase_requirements>

---

## Summary

Phase 1 is pure data modeling and infrastructure bootstrapping. There is no application code written here — only SQL DDL, Alembic migrations, test fixtures, and docker-compose configuration. The output is a running, seeded Postgres instance from which the executor (Phase 2) can read without modification.

The most important insight for planning: three day-one correctness invariants have no retroactive fix path. (1) `schema_version` on every `ledger_entry` row must be in the first migration — adding it later requires mutating immutable records, which violates the ledger guarantee. (2) LISTEN/NOTIFY must be a wake-hint layered on top of SKIP LOCKED polling from the start — retrofitting this after the executor is built around NOTIFY-as-guarantee is architecturally invasive. (3) All 8 self-calibration metric formulas must be verified as SQL-computable against the actual schema before the schema is frozen — adding a required field retroactively means mutating the append-only ledger. These three invariants are the exit criteria for the phase, not aspirational goals.

The schema itself is well-specified in the canonical RFC (eclusa.md §3, §4, §5.1). All 9 domain entities have exact field definitions. The knowledge graph (episode, entity, fact, community) tables are laid in Phase 1 DDL even though they are populated in Phase 4 — this avoids a later migration that would touch tables already in use. The executor query contract (SKIP LOCKED pattern from §5.1) must be readable from the schema as designed — verify this before freezing.

**Primary recommendation:** Begin with the Alembic migration history structure and `schema_version` injection before writing any entity DDL. The versioned envelope on `ledger_entry` is the load-bearing constraint all other tables depend on.

---

## Standard Stack

### Core (Phase 1 specific)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PostgreSQL | 17 | Primary data store + execution engine | PG17 ships WITHOUT OVERLAPS for uni-temporal PKs (D-11 uses this); PG17 is current LTS; all extensions (pgvector 0.8.2, pg_search) require PG15+ |
| pgvector | 0.8.2 | Vector similarity search | HNSW iterative scans added in 0.8.0 prevent overfiltering on filtered queries; production-stable; D-18 requires HNSW indexes created in Phase 1 DDL |
| pg_search (ParadeDB) | latest | BM25 full-text search | Required by INFRA-04; runs inside Postgres — no external service; PG17 compatible |
| SQLAlchemy | 2.0.49 | Schema declaration / model definitions | D-03 locks this; Alembic integration; async support; use declarative mode only |
| Alembic | 1.18.4 | Migration management | D-04 locks this; `alembic init -t async` for async-compatible env.py; pairs exactly with SQLAlchemy 2.0 |
| asyncpg | 0.31.0 | Async Postgres driver (executor hot path) | D-06 locks direct SQL; asyncpg is fastest Python PG driver; binary protocol |
| psycopg | 3.3.3 | Async Postgres driver (general + LISTEN/NOTIFY) | Native async LISTEN/NOTIFY required for wake-hint pattern; richer feature set for non-hot-path use |
| python-ulid | current | ULID generation | D-01/D-02: ULIDs as sortable IDs stored as UUID; `python-ulid` generates ULIDs, `str(ulid)` gives 26-char string, `.uuid` gives UUID-compatible value |

### Testing Stack

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | current | Test runner | D-13 locks this; all Phase 1 tests |
| pytest-asyncio | current | Async test support | `asyncio_mode = "auto"` in pytest.ini; required for async DB tests |
| testcontainers | current | Real Postgres in tests | D-13 locks this — no mocks for DB tests; `PostgresContainer` spins a real PG17 instance per test session |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| char(26) ULID | native UUID | D-02 decided: prefer UUID type for index efficiency; generate as ULID for sortability |
| SQLAlchemy declarative | Raw SQL DDL only | SQLAlchemy gives Alembic autogenerate; but raw SQL is more readable for complex temporal constraints — use SQLAlchemy for basic entities, raw SQL in migration files for complex constraints |
| testcontainers | pg_temp / pytest-postgresql | testcontainers gives a real Docker-based Postgres with same extensions as prod; no extension management surprises |
| HNSW on all vector columns | HNSW only on query-heavy columns | D-18 decided: HNSW everywhere from Phase 1 DDL; embedding write path comes later |

**Installation:**
```bash
# From project root
uv add sqlalchemy[asyncio] alembic asyncpg "psycopg[binary,pool]" python-ulid

# Dev dependencies
uv add --dev pytest pytest-asyncio testcontainers[postgres]

# Initialize Alembic with async template
alembic init -t async alembic
```

---

## Architecture Patterns

### Recommended Project Structure (Phase 1 scope)

```
eclusa/
├── db/
│   ├── models/              # SQLAlchemy 2.0 declarative models (schema declaration)
│   │   ├── __init__.py
│   │   ├── base.py          # declarative_base(), common columns (id, created_at)
│   │   ├── domain.py        # intent, actor, cascade, stage, artifact, ledger_entry, tool
│   │   ├── compute.py       # work_session, judgment_pass, fan_out
│   │   └── knowledge.py     # episode, entity, fact, community (KG tables)
│   └── queries/             # Named SQL query files (no ORM)
│       ├── trace_chain.sql  # artifact → session → stage → cascade → intent
│       ├── as_of.sql        # AS OF TIMESTAMP ledger query
│       └── metrics/         # One .sql file per self-calibration metric
│           ├── gate_necessity.sql
│           ├── orchestrator_absorption.sql
│           ├── resolution_latency.sql
│           ├── decision_durability.sql
│           ├── cascade_rework.sql
│           ├── model_convergence.sql
│           ├── minority_accuracy.sql
│           └── fanout_necessity.sql
├── alembic/
│   ├── env.py               # async-compatible env.py (alembic init -t async)
│   ├── script.py.mako       # migration template — injects SCHEMA_VERSION constant
│   └── versions/
│       └── 0001_initial_schema.py   # all 9 domain + 4 KG tables, ledger enforcement
├── tests/
│   ├── conftest.py          # PostgresContainer fixture, session-scoped
│   ├── test_schema.py       # table existence, constraint verification, HNSW index check
│   ├── test_ledger.py       # append-only enforcement, schema_version presence, trigger
│   ├── test_trace_chain.py  # recursive CTE correctness, CYCLE guard, depth limit
│   ├── test_as_of.py        # AS OF TIMESTAMP query against seeded multi-version data
│   └── test_metrics.py      # all 8 metric SQL queries return non-null results on seed data
└── docker-compose.yml       # postgres service with pgvector + pg_search
```

### Pattern 1: Alembic Migration with Schema Version Injection

**What:** Each Alembic migration file defines a `SCHEMA_VERSION` constant that is bound into the migration context. The first migration sets this to `"0001"`. Every subsequent migration increments it. The ledger_entry table has a `schema_version` column with a `DEFAULT` set to the current migration's version constant.

**When to use:** Every migration file, from the first. The value must be hardcoded in each migration (not computed at runtime) so it is immutable per-revision.

**Why it cannot be deferred:** If `schema_version` is absent from the first migration, all records inserted before the field is added will have `NULL` as their version. AS OF TIMESTAMP queries that branch on `schema_version` cannot distinguish "version 1 record" from "pre-versioning record" — they are both NULL. The distinction is gone forever.

**Example:**
```python
# alembic/versions/0001_initial_schema.py
# Source: CONTEXT.md D-05; PITFALLS.md Pitfall 4

SCHEMA_VERSION = "0001"

def upgrade() -> None:
    op.execute(f"SET eclusa.schema_version = '{SCHEMA_VERSION}'")
    op.create_table(
        "ledger_entry",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("schema_version", sa.String(10), nullable=False,
                  server_default=SCHEMA_VERSION),
        # ... other columns
    )
```

### Pattern 2: Append-Only Ledger Enforcement (Defense-in-Depth)

**What:** Two independent enforcement layers on `ledger_entry`. First: REVOKE UPDATE/DELETE from the application role at the Postgres permission layer. Second: a trigger that raises an exception even if a DBA or superuser attempts an UPDATE/DELETE, catching misuse from privileged connections.

**When to use:** Applied in the initial migration, never removed. Both layers are required (D-07 + D-08).

**Why defense-in-depth:** Grant revocation protects against normal application code mistakes. The trigger protects against: (a) developers connecting as postgres superuser during debugging, (b) future migrations that accidentally touch ledger rows, (c) ORMs that issue UPDATE silently.

**Example:**
```sql
-- Source: CONTEXT.md D-07, D-08; PITFALLS.md §Security Mistakes

-- Layer 1: Role-level grant revocation
REVOKE UPDATE, DELETE ON ledger_entry FROM eclusa_app;

-- Layer 2: Trigger on privileged connections
CREATE OR REPLACE FUNCTION ledger_entry_immutability_guard()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'ledger_entry is append-only: UPDATE and DELETE are forbidden. '
                  'Create a new entry referencing the superseded entry instead.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_ledger_immutability
BEFORE UPDATE OR DELETE ON ledger_entry
FOR EACH ROW EXECUTE FUNCTION ledger_entry_immutability_guard();
```

### Pattern 3: Trace Chain Query with CYCLE Guard

**What:** A recursive CTE walks from any artifact row up through session → stage → cascade → intent using foreign key joins. The CYCLE clause (PG14+) prevents infinite loops on any malformed data. A depth limit provides a secondary guard.

**When to use:** Verified in Phase 1 tests against seeded data. Consumed by Phase 2 executor for cascade graph traversal. Verified to terminate even on intentionally cyclic test fixtures.

**Why CYCLE guard from day one:** A cascade that references a sub-cascade that references a parent stage CAN form a cycle on a data bug. Without the guard, the executor hangs indefinitely, consuming a connection until killed.

**Example:**
```sql
-- Source: PITFALLS.md §Pitfall 2; Postgres docs WITH RECURSIVE

WITH RECURSIVE trace AS (
  -- Base: start from artifact
  SELECT
    a.id           AS artifact_id,
    a.session_id,
    a.stage_id,
    a.cascade_id,
    a.intent_id,
    1              AS depth
  FROM artifact a
  WHERE a.id = $1

  UNION ALL

  -- Recursive: walk up the cascade nesting (sub-cascades)
  SELECT
    t.artifact_id,
    t.session_id,
    t.stage_id,
    c.intent_id    AS cascade_id,   -- cascade's parent intent
    c.intent_id,
    t.depth + 1
  FROM trace t
  JOIN cascade c ON c.id = t.cascade_id
  WHERE t.depth < 50
)
CYCLE intent_id SET is_cycle USING cycle_path
SELECT
  artifact_id,
  session_id,
  stage_id,
  cascade_id,
  intent_id
FROM trace
WHERE NOT is_cycle
ORDER BY depth DESC
LIMIT 1;
```

### Pattern 4: AS OF TIMESTAMP Ledger Query

**What:** Returns the ledger state for a given entity at any historical moment by filtering on `timestamp <= $as_of` and returning the latest row before that point.

**When to use:** Any query that needs to answer "what was the system state at time T?" Including audit, rollback reference, and the self-calibration metrics that depend on historical state snapshots.

**Example:**
```sql
-- Source: ARCHITECTURE.md §Pattern 5; eclusa.md §3.7

SELECT *
FROM ledger_entry
WHERE entity_id = $1          -- cascade_id, stage_id, etc.
  AND timestamp <= $2::timestamptz
ORDER BY timestamp DESC
LIMIT 1;
```

### Pattern 5: Bi-Temporal Fact with Explicit Four-Timestamp Columns

**What:** The `fact` table (knowledge graph tier) uses four explicit `timestamptz` columns — not range types, not PG17 system-time automation. This is D-10 locked. Each column has a distinct semantic meaning.

**When to use:** All fact rows. The four columns answer two independent questions:
- Event timeline: `t_valid` (when fact became true in world) / `t_invalid` (when it stopped being true)
- Transactional timeline: `t_created` (when system learned it) / `t_expired` (when system invalidated it)

**Example:**
```sql
-- Source: eclusa.md §4.1; CONTEXT.md D-10; ARCHITECTURE.md §Pattern 6

CREATE TABLE fact (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_entity  UUID NOT NULL REFERENCES entity(id),
  target_entity  UUID NOT NULL REFERENCES entity(id),
  predicate      TEXT NOT NULL,
  embedding      vector(1024),
  t_valid        TIMESTAMPTZ NOT NULL,
  t_invalid      TIMESTAMPTZ,
  t_created      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  t_expired      TIMESTAMPTZ,
  source_episodes UUID[] NOT NULL DEFAULT '{}',
  schema_version VARCHAR(10) NOT NULL DEFAULT '0001'
);
```

### Pattern 6: pgvector HNSW Index Creation

**What:** HNSW indexes on all `vector(1024)` columns are created in the Phase 1 DDL (D-18), even though embeddings are not written until later phases. This avoids a future DDL migration on populated tables.

**When to use:** On every `embedding vector(1024)` column: intent.embedding, cascade.embedding, entity.embedding, fact.embedding.

**Example:**
```sql
-- Source: STACK.md; CONTEXT.md D-18; pgvector docs

-- After creating the extension
CREATE EXTENSION IF NOT EXISTS vector;

-- HNSW index with cosine distance operator class
CREATE INDEX idx_intent_embedding ON intent
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

### Pattern 7: pg_search (ParadeDB) Extension and BM25 Index

**What:** pg_search enables BM25 full-text search inside Postgres. It installs as a Postgres extension. In Phase 1, the extension is installed and BM25 indexes are created on text columns that will be searched in Phase 4 (entity.name, entity.summary, fact.predicate). Creating them now avoids Phase 4 DDL migrations on populated tables.

**When to use:** Phase 1 DDL only. Actual BM25 queries are a Phase 4 concern.

**Example:**
```sql
-- Source: STACK.md §pg_search; INFRA-04

CREATE EXTENSION IF NOT EXISTS pg_search;

-- BM25 index on entity text columns
CALL paradedb.create_bm25(
  index_name => 'entity_bm25',
  table_name => 'entity',
  key_field  => 'id',
  text_fields => paradedb.field('name') || paradedb.field('summary')
);
```

### Anti-Patterns to Avoid

- **Backfilling ledger rows on schema changes:** Adding a new column to `ledger_entry` and writing NULL or a default to old rows mutates immutable records. Never do this. Old rows live with the schema they were written under. AS OF queries must branch on `schema_version`.
- **Missing CYCLE clause in recursive CTEs:** Any CTE touching stage.depends_on or cascade hierarchy without a CYCLE clause will hang on malformed data. No exceptions.
- **REVOKE without trigger:** Grant revocation alone misses privileged connections. Both layers (D-07 and D-08) are required.
- **Storing ULID as text in a non-indexed column:** ULIDs stored as `char(26)` text cannot use index range scans. Store as UUID type with the ULID value cast — UUID supports B-tree range scans on the ULID byte order.
- **Python-native temporal_tables extension:** The `temporal_tables` extension has limited maintenance activity. Do not depend on it for bi-temporal support. Use explicit four-column design (D-10).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ULID generation | Custom base32 encoder | `python-ulid` library | ULIDs have a specific alphabet (Crockford base32) and monotonicity guarantee; hand-rolling is error-prone |
| Schema migration management | Shell scripts + raw SQL | Alembic (D-04 locked) | Alembic tracks migration history, handles dependency ordering, generates upgrade/downgrade scripts |
| Real Postgres in tests | `sqlite` mock DB | `testcontainers[postgres]` (D-13 locked) | Recursive CTEs, HNSW indexes, `FOR UPDATE SKIP LOCKED`, and Postgres triggers have no SQLite equivalents; mocks produce false confidence |
| Immutability enforcement | Application-level check | Postgres REVOKE + trigger (D-07, D-08) | Application checks can be bypassed; DB-level enforcement cannot |
| BM25 full-text search | tsvector/ts_rank | pg_search (INFRA-04 locked) | pg_search delivers proper BM25 IDF weighting inside Postgres; tsvector uses a simpler TF-only ranking |
| Vector similarity search | Hand-rolled cosine in Python | pgvector HNSW | pgvector runs inside the query planner; pulling vectors to Python is N×bandwidth cost |
| Cycle detection in graph traversal | Manual visited-set accumulation | SQL CYCLE clause (PG14+) | CYCLE is standard SQL:1999, fully supported in PG14+; manual sets have bugs; CYCLE is auditable |

**Key insight:** Every "hand-roll" candidate in this domain has subtle correctness requirements (ULID alphabet, cycle detection, immutability) that are exactly the kind of edge case that fails silently in tests but breaks in production.

---

## Common Pitfalls

### Pitfall 1: schema_version Absent from First Migration (CRITICAL — no retroactive fix)

**What goes wrong:** `schema_version` is added to `ledger_entry` in a later migration as an afterthought. Old rows receive NULL. AS OF TIMESTAMP replay logic cannot distinguish "version 1 record" from "pre-versioning record." Metric queries that branch on schema_version produce historically incorrect answers — silently.

**Why it happens:** Developers treat schema_version as a "nice to have" that can be added later. It cannot. The append-only guarantee means old rows cannot be updated.

**How to avoid:** `schema_version VARCHAR(10) NOT NULL DEFAULT '0001'` must be in the column list of the very first `CREATE TABLE ledger_entry`. The `DEFAULT` is what auto-populates existing rows; for future migrations, each revision's Python file contains the hardcoded next version string.

**Warning signs:** Any Alembic revision that adds `schema_version` to `ledger_entry` — that means it was missing from the initial migration.

### Pitfall 2: Recursive CTE Without CYCLE Guard

**What goes wrong:** The trace chain query hangs forever on a cascade with a cycle (possible from a data bug in `stage.depends_on`). Under multi-executor load, this consumes DB connections until exhaustion.

**Why it happens:** Happy-path traversal works. CYCLE guards are added "later" — but later is production.

**How to avoid:** Every recursive CTE must have `CYCLE id SET is_cycle USING cycle_path` and a hard `WHERE depth < 50`. Verify with a test fixture that inserts a cyclic stage graph and confirms the query terminates.

**Warning signs:** Any recursive CTE in trace_chain.sql, as_of.sql, or executor queries that lacks both guards.

### Pitfall 3: HNSW Index Created on Already-Populated Table

**What goes wrong:** Phase 1 skips HNSW index creation because embeddings aren't written until Phase 4. Phase 4 tries to `CREATE INDEX` on a table with millions of rows. HNSW index build on a populated table takes 10+ GB RAM and hours, blocking all other DB operations.

**Why it happens:** "We'll add the index when we need it." The cost is deferred to the worst possible moment.

**How to avoid:** D-18 locked this correctly: create all HNSW indexes in Phase 1 DDL on empty tables. Index build on empty tables is instant.

**Warning signs:** Any `CREATE INDEX ... USING hnsw` not present in the Phase 1 migration.

### Pitfall 4: pg_search Requires Docker Image With Extension Pre-Compiled

**What goes wrong:** Standard `postgres:17` Docker image does not include pg_search. Running `CREATE EXTENSION pg_search` on a vanilla image will fail. This breaks `docker-compose up` if the image is wrong.

**Why it happens:** pg_search is a Postgres extension that must be compiled against the specific PG version. The base Postgres image does not include it.

**How to avoid:** Use `paradedb/paradedb:latest` as the Docker image (which includes both pgvector and pg_search) or use a custom Dockerfile that installs both extensions against postgres:17. The docker-compose.yml must specify the correct image from day one.

**Warning signs:** `docker-compose.yml` using `image: postgres:17` without a Dockerfile that installs pg_search.

### Pitfall 5: LISTEN/NOTIFY Used Alone Without Polling Baseline (Pre-empted from Phase 2)

**What goes wrong:** Even though the executor is Phase 2, the schema design in Phase 1 must lay the correct foundation. Specifically: if `pg_notify('stage_changed', ...)` is emitted inside the same transaction that inserts a `ledger_entry`, the NOTIFY holds a `ShareLock` until commit. Under concurrent load, this serializes all commits across the Postgres instance.

**Why it happens:** Phase 1 sets up the trigger or `ledger_entry` insert function, and it is tempting to include a `NOTIFY` inside that function. Do not.

**How to avoid:** Never emit NOTIFY inside a ledger_entry trigger or INSERT. NOTIFY is a separate, lightweight, out-of-band signal. The executor's SKIP LOCKED poll is the durable dispatch mechanism. NOTIFY is the hint that wakes it early.

**Warning signs:** Any `pg_notify(...)` call inside a trigger function on `ledger_entry` or other high-frequency write tables.

### Pitfall 6: Self-Calibration Metrics Cannot Be Computed From Ledger Schema

**What goes wrong:** The 8 metric formulas reference ledger event types that are not present as `ledger_type` enum values. For example, "gate_resolved" events are needed for gate necessity rate, but if `ledger_type` enum does not include `gate_resolved`, the query returns zero rows.

**Why it happens:** Metrics are specified as product requirements but not cross-referenced with the schema during DDL design.

**How to avoid:** Before finalizing the `ledger_type` enum, write all 8 metric SQL queries and verify each requires only event types defined in the enum. This is the literal exit criterion (SCHEMA-06, D-15). Run all 8 queries against seeded test data before the schema is frozen.

**Warning signs:** Any metric query that returns NULL or zero on seeded data; any metric that requires a `ledger_type` value not in the enum.

---

## Code Examples

Verified patterns from canonical sources:

### Entity ID Pattern (ULID as UUID)
```python
# Source: CONTEXT.md D-01, D-02; python-ulid docs

from ulid import ULID
import uuid

def new_id() -> uuid.UUID:
    """Generate a ULID as UUID — sortable by creation time, stored as native UUID type."""
    return ULID().to_uuid()

# SQLAlchemy column declaration
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

class Intent(Base):
    __tablename__ = "intent"
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    # ...
```

### Alembic Async env.py Pattern
```python
# Source: STACK.md; Alembic async template; CONTEXT.md D-04

# alembic/env.py (generated by alembic init -t async, then customized)
from sqlalchemy.ext.asyncio import async_engine_from_config

async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```

### testcontainers Fixture Pattern
```python
# Source: CONTEXT.md D-13; testcontainers-python docs

import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def pg_container():
    """Real PG17 instance with pgvector + pg_search extensions."""
    with PostgresContainer("paradedb/paradedb:latest") as pg:
        yield pg

@pytest.fixture(scope="session")
async def db_conn(pg_container):
    import asyncpg
    conn = await asyncpg.connect(pg_container.get_connection_url())
    # Run Alembic migrations
    yield conn
    await conn.close()
```

### Ledger Enforcement Test
```python
# Source: CONTEXT.md D-07, D-08; PITFALLS.md §Pitfall 4

import pytest
import asyncpg

async def test_ledger_entry_is_append_only(db_conn):
    """Verify both enforcement layers: REVOKE and trigger."""
    # Insert a valid ledger entry
    row_id = await db_conn.fetchval(
        "INSERT INTO ledger_entry (actor_id, type, content, reversible, timestamp) "
        "VALUES ($1, 'intent_created', '{}', false, NOW()) RETURNING id",
        some_actor_id
    )

    # Attempt UPDATE — must be rejected
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await db_conn.execute(
            "UPDATE ledger_entry SET content = '{}' WHERE id = $1", row_id
        )

    # Attempt DELETE — must be rejected
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await db_conn.execute("DELETE FROM ledger_entry WHERE id = $1", row_id)
```

### Metric SQL Example: Gate Necessity Rate
```sql
-- Source: eclusa.md §9; REQUIREMENTS.md CAL-01
-- "% of gates where human chose different from system recommendation"
-- Requires ledger_type values: gate_surfaced, gate_resolved

SELECT
  COUNT(*) FILTER (WHERE
    resolved.content->>'human_choice' != resolved.content->>'system_recommendation'
  )::FLOAT
  / NULLIF(COUNT(*), 0) AS gate_necessity_rate
FROM ledger_entry surfaced
JOIN ledger_entry resolved
  ON resolved.stage_id = surfaced.stage_id
  AND resolved.type = 'gate_resolved'
WHERE surfaced.type = 'gate_surfaced'
  AND surfaced.timestamp >= NOW() - INTERVAL '30 days';
```

---

## Complete Entity Schema Reference

Extracted from `eclusa.md §3` and `§4` for planner use. These are the authoritative field definitions.

### Domain Entities (9)

**intent** — root of all trace chains
```sql
id           UUID  PRIMARY KEY  (ULID as UUID)
parent_id    UUID  REFERENCES intent(id)  -- NULL for root intents
source       intent_source  NOT NULL
raw          TEXT  NOT NULL
context      JSONB
embedding    vector(1024)
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
created_by   UUID  NOT NULL REFERENCES actor(id)
```

**actor** — any participating entity (human, agent, system, webhook)
```sql
id           UUID  PRIMARY KEY
type         actor_type  NOT NULL  -- human | agent | system | webhook
identity     TEXT  NOT NULL
permissions  JSONB
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
```

**cascade** — living directed graph of work
```sql
id           UUID  PRIMARY KEY
intent_id    UUID  NOT NULL REFERENCES intent(id)
shape        JSONB  NOT NULL  -- pydantic_graph definition
annotations  JSONB
narrative    TEXT
state        cascade_state  NOT NULL  -- active|paused|completed|failed|evergreen
embedding    vector(1024)
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
completed_at TIMESTAMPTZ
```

**stage** — node in cascade graph
```sql
id           UUID  PRIMARY KEY
cascade_id   UUID  NOT NULL REFERENCES cascade(id)
type         stage_type  NOT NULL  -- narrowing | gate
state        stage_state  NOT NULL  -- pending|active|blocked|resolved|skipped
input        JSONB
output       JSONB
depends_on   UUID[]  NOT NULL DEFAULT '{}'  -- graph edges
served_by    UUID[]  NOT NULL DEFAULT '{}'  -- work_session or judgment_pass ids
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
resolved_at  TIMESTAMPTZ
resolved_by  UUID  REFERENCES actor(id)
```

**work_session** — agent in harness with tools
```sql
id              UUID  PRIMARY KEY
stage_ids       UUID[]  NOT NULL DEFAULT '{}'
harness_type    TEXT  NOT NULL  -- native|claude_code|codex|opencode|custom
model           TEXT  NOT NULL
model_swaps     JSONB  NOT NULL DEFAULT '[]'
message_history JSONB  NOT NULL DEFAULT '[]'
workspace_ref   TEXT
state           work_session_state  NOT NULL  -- running|paused|completed|failed
cost            JSONB  NOT NULL DEFAULT '{}'  -- tokens_in, tokens_out, api_calls, tool_calls, wall_time_ms, estimated_usd
created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
paused_at       TIMESTAMPTZ
resumed_at      TIMESTAMPTZ
completed_at    TIMESTAMPTZ
```

**judgment_pass** — single API completion, no tools
```sql
id           UUID  PRIMARY KEY
stage_ids    UUID[]  NOT NULL DEFAULT '{}'
model        TEXT  NOT NULL
context_ref  TEXT  NOT NULL  -- object storage path
context_hash TEXT  NOT NULL  -- blake3, dedup identical evaluations
prompt       TEXT  NOT NULL
response     JSONB
confidence   NUMERIC
cost         JSONB  NOT NULL DEFAULT '{}'
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
completed_at TIMESTAMPTZ
```

**fan_out** — parallel judgment passes with convergence check
```sql
id           UUID  PRIMARY KEY
stage_id     UUID  NOT NULL REFERENCES stage(id)
context_ref  TEXT  NOT NULL
prompt       TEXT  NOT NULL
passes       UUID[]  NOT NULL DEFAULT '{}'  -- judgment_pass.ids
convergence  JSONB
verdict      fan_out_verdict  -- converged|diverged|partial
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
completed_at TIMESTAMPTZ
```

**artifact** — bridge to outside world, full trace chain links
```sql
id           UUID  PRIMARY KEY
intent_id    UUID  NOT NULL REFERENCES intent(id)  -- root trace, always
cascade_id   UUID  NOT NULL REFERENCES cascade(id)
stage_id     UUID  NOT NULL REFERENCES stage(id)
session_id   UUID  REFERENCES work_session(id)
type         artifact_type  NOT NULL
external_ref TEXT
external_sys TEXT
payload      JSONB
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
```

**ledger_entry** — the sacred record, append-only
```sql
id             UUID  PRIMARY KEY
intent_id      UUID  REFERENCES intent(id)
cascade_id     UUID  REFERENCES cascade(id)
stage_id       UUID  REFERENCES stage(id)
session_id     UUID  REFERENCES work_session(id)
actor_id       UUID  NOT NULL REFERENCES actor(id)
type           ledger_type  NOT NULL
content        JSONB  NOT NULL DEFAULT '{}'
confidence     NUMERIC
reversible     BOOLEAN  NOT NULL DEFAULT false
artifact_ids   UUID[]  NOT NULL DEFAULT '{}'
timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
schema_version VARCHAR(10)  NOT NULL DEFAULT '0001'  -- CRITICAL: in first migration
```

**tool** — external capability registration
```sql
id            UUID  PRIMARY KEY
name          TEXT  NOT NULL
interface     JSONB  NOT NULL
auth_ref      TEXT
cost_profile  JSONB
registered_by UUID  NOT NULL REFERENCES actor(id)
created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
```

### Knowledge Graph Tables (4)

**episode** — raw ingested data, non-lossy
```sql
id           UUID  PRIMARY KEY
source       TEXT  NOT NULL
raw_data     JSONB  NOT NULL
reference_ts TIMESTAMPTZ  NOT NULL  -- when the event occurred in the world
ingested_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
schema_version VARCHAR(10) NOT NULL DEFAULT '0001'
```

**entity** — durable extracted concept
```sql
id           UUID  PRIMARY KEY
name         TEXT  NOT NULL
type         TEXT
summary      TEXT
embedding    vector(1024)
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
```

**fact** — edge between entities, bi-temporal
```sql
id              UUID  PRIMARY KEY
source_entity   UUID  NOT NULL REFERENCES entity(id)
target_entity   UUID  NOT NULL REFERENCES entity(id)
predicate       TEXT  NOT NULL
embedding       vector(1024)
t_valid         TIMESTAMPTZ  NOT NULL
t_invalid       TIMESTAMPTZ
t_created       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
t_expired       TIMESTAMPTZ
source_episodes UUID[]  NOT NULL DEFAULT '{}'
schema_version  VARCHAR(10)  NOT NULL DEFAULT '0001'
```

**community** — clusters of strongly connected entities
```sql
id           UUID  PRIMARY KEY
name         TEXT  NOT NULL
summary      TEXT
entity_ids   UUID[]  NOT NULL DEFAULT '{}'
created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
```

### Required Enum Types

```sql
CREATE TYPE intent_source AS ENUM (
  'slack_message', 'email', 'voice', 'chat', 'webhook', 'api',
  'cli', 'figma_comment', 'notion_page', 'lark_message',
  'github_issue', 'manual'
);

CREATE TYPE actor_type AS ENUM ('human', 'agent', 'system', 'webhook');

CREATE TYPE cascade_state AS ENUM ('active', 'paused', 'completed', 'failed', 'evergreen');

CREATE TYPE stage_type AS ENUM ('narrowing', 'gate');

CREATE TYPE stage_state AS ENUM ('pending', 'active', 'blocked', 'resolved', 'skipped');

CREATE TYPE work_session_state AS ENUM ('running', 'paused', 'completed', 'failed');

CREATE TYPE artifact_type AS ENUM (
  'git_commit', 'git_branch', 'git_pr', 'api_request', 'api_response',
  'deployment', 'file_created', 'message_sent', 'webhook_out',
  'config_change', 'external_state'
);

CREATE TYPE fan_out_verdict AS ENUM ('converged', 'diverged', 'partial');

-- CRITICAL: All 8 self-calibration metrics must map to ledger_type values here
CREATE TYPE ledger_type AS ENUM (
  -- Domain lifecycle events
  'intent_created',
  'cascade_created', 'cascade_state_changed', 'cascade_migration',
  'stage_created', 'stage_state_changed',
  'work_session_started', 'work_session_paused', 'work_session_resumed',
  'work_session_completed', 'work_session_failed',
  'judgment_pass_created', 'judgment_pass_completed',
  'fan_out_created', 'fan_out_completed',
  'artifact_created',
  -- Gate lifecycle (required for CAL-01, CAL-02, CAL-03, CAL-04)
  'gate_surfaced',
  'gate_resolved',
  'gate_auto_resolved',
  -- Cascade rework (required for CAL-05)
  'cascade_reopened',
  -- Self-calibration signals
  'orchestrator_absorbed',  -- ambiguityUp resolved without human (CAL-02)
  -- Schema migration record
  'schema_migration'
);
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| psycopg2 (sync) | psycopg 3.3.x (async, native LISTEN/NOTIFY) | 2021–2023 | Async-native LISTEN/NOTIFY; no more thread hacks |
| SQLAlchemy 1.x | SQLAlchemy 2.0 (async, new query API) | 2023 | `async with Session` pattern; do not use 1.x |
| Alembic sync env.py | `alembic init -t async` | 2021 | Async-compatible env.py generated out of the box |
| Separate vector DB (Qdrant, Weaviate) | pgvector inside Postgres | 2022–2024 | Single-DB constraint satisfied; no synchronization lag |
| IVFFlat indexes | HNSW indexes (pgvector 0.5+) | 2023 | HNSW iterative scan (0.8.0) prevents overfiltering |
| pg_trgm / tsvector | pg_search (ParadeDB) BM25 | 2024–2025 | Proper BM25 IDF weighting; not just TF ranking |
| PG14 temporal constraints | PG17 WITHOUT OVERLAPS | 2024 | First-class uni-temporal PKs in PG17 |

**Deprecated/outdated:**
- `psycopg2`: Synchronous-only; replaced by `psycopg` (3.x); do not use
- `SQLModel`: Merges SQLAlchemy + Pydantic in ways that break Alembic autogenerate; use SQLAlchemy + Pydantic separately
- `temporal_tables` extension: Limited maintenance; use explicit four-column bi-temporal design (D-10)
- `alembic init` (without `-t async`): Generates sync env.py; use `-t async` for this project

---

## Open Questions

1. **ledger_type enum growth over time**
   - What we know: All 8 metric queries are verified at phase exit, but the enum will grow as new event types are needed in Phases 2–4
   - What's unclear: PG enum types can only be extended (ADD VALUE), not modified — values can never be removed or renamed without a full type rebuild
   - Recommendation: Design `ledger_type` generously in Phase 1. It is cheaper to define extra values that are unused than to discover a missing value in Phase 2 when the ledger is already populated. Consider whether a `TEXT` column with a CHECK constraint is more migration-friendly than an ENUM.

2. **SCHEMA-08 placement (RBAC)**
   - What we know: REQUIREMENTS.md traceability maps SCHEMA-08 to Phase 5; but the actor.permissions JSONB column is laid in Phase 1 DDL
   - What's unclear: Phase 1 instructions list INFRA-02 and INFRA-04 as requirements; the additional context lists SCHEMA-08 as a Phase 1 requirement ID — this contradicts the traceability table
   - Recommendation: Lay the `actor.permissions JSONB` column in Phase 1 DDL (it is part of SCHEMA-01 scope anyway) but do not implement the RBAC enforcement logic — that is Phase 5.

3. **pg_search Docker image version pinning**
   - What we know: `paradedb/paradedb:latest` is the recommended base image; STACK.md lists pg_search as "latest" without a version
   - What's unclear: ParadeDB releases frequently; `latest` in docker-compose can drift between developer machines
   - Recommendation: Pin to a specific ParadeDB image tag in docker-compose.yml rather than `latest`. Determine the current stable tag before writing the compose file.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | docker-compose.yml; testcontainers | Yes | 29.2.1 | — |
| Docker Compose | `docker-compose up` bootstrap | Yes | v5.0.2 | — |
| Python | All DB code, tests | Yes | 3.13.3 | Note: 3.13 free-threading; all deps support 3.10–3.14 |
| uv | Dependency management | Yes | 0.9.24 | — |
| pytest | Test runner | Yes (via asdf shim) | current | — |
| asyncpg | Executor hot path | Not installed | — | `uv add asyncpg` in Wave 0 |
| psycopg | LISTEN/NOTIFY + general | Not installed | — | `uv add "psycopg[binary,pool]"` in Wave 0 |
| SQLAlchemy | Schema declaration | Not installed | — | `uv add sqlalchemy[asyncio]` in Wave 0 |
| Alembic | Migrations | Not installed | — | `uv add alembic` in Wave 0 |
| testcontainers | Real PG in tests | Not installed | — | `uv add --dev "testcontainers[postgres]"` in Wave 0 |
| python-ulid | ULID generation | Not installed | — | `uv add python-ulid` in Wave 0 |
| Postgres (local) | Direct connection | Not running | — | All tests use testcontainers (Docker-based) |

**Missing dependencies with no fallback:**
- None — all missing packages install via `uv add`; Docker is present for testcontainers

**Missing dependencies with fallback:**
- All Python packages: Wave 0 installs them via `uv add`
- Local Postgres: Not needed — testcontainers spins a real instance per test session

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (current) + pytest-asyncio (current) |
| Config file | `pytest.ini` — Wave 0 creates this; `asyncio_mode = "auto"` required |
| Quick run command | `pytest tests/test_schema.py tests/test_ledger.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHEMA-01 | All 9 domain tables + 4 KG tables exist with correct columns | structural | `pytest tests/test_schema.py::test_all_tables_exist -x` | Wave 0 |
| SCHEMA-02 | UPDATE/DELETE on ledger_entry raises exception (both role and trigger) | enforcement | `pytest tests/test_ledger.py::test_ledger_entry_is_append_only -x` | Wave 0 |
| SCHEMA-03 | Every ledger_entry row has non-null schema_version from first insert | structural | `pytest tests/test_ledger.py::test_schema_version_present -x` | Wave 0 |
| SCHEMA-04 | Trace chain CTE walks artifact → session → stage → cascade → intent | integration | `pytest tests/test_trace_chain.py::test_full_trace_chain -x` | Wave 0 |
| SCHEMA-04 | Trace chain CTE terminates on cyclic stage.depends_on (CYCLE guard) | correctness | `pytest tests/test_trace_chain.py::test_cycle_guard_terminates -x` | Wave 0 |
| SCHEMA-05 | AS OF TIMESTAMP returns correct ledger state at historical moment | integration | `pytest tests/test_as_of.py::test_as_of_timestamp_query -x` | Wave 0 |
| SCHEMA-06 | All 8 metric SQL queries return non-null results on seeded test data | correctness | `pytest tests/test_metrics.py -x` | Wave 0 |
| SCHEMA-07 | pgvector extension exists; HNSW indexes present on all vector(1024) columns | structural | `pytest tests/test_schema.py::test_pgvector_and_hnsw_indexes -x` | Wave 0 |
| INFRA-02 | Single PG instance serves all tables: domain, KG, ledger | structural | `pytest tests/test_schema.py::test_single_db_all_tables -x` | Wave 0 |
| INFRA-04 | pg_search extension installed; BM25 index present on entity text columns | structural | `pytest tests/test_schema.py::test_pg_search_extension -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_schema.py tests/test_ledger.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green + all 8 metric queries return non-null on seeded data before schema is frozen

### Wave 0 Gaps

- [ ] `pytest.ini` — `asyncio_mode = "auto"` required; install: `uv add --dev pytest pytest-asyncio`
- [ ] `tests/conftest.py` — `PostgresContainer("paradedb/paradedb:latest")` session-scoped fixture; install: `uv add --dev "testcontainers[postgres]"`
- [ ] `tests/test_schema.py` — covers SCHEMA-01, SCHEMA-07, INFRA-02, INFRA-04
- [ ] `tests/test_ledger.py` — covers SCHEMA-02, SCHEMA-03
- [ ] `tests/test_trace_chain.py` — covers SCHEMA-04 (including cyclic fixture)
- [ ] `tests/test_as_of.py` — covers SCHEMA-05
- [ ] `tests/test_metrics.py` — covers SCHEMA-06 (all 8 metric queries)
- [ ] Package install: `uv add sqlalchemy[asyncio] alembic asyncpg "psycopg[binary,pool]" python-ulid`
- [ ] Package install: `uv add --dev pytest pytest-asyncio "testcontainers[postgres]"`

---

## Project Constraints (from CLAUDE.md)

- **Infrastructure**: Single Postgres instance (+ pgvector) for everything — no external vector DB
- **Execution**: Stateless executor, all state in DB, crash-restart safe
- **Concurrency**: Postgres SKIP LOCKED for multi-executor, LISTEN/NOTIFY for event-driven dispatch (as wake-hint only — not sole mechanism)
- **Storage**: Object storage for workspace snapshots (session pause/resume)
- **Deployment**: `docker-compose up` — single command bootstrap
- **Tech stack**: Python executor (~300-500 lines), Pydantic AI for native harness
- **Python packaging**: Use `uv add` — never `pip install` or `uv pip install`
- **Linting**: `ruff check . && ruff format .`
- **Type checking**: `pyright` strict mode
- **Workflow**: Start work through Eclusa commands; no direct repo edits outside Eclusa workflow unless user explicitly asks

---

## Sources

### Primary (HIGH confidence)
- `eclusa.md §3` — All 9 domain entity schemas with exact field definitions (canonical RFC)
- `eclusa.md §4.1` — Fact entity bi-temporal schema (four timestamps)
- `eclusa.md §5.1` — Executor pseudocode defining the SKIP LOCKED + LISTEN/NOTIFY query contract
- `eclusa.md §9` — 8 self-calibration metric definitions and SQL formula shapes
- `.eclusa/research/STACK.md` — All library versions verified via PyPI/npm on 2026-04-04
- `.eclusa/research/PITFALLS.md` — Production pitfall catalog with root causes and prevention strategies
- `.eclusa/research/ARCHITECTURE.md` — Project structure, data flows, and anti-patterns
- `.eclusa/phases/01-db-foundation/01-CONTEXT.md` — 18 locked implementation decisions

### Secondary (MEDIUM confidence)
- [Postgres docs — WITH RECURSIVE + CYCLE clause](https://www.postgresql.org/docs/current/queries-with.html) — PG14+ CYCLE standard support confirmed
- [pgvector GitHub](https://github.com/pgvector/pgvector) — v0.8.2 HNSW iterative scan confirmed
- [ParadeDB pg_search](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) — BM25 in PG17 confirmed
- [Alembic docs — async support](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic) — `-t async` template confirmed

### Tertiary (LOW confidence)
- None — all critical claims cross-verified against official documentation or canonical project sources

---

## Metadata

**Confidence breakdown:**
- Entity schemas: HIGH — sourced directly from canonical RFC eclusa.md
- Migration pattern: HIGH — locked decisions D-03 through D-05; Alembic docs verified
- Ledger enforcement: HIGH — locked decisions D-07, D-08; Postgres docs verified
- Recursive CTE pattern: HIGH — Postgres docs (CYCLE clause); PITFALLS.md (production incidents)
- Metric SQL computability: MEDIUM — formulas derived from eclusa.md §9 definitions; require seeded data verification to confirm field-level correctness
- pg_search Docker image: MEDIUM — ParadeDB image pattern confirmed; exact pinning version not checked

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable — library versions pinned; architecture is locked by RFC)
