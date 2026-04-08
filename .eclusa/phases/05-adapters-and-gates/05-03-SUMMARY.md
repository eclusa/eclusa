---
phase: 05-adapters-and-gates
plan: "03"
subsystem: executor
tags: [asyncpg, psycopg, pg_notify, adapters, executor, gate]

# Dependency graph
requires:
  - phase: 05-01
    provides: AdapterProtocol ABC, GateContext dataclass, AdapterRegistry skeleton
  - phase: 02-executor-and-cascade
    provides: dispatch.py surface_gate/resolve_gate stubs, stage table, ledger_entry table
provides:
  - Real surface_gate() dispatch via AdapterRegistry — no longer a stub
  - resolve_gate() fires pg_notify on both 'stage_changed' and 'stage_changed:{cascade_id}'
  - GateContext built from stage input fields and ECLUSA_BASE_URL env var
  - 4 green tests in test_gate_surfacing.py covering EXEC-06 and EXEC-07
affects:
  - future gate API routes (resolve endpoint fires resolve_gate)
  - executor loop (LISTEN on stage_changed catches resolution wake hints)
  - adapter implementations (email, Slack) that register against AdapterRegistry

# Tech tracking
tech-stack:
  added: []
  patterns:
    - registry.get(channel_type) lookup pattern for adapter dispatch — unknown channel_type → warn, not raise
    - pg_notify dual-channel pattern: catch-all 'stage_changed' + scoped 'stage_changed:{cascade_id}'
    - psycopg3 LISTEN connection in tests with asyncio.wait_for for bounded notification wait

key-files:
  created:
    - tests/test_gate_surfacing.py
  modified:
    - executor/dispatch.py
    - adapters/registry.py (no change — already complete from 05-01)

key-decisions:
  - "surface_gate dispatches adapter call AFTER DB transaction — adapter call failure cannot roll back DB writes; idempotent adapter design is the contract"
  - "resolve_gate fires both pg_notify channels inside the transaction — ensures notification only sent on successful commit"
  - "channel_type defaults to 'email' when not specified in stage input — safe default for existing gate stages"
  - "ECLUSA_BASE_URL env var controls resolve_url base — defaults to http://localhost:8000 for local dev"

patterns-established:
  - "Pattern: dual pg_notify on resolve — stage_changed (catch-all) + stage_changed:{cascade_id} (scoped)"
  - "Pattern: registry monkeypatching in tests — rebind dispatch_module.registry for isolation without side effects"

requirements-completed:
  - EXEC-06
  - EXEC-07

# Metrics
duration: 4min
completed: 2026-04-05
---

# Phase 05 Plan 03: AdapterRegistry + Gate Dispatch + Scoped NOTIFY Summary

**Real adapter dispatch wired into surface_gate via AdapterRegistry; resolve_gate fires dual pg_notify (catch-all + cascade-scoped) inside transaction; 4 gate surfacing tests green**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-05T05:27:29Z
- **Completed:** 2026-04-05T05:31:00Z
- **Tasks:** 2 (combined TDD RED+GREEN in one commit)
- **Files modified:** 2 (executor/dispatch.py, tests/test_gate_surfacing.py)

## Accomplishments

- Replaced Phase 2 `surface_gate` stub: now builds GateContext from stage input, looks up adapter by channel_type, calls adapter.surface_gate() after DB writes
- Added dual pg_notify to `resolve_gate`: both `stage_changed` (catch-all executor wake) and `stage_changed:{cascade_id}` (D-05 scoped signal) fired inside transaction
- Implemented 4 tests (was 4 stubs with pytestmark skip) — all pass including LISTEN/NOTIFY integration tests using psycopg3

## Task Commits

1. **Task 1+2: AdapterRegistry dispatch + NOTIFY + all 4 tests** - `aa79607` (feat)

**Plan metadata:** (to be committed as docs commit)

## Files Created/Modified

- `executor/dispatch.py` — surface_gate replaced (imports GateContext/registry, builds context, dispatches adapter); resolve_gate updated (cascade_id fetch, dual pg_notify inside transaction)
- `tests/test_gate_surfacing.py` — 4 tests: surface_gate_real_dispatch, resolve_gate_fires_notify, resolve_gate_fires_scoped_notify, gate_sibling_branch_continues

## Decisions Made

- Adapter call placed AFTER the DB transaction (not inside): adapter failure cannot roll back the DB state; idempotent adapter design is the contract per D-02.
- Both pg_notify calls placed INSIDE the resolve_gate transaction: guarantees notification only fires if DB commit succeeds.
- channel_type defaults to "email" when absent from stage input — safe fallback for pre-existing gate stages.
- ECLUSA_BASE_URL defaults to "http://localhost:8000" — overridable via env var for production deployments.

## Deviations from Plan

None — plan executed exactly as written. AdapterRegistry was already fully implemented from Plan 05-01 (no changes needed). The dispatch.py implementation matched the plan spec precisely.

## Issues Encountered

None. Full test suite: 250 passed, 8 skipped, 0 failed.

## Next Phase Readiness

- EXEC-06 and EXEC-07 are complete: executor now surfaces gates to real adapters and resolution fires scoped wake signals
- gate API route (resolve endpoint) can call resolve_gate() and the executor loop will pick up the scoped NOTIFY
- Email and Slack adapters (Plans 04, 05+) can register against the module-level registry singleton at app startup
- loop.py LISTEN on 'stage_changed' remains correct — catch-all channel covers all resolutions

---
*Phase: 05-adapters-and-gates*
*Completed: 2026-04-05*
