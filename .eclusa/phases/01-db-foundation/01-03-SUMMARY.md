---
phase: 01-db-foundation
plan: "03"
subsystem: database
tags: [sql, recursive-cte, trace-chain, as-of-timestamp, ledger, self-calibration, metrics, postgres]

# Dependency graph
requires:
  - phase: 01-02
    provides: All 13 SQLAlchemy models + initial Alembic migration with full DDL, all enum types

provides:
  - trace_chain.sql: recursive CTE with CYCLE guard walking artifact→session→stage→cascade→intent
  - as_of.sql: AS OF TIMESTAMP point-in-time ledger state retrieval
  - 8 self-calibration metric SQL files (CAL-01 through CAL-08), all parameterized with $1 lookback interval
  - db/queries/ and db/queries/metrics/ package structure with __init__.py files

affects:
  - 01-04 (test_trace_chain.py and test_as_of.py tests verify these queries against seeded data)
  - 01-05 (test_metrics.py verifies all 8 metric SQL files return non-null results)
  - Phase 2 (executor consumes trace_chain.sql for cascade graph traversal)
  - Phase 6 (back office UI consumes metric queries for cost dashboard)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Recursive CTE CYCLE guard (PG14+): CYCLE col SET is_cycle USING cycle_path — prevents infinite loop on cyclic stage.depends_on without application-level detection"
    - "Depth limit secondary guard: WHERE t.depth < 50 in recursive CTE provides hard termination even if CYCLE guard has edge cases"
    - "AS OF TIMESTAMP pattern: filter on timestamp <= $2::timestamptz ORDER BY timestamp DESC LIMIT 1 — works for any ledger FK (intent_id, cascade_id, stage_id, session_id)"
    - "Metric queries parameterized with $1 interval: allows rolling-window queries (e.g., '30 days'::interval) without hardcoded dates"
    - "NULLIF(COUNT(*), 0) pattern: prevents division-by-zero in rate calculations, returns NULL on empty window"

key-files:
  created:
    - db/queries/__init__.py
    - db/queries/trace_chain.sql
    - db/queries/as_of.sql
    - db/queries/metrics/__init__.py
    - db/queries/metrics/gate_necessity.sql
    - db/queries/metrics/orchestrator_absorption.sql
    - db/queries/metrics/resolution_latency.sql
    - db/queries/metrics/decision_durability.sql
    - db/queries/metrics/cascade_rework.sql
    - db/queries/metrics/model_convergence.sql
    - db/queries/metrics/minority_accuracy.sql
    - db/queries/metrics/fanout_necessity.sql
  modified: []

key-decisions:
  - "trace_chain.sql walks via cascade.intent_id not stage.depends_on — the recursive step follows the cascade→intent FK upward, not stage dependency edges"
  - "CYCLE guard uses intent_id as the cycle-detection column — intent_id is the root anchor; cycling on it detects malformed sub-cascade references before depth limit fires"
  - "as_of.sql matches on any ledger FK column (intent_id OR cascade_id OR stage_id OR session_id) — a single query serves all entity types"
  - "cascade_rework.sql uses cascade_state_changed with content->>'new_state' = 'completed' as the completion signal — this is the correct ledger event, not a direct cascade.state read"
  - "minority_accuracy.sql uses CROSS JOIN LATERAL over fan_out.convergence->'passes' JSONB array — this is a SQL pattern, not an application-level loop"

# Metrics
duration: 2min
completed: 2026-04-04
---

# Phase 01 Plan 03: SQL Query Files — Trace Chain and Self-Calibration Metrics Summary

**10 SQL files written: recursive CTE trace chain with CYCLE guard, AS OF TIMESTAMP ledger snapshot, and all 8 self-calibration metric queries (CAL-01..CAL-08) — each parameterized with $1 lookback interval, referencing only valid ledger_type enum values**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-04T22:13:41Z
- **Completed:** 2026-04-04T22:15:42Z
- **Tasks:** 2
- **Files modified:** 12 (12 created, 0 modified)

## Accomplishments

- `db/queries/trace_chain.sql`: recursive CTE walks artifact→cascade→intent with `CYCLE intent_id SET is_cycle USING cycle_path` guard and `depth < 50` secondary termination. Enriches output with stage, cascade, and intent context via LEFT JOINs. Tested by plan 04.
- `db/queries/as_of.sql`: point-in-time ledger query matches on any FK column (intent_id, cascade_id, stage_id, session_id) filtered by `timestamp <= $2::timestamptz`, returning most recent entry at that moment.
- All 8 metric SQL files created, each mapping to exactly one CAL-XX requirement from eclusa.md §9:
  - CAL-01 (gate_necessity.sql): gate_surfaced/gate_resolved JOIN, human_choice vs system_recommendation
  - CAL-02 (orchestrator_absorption.sql): gate_auto_resolved rate vs all gate-eligible events
  - CAL-03 (resolution_latency.sql): PERCENTILE_CONT p50/p95 of gate resolution duration in seconds
  - CAL-04 (decision_durability.sql): gate_resolved cascade subsequent cascade_migration rate
  - CAL-05 (cascade_rework.sql): cascade_state_changed(completed) → cascade_reopened rate
  - CAL-06 (model_convergence.sql): fan_out converged verdict rate
  - CAL-07 (minority_accuracy.sql): model frequency when human picks minority fan_out verdict
  - CAL-08 (fanout_necessity.sql): fan_out diverged|partial rate (models disagreed)
- All metric files use `NULLIF(COUNT(*), 0)` to prevent division-by-zero on empty lookback windows
- All metric files reference only valid `ledger_type` enum values as defined in 0001_initial_schema.py

## Task Commits

Each task was committed atomically:

1. **Task 1: trace_chain.sql + as_of.sql** - `784ad04` (feat)
2. **Task 2: 8 metric SQL files** - `9fbd198` (feat)

## Files Created/Modified

- `db/queries/__init__.py` — package marker
- `db/queries/trace_chain.sql` — recursive CTE artifact→session→stage→cascade→intent with CYCLE guard
- `db/queries/as_of.sql` — AS OF TIMESTAMP ledger state retrieval
- `db/queries/metrics/__init__.py` — package marker
- `db/queries/metrics/gate_necessity.sql` — CAL-01
- `db/queries/metrics/orchestrator_absorption.sql` — CAL-02
- `db/queries/metrics/resolution_latency.sql` — CAL-03
- `db/queries/metrics/decision_durability.sql` — CAL-04
- `db/queries/metrics/cascade_rework.sql` — CAL-05
- `db/queries/metrics/model_convergence.sql` — CAL-06
- `db/queries/metrics/minority_accuracy.sql` — CAL-07
- `db/queries/metrics/fanout_necessity.sql` — CAL-08

## Decisions Made

- trace_chain.sql recursive step walks via `cascade.intent_id` — follows the cascade→intent FK, not stage dependency edges (`stage.depends_on` is a self-referential UUID[] for within-cascade ordering, not the upward chain)
- CYCLE guard uses `intent_id` as cycle-detection column — intent is the root anchor, so cycling on it detects malformed sub-cascade back-references
- as_of.sql matches any ledger FK column — one query file handles intent, cascade, stage, or session entity lookups without branching
- cascade_rework.sql signals completion via `cascade_state_changed` + `content->>'new_state' = 'completed'` — the ledger event, not the cascade.state column (which would be a point-in-time read, not a historical query)

## Deviations from Plan

None — plan executed exactly as written. All SQL files match the specification in the plan interfaces section. All ledger_type enum values cross-checked against 0001_initial_schema.py before writing.

## Issues Encountered

None.

## Known Stubs

None — all SQL queries reference real schema columns and enum values. No placeholder data.

## Next Phase Readiness

- Plan 01-04 (ledger enforcement tests + trace chain tests + as_of tests) can begin immediately — test files for trace_chain.sql and as_of.sql can now be written with seeded data fixtures
- Plan 01-05 (metric SQL verification) can begin — all 8 metric files exist and are ready for seeded data verification via pytest

---
*Phase: 01-db-foundation*
*Completed: 2026-04-04*

## Self-Check: PASSED

Files confirmed present:
- FOUND: db/queries/__init__.py
- FOUND: db/queries/trace_chain.sql
- FOUND: db/queries/as_of.sql
- FOUND: db/queries/metrics/__init__.py
- FOUND: db/queries/metrics/gate_necessity.sql
- FOUND: db/queries/metrics/orchestrator_absorption.sql
- FOUND: db/queries/metrics/resolution_latency.sql
- FOUND: db/queries/metrics/decision_durability.sql
- FOUND: db/queries/metrics/cascade_rework.sql
- FOUND: db/queries/metrics/model_convergence.sql
- FOUND: db/queries/metrics/minority_accuracy.sql
- FOUND: db/queries/metrics/fanout_necessity.sql
- FOUND: .eclusa/phases/01-db-foundation/01-03-SUMMARY.md

Commits confirmed:
- FOUND: 784ad04 (feat: trace chain + as_of SQL)
- FOUND: 9fbd198 (feat: 8 metric SQL files)
