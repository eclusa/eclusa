---
phase: 02-executor-and-cascade
plan: "01"
subsystem: database
tags: [alembic, sqlalchemy, postgres, schema-migration, executor]

# Dependency graph
requires:
  - phase: 01-db-foundation
    provides: Initial schema migration 0001 with all 13 tables and enum types

provides:
  - Alembic migration 0002 adding failure_policy, parent_stage_id, retry_count, and cascade_migration_proposal table
  - Updated SQLAlchemy Cascade model with failure_policy and parent_stage_id columns
  - Updated SQLAlchemy Stage model with retry_count column
  - CascadeMigrationProposal SQLAlchemy model class

affects: [02-02, 02-03, 02-04, 02-05, executor, cascade-shape-migration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use op.execute() for all DDL in Alembic migrations (consistent with 0001 pattern)"
    - "server_default on SQLAlchemy columns (not default=) for columns added via ALTER TABLE"
    - "cascade_migration_proposal as mutable sidecar to the append-only ledger (Pitfall 5 pattern)"

key-files:
  created:
    - alembic/versions/0002_executor_schema_gaps.py
  modified:
    - db/models/domain.py

key-decisions:
  - "failure_policy DEFAULT is 'fail_cascade' — conservative choice per D-18, executor fails loudly rather than silently skipping"
  - "parent_stage_id is NULLABLE — root cascades have no parent, sub-cascades reference the spawning stage"
  - "cascade_migration_proposal is a separate mutable table (not a ledger entry) per Pitfall 5 — preserves append-only ledger invariant"
  - "server_default used for all new columns on SQLAlchemy models (not Python-side default=) to match ALTER TABLE DDL semantics"

patterns-established:
  - "Pitfall 5 pattern: when cascade shape must change, write to cascade_migration_proposal, not to ledger_entry"

requirements-completed: [CASC-03, CASC-04, CASC-05, CASC-06, CASC-07]

# Metrics
duration: 2min
completed: 2026-04-04
---

# Phase 2 Plan 01: Executor Schema Gaps Summary

**Alembic migration 0002 adds failure_policy/parent_stage_id/retry_count columns and cascade_migration_proposal table; SQLAlchemy models updated to match; 14/14 schema tests green**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-04T23:06:24Z
- **Completed:** 2026-04-04T23:08:08Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `alembic/versions/0002_executor_schema_gaps.py` with all 4 schema changes and correct `down_revision = "0001"` chain
- Added `failure_policy`, `parent_stage_id` to the `cascade` table and `retry_count` to `stage` table via ALTER TABLE DDL
- Created `cascade_migration_proposal` table with indexes as Pitfall 5 resolution (mutable proposal lifecycle outside append-only ledger)
- Updated SQLAlchemy `Cascade` and `Stage` classes with the 3 new columns and added `CascadeMigrationProposal` model class
- All existing Phase 1 tests remain green (14/14 in test_schema.py)

## Task Commits

Each task was committed atomically:

1. **Task 1: Write Alembic migration 0002** - `18b96d2` (feat)
2. **Task 2: Update SQLAlchemy models to match 0002** - `d4a9aff` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `alembic/versions/0002_executor_schema_gaps.py` - Migration 0002: adds failure_policy, parent_stage_id, retry_count, cascade_migration_proposal table + 2 indexes
- `db/models/domain.py` - Added failure_policy + parent_stage_id to Cascade, retry_count to Stage, new CascadeMigrationProposal class

## Decisions Made

- `server_default="fail_cascade"` (not Python `default=`) used on the SQLAlchemy `failure_policy` column to match the ALTER TABLE DDL — ensures rows inserted via raw SQL receive the correct default
- `cascade_migration_proposal` modeled as a plain mutable table, not a ledger entry — this is Pitfall 5's explicit resolution pattern: ledger remains append-only, mutation lives elsewhere
- `retry_count` uses `server_default=sa.text("0")` to produce a literal integer default (not a string) in Postgres

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Tests passed on first run with the new migration applied.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Migration 0002 is at `head`, chained from 0001
- Executor code in Plans 02-02 through 02-05 can now read `failure_policy`, `retry_count`, and `parent_stage_id` directly from DB rows
- `cascade_migration_proposal` table exists and is ready for the executor's cascade reshape logic
- All Phase 1 tests remain green — no regressions

## Self-Check: PASSED

- `alembic/versions/0002_executor_schema_gaps.py` — FOUND
- `db/models/domain.py` — FOUND (modified)
- `02-01-SUMMARY.md` — FOUND
- Commit `18b96d2` — FOUND (feat(02-01): add Alembic migration 0002 for executor schema gaps)
- Commit `d4a9aff` — FOUND (feat(02-01): update SQLAlchemy models to match migration 0002)

---
*Phase: 02-executor-and-cascade*
*Completed: 2026-04-04*
