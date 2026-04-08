---
phase: 01-db-foundation
plan: "02"
subsystem: database
tags: [sqlalchemy, alembic, pgvector, pg_search, paradedb, hnsw, bm25, ledger, bitemporal, ulid]

# Dependency graph
requires:
  - phase: 01-01
    provides: Alembic async setup, testcontainers conftest, pyproject.toml with deps, db/models/base.py stub
provides:
  - SQLAlchemy 2.0 declarative models for all 13 tables (9 domain + 4 KG)
  - Initial Alembic migration 0001_initial_schema.py with full DDL
  - All 9 enum types with exact values from eclusa.md §3
  - Ledger append-only enforcement (REVOKE + trigger defense-in-depth)
  - HNSW indexes on all 4 vector(1024) columns (intent, cascade, entity, fact)
  - BM25 index on entity.name+summary via pg_search 0.22+ USING bm25 API
  - schema_version VARCHAR(10) NOT NULL DEFAULT '0001' on ledger_entry from first migration
  - 13 passing tests covering schema correctness, ledger enforcement, index presence
affects:
  - 01-03 (trace chain queries use schema created here)
  - 01-04 (ledger enforcement tests run against this schema)
  - 01-05 (metric SQL queries verified against this schema)
  - all subsequent phases (every domain entity lives in these tables)

# Tech tracking
tech-stack:
  added:
    - pgvector==0.4.2 (Python package for Vector(1024) SQLAlchemy column type)
  patterns:
    - SQLAlchemy models use Python-side default=new_id() (ULID→UUID), not server_default for IDs
    - Alembic migration creates enum types via op.execute() raw SQL before op.create_table()
    - pg_search BM25 index via CREATE INDEX USING bm25() WITH (key_field='id', text_fields=...) — pg_search 0.22+ API
    - HNSW indexes created on empty tables in Phase 1 DDL to avoid expensive rebuild on populated tables
    - Raw asyncpg test inserts must use gen_random_uuid() for IDs since Python-side new_id() doesn't apply

key-files:
  created:
    - db/models/domain.py
    - db/models/compute.py
    - db/models/knowledge.py
    - alembic/versions/0001_initial_schema.py
    - tests/test_schema.py
    - tests/test_ledger.py
  modified:
    - db/models/base.py (added new_id() ULID function)
    - tests/conftest.py (fixed URL normalization for psycopg2:// prefix)
    - pyproject.toml (added pgvector dependency)

key-decisions:
  - "pg_search 0.22+ changed BM25 API from paradedb.create_bm25() CALL to CREATE INDEX USING bm25() WITH — migration uses new API"
  - "Raw asyncpg test inserts require gen_random_uuid() for UUID PKs since SQLAlchemy Python-side default=new_id() doesn't apply to raw SQL"
  - "All 9 enum types created via op.execute() raw SQL before table creation — necessary because SQLAlchemy's Text column type doesn't embed enum creation"

patterns-established:
  - "Pattern: ULID IDs generated as Python-side default in SQLAlchemy models (default=new_id), not server_default"
  - "Pattern: Alembic migration creates vector columns via ALTER TABLE ADD COLUMN after table creation (pgvector vector type not natively in sa)"
  - "Pattern: pg_search BM25 index uses pg_search 0.22+ syntax: CREATE INDEX name ON table USING bm25(id, col1, col2) WITH (key_field='id', text_fields='...')"
  - "Pattern: TDD tests for DB schema use gen_random_uuid() for raw SQL inserts — Python-side SQLAlchemy defaults don't apply"

requirements-completed: [SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-07, SCHEMA-08, INFRA-02, INFRA-04]

# Metrics
duration: 7min
completed: 2026-04-04
---

# Phase 01 Plan 02: SQLAlchemy Models and Initial Schema Migration Summary

**13 SQLAlchemy models + Alembic 0001 migration: all DDL, 9 enums, ledger REVOKE+trigger, HNSW on 4 vector columns, BM25 on entity — 13 tests passing**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-04T22:02:54Z
- **Completed:** 2026-04-04T22:10:00Z
- **Tasks:** 2
- **Files modified:** 9 (6 created, 3 modified)

## Accomplishments
- All 13 SQLAlchemy 2.0 declarative models created across domain.py, compute.py, knowledge.py — all import cleanly
- Initial Alembic migration creates all 13 tables, 9 enum types, all extensions, ledger enforcement, HNSW + BM25 indexes
- LedgerEntry.schema_version = VARCHAR(10) NOT NULL DEFAULT '0001' present from first migration (SCHEMA-03 satisfied — no retroactive fix path)
- Ledger append-only enforced by both REVOKE UPDATE/DELETE on eclusa_app role AND a trigger that raises exception even for privileged connections
- All 4 vector(1024) columns have HNSW indexes (m=16, ef_construction=64) created on empty tables per D-18
- ledger_type enum includes all 5 self-calibration metric values: gate_surfaced, gate_resolved, gate_auto_resolved, cascade_reopened, orchestrator_absorbed

## Task Commits

Each task was committed atomically:

1. **Task 1: Create SQLAlchemy 2.0 declarative models** - `74305fb` (feat)
2. **Task 2: TDD RED — failing tests for schema, ledger, indexes** - `15b1a33` (test)
3. **Task 2: TDD GREEN — initial Alembic migration** - `6e9429a` (feat)

## Files Created/Modified
- `db/models/base.py` - Updated with new_id() using ULID().to_uuid() per D-01/D-02
- `db/models/domain.py` - Intent, Actor, Cascade, Stage, Artifact, LedgerEntry, Tool + all 9 enum type definitions
- `db/models/compute.py` - WorkSession, JudgmentPass, FanOut
- `db/models/knowledge.py` - Episode, Entity, Fact (bi-temporal 4-column per D-10), Community
- `alembic/versions/0001_initial_schema.py` - Full DDL: 13 tables, 9 enums, extensions, REVOKE, trigger, HNSW×4, BM25, B-tree+GIN indexes
- `tests/test_schema.py` - 8 tests: table existence, extensions, HNSW indexes, enum types, schema_version, BM25, bi-temporal columns
- `tests/test_ledger.py` - 5 tests: schema_version default, UPDATE blocked, DELETE blocked, trigger exists, function exists
- `tests/conftest.py` - Fixed URL normalization (postgresql+psycopg2:// prefix handling)
- `pyproject.toml` - Added pgvector dependency

## Decisions Made
- pg_search 0.22+ changed API from `CALL paradedb.create_bm25()` to `CREATE INDEX USING bm25()` — migration updated to new API
- Raw asyncpg test inserts use `gen_random_uuid()` for PKs since Python-side `default=new_id()` doesn't apply to raw SQL
- Alembic migration creates enum types via raw `op.execute()` before `op.create_table()` to avoid SQLAlchemy enum embedding issues

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pg_search API changed in 0.22+ — replaced paradedb.create_bm25() with USING bm25 syntax**
- **Found during:** Task 2 (initial migration)
- **Issue:** `CALL paradedb.create_bm25(...)` procedure does not exist in pg_search 0.22.5 (the current paradedb/paradedb:latest). The API was completely reworked to use standard SQL `CREATE INDEX ... USING bm25`.
- **Fix:** Updated migration Step 8 to use `CREATE INDEX entity_bm25 ON entity USING bm25(id, name, summary) WITH (key_field='id', text_fields='{"name":{}, "summary":{}}')`
- **Files modified:** alembic/versions/0001_initial_schema.py, tests/test_schema.py
- **Verification:** test_bm25_index_exists passes
- **Committed in:** 6e9429a (Task 2 commit)

**2. [Rule 1 - Bug] conftest.py URL normalization missed postgresql+psycopg2:// prefix**
- **Found during:** Task 2 (RED test run)
- **Issue:** testcontainers returns `postgresql+psycopg2://` URL; `apply_migrations` fixture called `.replace("postgresql://", ...)` which didn't match this prefix, causing `ModuleNotFoundError: No module named 'psycopg2'`
- **Fix:** Added explicit normalization of `postgresql+psycopg2://` → `postgresql://` in `db_url` fixture
- **Files modified:** tests/conftest.py
- **Verification:** Tests run and reach Alembic migration stage
- **Committed in:** 15b1a33 (TDD RED commit)

**3. [Rule 1 - Bug] Raw asyncpg test inserts need explicit gen_random_uuid() for UUID PKs**
- **Found during:** Task 2 (GREEN test run)
- **Issue:** `INSERT INTO actor (type, identity) VALUES ('system', 'test') RETURNING id` failed with `null value in column "id"` — SQLAlchemy's Python-side `default=new_id()` doesn't apply to raw asyncpg INSERTs
- **Fix:** All test INSERT statements updated to include `gen_random_uuid()` for id column
- **Files modified:** tests/test_ledger.py
- **Verification:** All 5 ledger tests pass
- **Committed in:** 6e9429a (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 × Rule 1 - Bug)
**Impact on plan:** All fixes necessary for correctness. pg_search API finding is important infrastructure knowledge — documented in patterns-established.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None — tests use testcontainers (auto-starts paradedb/paradedb image). `uv run pytest tests/test_schema.py tests/test_ledger.py` runs cleanly from a clean checkout.

## Known Stubs
None — all columns, indexes, and constraints are fully wired. No placeholder data or hardcoded values in non-test code.

## Next Phase Readiness
- Schema DDL foundation is complete — all 13 tables exist after `alembic upgrade head`
- Plan 01-03 (trace chain queries) can begin immediately — recursive CTE queries against stage/cascade/intent are all present
- Plan 01-04 (ledger enforcement tests) has been partially covered here; remaining tests can build on this conftest
- Plan 01-05 (metric SQL verification) can query the ledger_type enum values (all 8 metric types present)

---
*Phase: 01-db-foundation*
*Completed: 2026-04-04*

## Self-Check: PASSED

Files confirmed present:
- FOUND: db/models/base.py
- FOUND: db/models/domain.py
- FOUND: db/models/compute.py
- FOUND: db/models/knowledge.py
- FOUND: alembic/versions/0001_initial_schema.py
- FOUND: tests/test_schema.py
- FOUND: tests/test_ledger.py
- FOUND: .eclusa/phases/01-db-foundation/01-02-SUMMARY.md

Commits confirmed:
- FOUND: 74305fb (feat: SQLAlchemy models)
- FOUND: 15b1a33 (test: TDD RED)
- FOUND: 6e9429a (feat: initial migration GREEN)
- FOUND: ec582ab (docs: SUMMARY + STATE)
