---
phase: 02-executor-and-cascade
plan: "05"
subsystem: executor
tags: [asyncio, asyncpg, psycopg3, postgres, skip-locked, listen-notify, crash-recovery, tdd]

# Dependency graph
requires:
  - phase: 02-executor-and-cascade-03
    provides: claim_ready_stages, apply_pending_migration, check_cascade_completion, retry_stage
  - phase: 02-executor-and-cascade-04
    provides: dispatch_stage, recover_stale_active_stages
provides:
  - executor/loop.py: run_executor entry point, _listen_for_changes, _poll_loop, single_poll_cycle
  - executor/__init__.py wired to export run_executor from loop.py
  - 6 passing executor loop integration tests (EXEC-01..EXEC-04)
  - SKIP LOCKED concurrent safety verified (3 executors, 20 stages, no double dispatch)
affects:
  - phase: 03-compute-primitives (run_executor is the entry point for all phase 3 dispatch)
  - main.py (calls run_executor to boot executor)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio two-task executor: _listen_for_changes (psycopg3 LISTEN) + _poll_loop (asyncpg SKIP LOCKED)"
    - "LISTEN/NOTIFY as wake-hint only — poll loop never relies solely on NOTIFY for dispatch (D-02)"
    - "Exponential backoff: 1.0s → 2.0s → 4.0s → 5.0s cap (D-03); reset on NOTIFY or successful claim"
    - "single_poll_cycle() helper for testable iteration without starting infinite loop"
    - "actor_id propagated to recover_stale_active_stages for correct ledger attribution"

key-files:
  created:
    - executor/loop.py
  modified:
    - executor/__init__.py
    - executor/recovery.py
    - tests/test_executor_loop.py

key-decisions:
  - "single_poll_cycle() exposed as public helper in loop.py — enables concurrent executor tests without infinite loop"
  - "recover_stale_active_stages accepts optional actor_id parameter — avoids NULL violation when system-executor actor absent; falls back to identity lookup for backwards compat"

patterns-established:
  - "TDD: test bodies written first (RED), then implementation (GREEN), confirmed all 6 loop tests pass"
  - "Test isolation: claim_ready_stages returns from shared DB; tests filter by known stage IDs"
  - "Loop polls stages via single_poll_cycle in tests rather than run_executor (infinite loop)"

requirements-completed:
  - EXEC-01
  - EXEC-02
  - EXEC-03
  - EXEC-04

# Metrics
duration: 4min
completed: 2026-04-04
---

# Phase 2 Plan 5: Executor Loop Summary

**Stateless asyncio executor loop with SKIP LOCKED poll, psycopg3 LISTEN/NOTIFY wake-hint, exponential backoff, and crash recovery — all 64 tests green including 3-concurrent-executor no-double-dispatch proof**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-04T23:22:47Z
- **Completed:** 2026-04-04T23:26:49Z
- **Tasks:** 2 (1 TDD implementation + 1 auto-approved verification)
- **Files modified:** 4

## Accomplishments

- `executor/loop.py` implements `run_executor` (two asyncio tasks: `_listen_for_changes` + `_poll_loop`), `single_poll_cycle` helper, `_dispatch_and_check` per-stage task, and constants `_INITIAL_BACKOFF`/`_MAX_BACKOFF`
- `executor/__init__.py` re-exports `run_executor` from `loop.py` (replaces placeholder)
- All 6 executor loop integration tests pass: poll claims ready stages, SKIP LOCKED prevents double claim, LISTEN/NOTIFY sets wake_event within 2s, backoff doubles on empty and resets on dispatch, crash recovery returns stale active stages to pending, 3 concurrent executors process 20 stages with no stage resolved twice
- Full suite: 64 tests pass (6 loop + 5 dispatch + 12 cascade + 8 phase-1 file sets)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement executor/loop.py and wire __init__.py (TDD)** - `04a9402` (feat)
2. **Task 2: Full test suite pass** - auto-approved (auto_advance mode)

## Files Created/Modified

- `executor/loop.py` — Main async poll loop: run_executor, _listen_for_changes, _poll_loop, _dispatch_and_check, single_poll_cycle
- `executor/__init__.py` — Package entry: imports run_executor from loop.py, drops placeholder
- `executor/recovery.py` — Bug fix: accepts optional actor_id param for ledger attribution
- `tests/test_executor_loop.py` — 6 executor loop integration tests (replaces Wave 0 stubs)

## Decisions Made

- `single_poll_cycle()` exposed as public helper to allow tests to run N controlled iterations without invoking the infinite `run_executor()` loop. Tests call it directly; production uses `run_executor()`.
- `recover_stale_active_stages` signature extended with `actor_id: str | None = None` — backcompat with existing callers while enabling correct ledger attribution from the poll loop. Avoids NULL constraint violation when `system-executor` actor identity is absent in test DB.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] recover_stale_active_stages NULL actor_id violation**
- **Found during:** Task 1 GREEN phase (test_crash_recovery_reclaims_stale_active_stages)
- **Issue:** recovery.py ledger INSERT used `(SELECT id FROM actor WHERE identity = 'system-executor' LIMIT 1)` which returns NULL in test DB (no such actor). asyncpg raises `NotNullViolationError` on ledger_entry.actor_id.
- **Fix:** Added `actor_id: str | None = None` parameter to `recover_stale_active_stages`. When provided, uses it directly for the ledger INSERT. Falls back to identity lookup for backward compatibility. Updated loop.py to pass `actor_id=actor_id` at startup recovery.
- **Files modified:** executor/recovery.py, executor/loop.py
- **Verification:** test_crash_recovery_reclaims_stale_active_stages PASSED
- **Committed in:** 04a9402 (Task 1 commit)

**2. [Rule 2 - Test Isolation] test_poll_claims_ready_stages not filtering by cascade**
- **Found during:** Task 2 full suite run (64 tests together)
- **Issue:** `claim_ready_stages(pconn)` with default limit=10 may not return a specific stage_a when many other tests' stages are also pending in the shared DB. Test asserted `stage_a_id in claimed_ids` on a single claim batch — fails when other tests seeded many pending stages that fill the limit first.
- **Fix:** Changed test to run up to 5 poll cycles, collecting all claimed IDs, then assert stage_a_id was claimed in any cycle. This is robust to shared DB state without requiring per-test teardown.
- **Files modified:** tests/test_executor_loop.py
- **Verification:** All 64 tests pass in full suite run
- **Committed in:** 04a9402 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 2 test robustness)
**Impact on plan:** Both fixes essential for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All EXEC-01..EXEC-04 requirements satisfied
- `run_executor(asyncpg_dsn, psycopg_dsn, actor_id)` is the boot entry point for Phase 3
- Phase 3 compute primitives can dispatch real work sessions/judgment passes — loop.py routes via `dispatch_stage` which routes to `dispatch_narrowing` (Phase 3) or `surface_gate` (Phase 5)
- No blockers for Phase 3

---
*Phase: 02-executor-and-cascade*
*Completed: 2026-04-04*
