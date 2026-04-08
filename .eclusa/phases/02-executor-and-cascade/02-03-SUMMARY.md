---
phase: 02-executor-and-cascade
plan: "03"
subsystem: executor
tags: [asyncpg, postgres, cascade-graph, skip-locked, tdd, retry, migration, ledger]

# Dependency graph
requires:
  - phase: 02-executor-and-cascade
    plan: "01"
    provides: "Migration 0002 — failure_policy, retry_count, cascade_migration_proposal table"
  - phase: 02-executor-and-cascade
    plan: "02"
    provides: "Wave 0 stub tests in test_cascade_graph.py and test_cascade_migration.py + topology seeders"

provides:
  - executor/cascade.py with claim_ready_stages, apply_pending_migration, check_cascade_completion, retry_stage, MaxRetriesExceeded
  - executor/__init__.py exporting run_executor placeholder and cascade functions
  - 12 passing integration tests (8 cascade graph + 4 migration)
  - 'failed' state added to stage_state enum (migration 0002 + SQLAlchemy model)

affects:
  - 02-04-executor-loop
  - 02-05-dispatch

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SKIP LOCKED inside explicit conn.transaction() — asyncpg autocommit drops lock without explicit tx boundary"
    - "MaxRetriesExceeded as module-level exception class — distinguishes retry exhaustion from other errors"
    - "JSONB params must be json.dumps() strings in asyncpg — dicts raise DataError"
    - "JSONB values returned by asyncpg as strings — use json.loads() for dict operations"
    - "$N parameters in jsonb_build_object need ::text cast — asyncpg can't infer type without cast"
    - "apply_pending_migration reads cascade_migration_proposal (Pitfall 5) — not ledger_entry"
    - "depends_on validation in apply_pending_migration catches Pitfall 6 at migration time"
    - "check_cascade_completion checks failures first (eager fail policy) not after all-terminal check"
    - "Test isolation for shared DB: mark prior proposals applied before testing cross-cascade validation"

key-files:
  created:
    - executor/cascade.py
  modified:
    - executor/__init__.py
    - alembic/versions/0002_executor_schema_gaps.py
    - db/models/domain.py
    - tests/test_cascade_graph.py
    - tests/test_cascade_migration.py

key-decisions:
  - "'failed' added to stage_state enum in migration 0002 — required by executor failure tracking (D-17..D-19); missing from initial schema"
  - "check_cascade_completion checks for failed stages first (before all-terminal check) — fail_cascade policy triggers immediately on first failure, not after all stages finish"
  - "test isolation: test_migration_validates_depends_on_stage_ids_belong_to_cascade marks all prior pending proposals as applied to ensure it processes the correct (invalid) proposal"
  - "retry_stage raises MaxRetriesExceeded before any DB write — no partial state on retry exhaustion"

patterns-established:
  - "SKIP LOCKED correctness: always wrap SELECT...SKIP LOCKED + UPDATE inside conn.transaction()"
  - "asyncpg JSONB: pass as json.dumps() strings, read back with json.loads() guard"

requirements-completed:
  - CASC-01
  - CASC-02
  - CASC-03
  - CASC-04
  - CASC-05
  - CASC-06
  - CASC-07

# Metrics
duration: 9min
completed: 2026-04-04
---

# Phase 2 Plan 03: Executor Cascade Implementation Summary

**executor/cascade.py implemented via TDD — SKIP LOCKED readiness query, retry enforcement (D-19), migration apply from proposal table (Pitfall 5), cascade completion state machine — 12/12 cascade and migration tests green**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-04-04T23:11:16Z
- **Completed:** 2026-04-04T23:20:02Z
- **Tasks:** 1 (TDD — RED + GREEN phases)
- **Files modified:** 6

## Accomplishments

- Created `executor/cascade.py` with four async functions: `claim_ready_stages`, `retry_stage`, `apply_pending_migration`, `check_cascade_completion`
- `claim_ready_stages` uses `FOR UPDATE OF s SKIP LOCKED` inside `conn.transaction()` (Pitfall 1 prevention) — batch limit parameter, returns list of dicts
- `retry_stage` implements D-19: max 3 retries, `MaxRetriesExceeded` raised at limit with no DB write, each retry writes `stage_state_changed` ledger entry with retry_count
- `apply_pending_migration` reads `cascade_migration_proposal` table (Pitfall 5 — not ledger_entry), guards against active stages (D-15), validates cross-cascade depends_on references (Pitfall 6), writes immutable `cascade_migration` ledger entry
- `check_cascade_completion` handles eager fail-cascade policy (triggers immediately on first failure, not after all stages complete), `skip` policy (skips pending/blocked, completes cascade), and all-resolved happy path
- Updated `executor/__init__.py` with `run_executor` placeholder and cascade function re-exports
- Added `failed` value to `stage_state` enum via `ALTER TYPE stage_state ADD VALUE IF NOT EXISTS 'failed'` in migration 0002
- Filled all 12 test stub bodies (8 graph + 4 migration) with full assertions
- All 58 tests pass: 22 Phase 1 tests green, 12 cascade+migration tests green, 6 executor loop/dispatch stubs skipped

## Task Commits

1. **Task 1: Implement executor/cascade.py (TDD)** — `0843246`
   - executor/cascade.py (created)
   - executor/__init__.py (updated)
   - alembic/versions/0002_executor_schema_gaps.py (added failed to stage_state enum)
   - db/models/domain.py (added failed to stage_state_enum)
   - tests/test_cascade_graph.py (stubs filled, 8 tests green)
   - tests/test_cascade_migration.py (stubs filled, 4 tests green)

## Files Created/Modified

- `executor/cascade.py` — Four async functions + MaxRetriesExceeded exception + _collect_depends_on_ids helper (~380 lines)
- `executor/__init__.py` — run_executor placeholder + cascade exports
- `alembic/versions/0002_executor_schema_gaps.py` — Added Step 0: ALTER TYPE stage_state ADD VALUE 'failed'
- `db/models/domain.py` — Added 'failed' to stage_state_enum tuple
- `tests/test_cascade_graph.py` — All 8 stubs filled with full test bodies
- `tests/test_cascade_migration.py` — All 4 stubs filled with full test bodies

## Decisions Made

- `failed` added to `stage_state` enum: the plan spec listed `failed` as a terminal state but the migration 0002 (and 0001) did not include it. Added via `ALTER TYPE...ADD VALUE IF NOT EXISTS` in migration 0002 Step 0. This is not reversal-safe (Postgres cannot remove enum values) but the value is correct and required.
- `check_cascade_completion` uses an **eager failure check**: checks `failed_count > 0` before the all-terminal check. This means `fail_cascade` policy triggers immediately when any stage fails (even if other stages are still `pending`). The alternative (wait until all terminal) would delay cascade failure signaling unnecessarily.
- `apply_pending_migration` uses `SKIP LOCKED` on the proposal SELECT — prevents double-migration under concurrent executors.
- Test isolation in `test_migration_validates_depends_on_stage_ids_belong_to_cascade`: marks all prior pending proposals as applied before inserting the invalid one. Without this, a prior test's proposal (left pending due to active stages in that cascade) would be processed first, and the validation test's invalid proposal would never be reached.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added 'failed' to stage_state enum**
- **Found during:** Task 1 GREEN phase — tests using `UPDATE stage SET state = 'failed'` raised `InvalidTextRepresentationError`
- **Issue:** `stage_state` enum had values `pending, active, blocked, resolved, skipped` — no `failed`. The plan spec and interfaces block explicitly listed `failed` as a terminal state value. The 0001 and 0002 migrations both omitted it.
- **Fix:** Added `op.execute("ALTER TYPE stage_state ADD VALUE IF NOT EXISTS 'failed'")` as Step 0 in migration 0002 upgrade. Added `'failed'` to `stage_state_enum` in `db/models/domain.py`.
- **Files modified:** `alembic/versions/0002_executor_schema_gaps.py`, `db/models/domain.py`
- **Commit:** `0843246`

**2. [Rule 1 - Bug] asyncpg JSONB parameter handling**
- **Found during:** Task 1 GREEN phase — passing Python `dict` to a JSONB parameter raised `DataError: expected str, got dict`
- **Issue:** asyncpg requires JSONB parameters as JSON strings, not Python dicts. All tests and `apply_pending_migration` that passed dicts directly to JSONB params needed `json.dumps()` wrapping.
- **Fix:** Added `import json` to `cascade.py` and test files. Wrapped all JSONB parameters with `json.dumps()`. Added `json.loads()` guard for reading back JSONB values (asyncpg returns JSONB as strings in this environment).
- **Files modified:** `executor/cascade.py`, `tests/test_cascade_graph.py`, `tests/test_cascade_migration.py`
- **Commit:** `0843246`

**3. [Rule 1 - Bug] asyncpg IndeterminateDatatypeError for $N in jsonb_build_object**
- **Found during:** Task 1 GREEN phase — `jsonb_build_object('key', $3)` raised `IndeterminateDatatypeError: could not determine data type of parameter $3`
- **Issue:** asyncpg cannot infer Python `str` type when used inside `jsonb_build_object()`. Requires `$3::text` explicit cast.
- **Fix:** Added `::text` cast to all string parameters inside `jsonb_build_object()` calls in `check_cascade_completion`.
- **Files modified:** `executor/cascade.py`
- **Commit:** `0843246`

**4. [Rule 1 - Bug] check_cascade_completion — eager failure policy**
- **Found during:** Task 1 GREEN phase — `test_cascade_fails_when_stage_fails_and_policy_is_fail_cascade` returned cascade still `active` after marking stage A `failed`
- **Issue:** Original logic checked `non_terminal > 0` first and returned early. With stage A `failed` and B/C still `pending`, the function returned without acting. The plan spec says `check_cascade_completion marks cascade failed and remaining stages skipped` when a stage fails with `fail_cascade` policy — this should be immediate.
- **Fix:** Reorganized `check_cascade_completion` to check for `failed_count > 0` BEFORE the all-terminal check. Failure policy triggers immediately when any stage fails.
- **Files modified:** `executor/cascade.py`
- **Commit:** `0843246`

**5. [Rule 2 - Test isolation] test_migration_validates_depends_on_stage_ids_belong_to_cascade**
- **Found during:** Task 1 GREEN phase — test passed in isolation but failed in full suite
- **Issue:** `apply_pending_migration` processes proposals in `created_at ASC` order. Prior test runs left proposals in `pending` state for cascades that had `active` stages (from `claim_ready_stages`). The validation test's proposal was never reached because older proposals returned `False` first.
- **Fix:** Added `UPDATE cascade_migration_proposal SET status = 'applied' WHERE status = 'pending'` at the start of the test to clean up prior pending proposals before inserting the invalid one.
- **Files modified:** `tests/test_cascade_migration.py`
- **Commit:** `0843246`

## Known Stubs

None — `run_executor` in `executor/__init__.py` is a documented placeholder (not a silent empty function presented to UI). The plan explicitly states it provides a "Package init — exports run_executor entry point" and the docstring says "Real loop implemented in loop.py (Phase 2 Plan 04)".

## Self-Check: PASSED

- `executor/cascade.py` — FOUND
- `executor/__init__.py` — FOUND (updated)
- `alembic/versions/0002_executor_schema_gaps.py` — FOUND (updated: 'failed' in stage_state)
- `db/models/domain.py` — FOUND (updated: 'failed' in stage_state_enum)
- `tests/test_cascade_graph.py` — FOUND (8 tests, all PASSED)
- `tests/test_cascade_migration.py` — FOUND (4 tests, all PASSED)
- `02-03-SUMMARY.md` — FOUND
- Commit `0843246` — FOUND (feat(02-03): implement executor/cascade.py with TDD)
- grep "FOR UPDATE OF s SKIP LOCKED" executor/cascade.py — LINE 52 FOUND
- grep "conn.transaction()" executor/cascade.py — 4 LINES FOUND
- grep "retry_count" executor/cascade.py — 8 LINES FOUND
- grep "MaxRetriesExceeded" executor/cascade.py — 3 LINES FOUND
- grep "cascade_migration_proposal" executor/cascade.py — 3 LINES FOUND
- uv run pytest tests/test_cascade_graph.py tests/test_cascade_migration.py — 12 PASSED
- uv run pytest tests/test_schema.py tests/test_ledger.py — 22 PASSED

---
*Phase: 02-executor-and-cascade*
*Completed: 2026-04-04*
