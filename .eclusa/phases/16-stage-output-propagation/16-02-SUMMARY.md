---
phase: 16-stage-output-propagation
plan: 02
subsystem: api
tags: [cascades, stages, api, pipeline-ui]
requirements-completed: [PROP-03]
duration: 5min
completed: 2026-04-06
---

# Phase 16 Plan 02: Per-Stage Status API Summary

**GET /api/cascades/{id}/stages endpoint for UI pipeline consumption**

## Accomplishments

- Added `StageDetail` model with scc_stage, display_name, depends_on, resolved_at, output_summary
- SCC display name mapping (refine → "Refine", intent_validation_fanout → "Intent Validation", etc.)
- Output summary: "N keys: key1, key2" for dicts, "N items" for lists, truncated text for strings
- Ordered by creation time (topological proxy for SCC pipeline order)

## Key Files
- `adapters/web/api/cascades.py` — new endpoint + StageDetail model + helpers

## Self-Check: PASSED
- [x] Route registered at /cascades/{cascade_id}/stages
- [x] Import succeeds
- [x] Returns scc_stage, display_name, depends_on, resolved_at, output_summary
