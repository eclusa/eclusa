---
phase: 23-pipeline-hardening
plan: "01"
subsystem: executor
tags: [scc, fanout, pipeline, build-mode-v2]
dependency_graph:
  requires: []
  provides: [fanout-v2-path, fanout-legacy-path-preserved]
  affects: [executor/scc_handlers.py, tests/test_scc_fanout.py]
tech_stack:
  added: []
  patterns: [input-branching, tdd-red-green]
key_files:
  created: []
  modified:
    - executor/scc_handlers.py
    - tests/test_scc_fanout.py
decisions:
  - "Branch on scope_doc presence first (v2), fall back to refine_stage_id lookup (v1), log error on neither — no new DB tables or schema changes needed"
metrics:
  duration: "2m"
  completed_date: "2026-04-07"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 2
requirements:
  - PIPE-02
---

# Phase 23 Plan 01: Fanout Handler Input Branching Summary

**One-liner:** Surgical 3-path branch in `handle_intent_validation_fanout` — scope_doc direct (v2), refine_stage_id DB lookup (v1), error+return on neither — unblocks the SCC pipeline end-to-end.

## What Was Built

`handle_intent_validation_fanout` in `executor/scc_handlers.py` previously required `refine_stage_id` in every fanout stage input, immediately bailing with `logger.error` if absent. Cascades created via `create_scc_cascade_from_refine` (the Refine agent conversation path, v2) pass `scope_doc` directly in the stage input with no `refine_stage_id`, so they were always failing at the first post-refine stage.

The fix rewrites the top of the handler to:
1. Check `stage_input.get("scope_doc")` first — if truthy, use it directly (no DB fetch)
2. Else check `stage_input.get("refine_stage_id")` — if truthy, fetch scope_doc from refine stage output via DB (legacy v1 path preserved unchanged)
3. Else log `"Fan-out stage %s has neither scope_doc nor refine_stage_id"` and return early

The `raw_intent` resolution logic below the branch is unchanged.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for v2 path and missing-inputs | 0c676f2 | tests/test_scc_fanout.py |
| 1 (GREEN) | Branching handler implementation | 2f047c7 | executor/scc_handlers.py |

## Tests

- `test_fanout_uses_scope_doc_directly` — v2 path: scope_doc in input, no DB call, correct prepared_context
- `test_fanout_missing_both_inputs_returns_early` — neither input, `run_fan_out_with_db` not called
- `test_fanout_falls_back_to_refine_stage_id` — covered by existing `test_dispatch_scc_fanout_resolves_stage_when_verdicts_converge` and `test_dispatch_scc_fanout_blocks_stage_when_verdicts_diverge` (both pass)

**Result:** 4 pass, 1 pre-existing failure (unrelated, logged to deferred-items.md)

## Deviations from Plan

### Pre-existing out-of-scope failure

**Found during:** Task 1, GREEN phase
**Issue:** `test_dispatch_scc_fanout_calls_run_fan_out_with_db_and_uses_raw_intent_fallback` hardcodes `["anthropic:claude-3-5-haiku-latest"]` but env resolves to `['openai:glm-5.1']`. Confirmed pre-existing — fails on commits before any 23-01 change.
**Action:** Logged to `.eclusa/phases/23-pipeline-hardening/deferred-items.md`. Not fixed (out-of-scope pre-existing stale assertion).

## Known Stubs

None — handler now fully wires both input paths to `run_fan_out_with_db`.

## Self-Check: PASSED
