---
phase: 16-stage-output-propagation
plan: 01
subsystem: executor
tags: [propagation, recursive-cte, scc, upstream-context]
requirements-completed: [PROP-01, PROP-02]
duration: 10min
completed: 2026-04-06
---

# Phase 16 Plan 01: Upstream Output Injection Summary

**Executor injects all ancestor outputs into stage.input before dispatch via recursive CTE**

## Accomplishments

- Created `executor/propagation.py` with `inject_upstream_context(conn, stage)`
- Recursive CTE walks full dependency graph (not just direct parent)
- SCC key mapping: refine.scope_doc → query_text, match output → matched_sources, cohere → cohere_output, formalize → formalize_output + haskell_source, derive → test_suite + derived_tests
- Wired into both `_dispatch_and_check` and `single_poll_cycle` in loop.py
- Existing keys preserved (shallow merge, creation-time keys take priority)
- dispatch_scc_fanout unchanged (uses stored refine_stage_id, not ancestor walk)

## Key Files
- `executor/propagation.py` — inject_upstream_context + key mapping rules
- `executor/loop.py` — import + 2 injection call sites

## Self-Check: PASSED
- [x] propagation.py imports clean
- [x] loop.py imports clean with inject_upstream_context
- [x] Key mapping covers all 5 SCC stages that need upstream data
- [x] scc_handlers.py unchanged — handlers already read the right keys via _stage_input_value
