---
phase: 13-self-calibration-e2e
plan: 02
subsystem: ui/e2e
tags: [playwright, metrics, e2e, self-calibration]
dependency_graph:
  requires: []
  provides: [CAL-E2E-02]
  affects: [ui/src/pages/MetricsPage.tsx, adapters/web/api/metrics.py]
tech_stack:
  added: []
  patterns: [docker-exec-psql-seeding, playwright-e2e, recharts-assertion]
key_files:
  created:
    - ui/e2e/14-metrics-e2e.spec.ts
  modified: []
decisions:
  - "Used existing file at 14-metrics-e2e.spec.ts (found pre-written, correct implementation)"
  - "Seed via docker exec psql with ON CONFLICT DO NOTHING for idempotency"
  - "Cleanup disables/re-enables enforce_ledger_immutability trigger to allow ledger row deletion"
metrics:
  duration: ~3 minutes
  completed: 2026-04-06
  tasks_completed: 1
  files_changed: 1
---

# Phase 13 Plan 02: Metrics Dashboard E2E Summary

Playwright E2E test proving all 8 self-calibration metric cards render real computed values (not empty state) after seeding sufficient test data into the live database.

## What Was Built

`ui/e2e/14-metrics-e2e.spec.ts` — a Playwright test that:

1. Seeds metric data via `docker exec eclusa-db-1 psql` in `beforeAll`: actor, 3 intents, 3 cascades, 6 stages (4 gate + 2 narrowing), 10 ledger entries (gate_surfaced, gate_resolved, gate_auto_resolved, cascade_state_changed, cascade_reopened, cascade_migration), and 3 fan_out rows (2 converged, 1 diverged).
2. Authenticates via `getAuthToken` from `./helpers/auth`, injects JWT into localStorage.
3. Navigates to `/metrics` and waits for network idle.
4. Asserts all 8 metric card titles are visible.
5. Asserts zero instances of the empty state message "Requires 10+ resolved gates to compute." (proving all 8 metrics returned non-null values).
6. Asserts 8 `.recharts-wrapper` SVG elements are visible (all cards rendered with real charts).
7. Cleans up all seeded data in `afterAll` — disabling the `enforce_ledger_immutability` trigger temporarily for ledger row deletion.

## Test Result

1 passed in 895ms (chromium). All 8 metric cards confirmed rendering with real Recharts charts and no empty state messages.

## Data Coverage Per Metric

| Metric | Data Seeded |
|--------|-------------|
| gate_necessity | 2x gate_surfaced + 2x gate_resolved (1 with differing human_choice/system_recommendation) |
| orchestrator_absorption | 2x gate_auto_resolved + 2x gate_surfaced events |
| resolution_latency | PERCENTILE_CONT over surfaced→resolved pairs (10min→5min gap) |
| decision_durability | gate_resolved + cascade_migration on same cascade after resolution |
| cascade_rework | 2x cascade_state_changed(completed) + 1x cascade_reopened |
| model_convergence | 3x fan_out (2 converged, 1 diverged) with completed_at |
| minority_accuracy | gate_resolved with human_choice=reject matching minority pass in fan_out convergence JSONB |
| fanout_necessity | fan_out with verdict=diverged (1 of 3 = 33%) |

## Deviations from Plan

The file `ui/e2e/14-metrics-e2e.spec.ts` was already present as an untracked file in the repository with a correct, complete implementation. Verified it passes the test suite before committing.

## Self-Check: PASSED

- File exists: `/home/lynxnathan/code/eclusa/ui/e2e/14-metrics-e2e.spec.ts` — FOUND
- Commit exists: `1b263e7` — FOUND
- Test passes: 1 passed (chromium), 895ms — VERIFIED
