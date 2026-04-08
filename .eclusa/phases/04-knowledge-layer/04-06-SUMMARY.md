---
phase: 04-knowledge-layer
plan: "06"
subsystem: database
tags: [asyncpg, pgvector, knowledge-graph, facts, community, bi-temporal, TDD, label-propagation]

# Dependency graph
requires:
  - phase: 04-05
    provides: entity table rows (source/target UUIDs for fact FK references)
  - phase: 04-01
    provides: DB schema — fact and community tables with HNSW indexes

provides:
  - knowledge/facts.py: create_fact_with_invalidation() — bi-temporal fact creation + edge invalidation (KG-03, KG-04)
  - knowledge/community.py: run_label_propagation() — community detection via label propagation (KG-05)

affects: [04-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pgvector embedding in asyncpg for facts: serialize as '[v1,v2,...]' string + ::vector cast (same as entity)"
    - "Edge invalidation: UPDATE fact SET t_invalid = $now WHERE id = $old_id — never DELETE"
    - "Label propagation: pure Python over adjacency loaded from fact table (t_invalid IS NULL)"
    - "Community replace pattern: DELETE FROM community then INSERT all in single transaction"
    - "SAVEPOINT for test isolation: rollback to savepoint to restore shared DB state after cleanup"

# Key files
key-files:
  created:
    - knowledge/facts.py
    - knowledge/community.py
  modified:
    - tests/test_facts.py
    - tests/test_community.py

# Key decisions
decisions:
  - "Embedding serialized as '[v1,v2,...]' string for asyncpg compatibility — same pattern as resolve.py (no native vector codec without registration)"
  - "test_label_propagation_empty uses SAVEPOINT for isolation in shared test DB — truncates fact table within transaction then rolls back"
  - "No-embedding facts skip similarity check entirely — None embedding = no invalidation path (prevents accidental invalidation)"
  - "Communities replace atomically on each run — DELETE + INSERT in single transaction, never append"

# Metrics
metrics:
  duration: 4min
  completed_date: "2026-04-05"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
---

# Phase 04 Plan 06: Bi-temporal Facts and Community Detection Summary

**One-liner:** Bi-temporal fact creation with append-only edge invalidation (KG-03/04) and label propagation community detection writing clustered entity groups to DB (KG-05).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing tests for fact creation + edge invalidation | dcf72b4 | tests/test_facts.py |
| 1 GREEN | facts.py — bi-temporal fact creation + edge invalidation | ea69df3 | knowledge/facts.py |
| 2 RED | Failing tests for label propagation community detection | 4edba73 | tests/test_community.py |
| 2 GREEN | community.py — label propagation implementation | aec8236 | knowledge/community.py |
| fix | test_label_propagation_empty isolation via SAVEPOINT | 5331e0c | tests/test_community.py |

## What Was Built

### knowledge/facts.py

`create_fact_with_invalidation(conn, source_entity, target_entity, predicate, embedding, t_valid, source_episodes) -> str`

- Inserts a new row into the `fact` table with all four bi-temporal timestamps populated:
  - `t_valid` = caller-supplied world-time (when fact became true in the world)
  - `t_invalid` = NULL (fact is currently valid)
  - `t_created` = now() (when system learned about this fact)
  - `t_expired` = NULL (not superseded)
- When `embedding` is provided and a prior fact between the same entities has cosine similarity > 0.90 (INVALIDATION_THRESHOLD), the prior fact's `t_invalid` is set to now()
- The old fact row is **not deleted** — the append-only invariant applies (KG-04)
- Facts without embedding (`None`) skip the similarity check entirely
- Full atomicity via `conn.transaction()` wrapping invalidation + insert

### knowledge/community.py

`run_label_propagation(conn, max_iterations=10) -> None`

- Loads undirected adjacency from `fact WHERE t_invalid IS NULL` (valid edges only)
- Runs pure-Python label propagation with random shuffle on each iteration to reduce oscillation
- Early termination when stable (no label changed in the iteration)
- Groups entities by final label into community clusters
- Atomic `DELETE FROM community` + `INSERT` for each cluster in a single transaction
- Graceful empty case: if no facts exist, clears community table and returns

## Test Results

```
tests/test_facts.py::test_create_fact PASSED
tests/test_facts.py::test_invalidate_prior_fact_on_contradiction PASSED
tests/test_facts.py::test_old_fact_preserved PASSED
tests/test_facts.py::test_no_invalidation_without_embedding PASSED
tests/test_community.py::test_label_propagation_empty PASSED
tests/test_community.py::test_label_propagation_clusters PASSED
tests/test_community.py::test_label_propagation_two_components PASSED
tests/test_community.py::test_label_propagation_replaces PASSED
234 passed, 3 skipped (full suite)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_label_propagation_empty in shared test DB**
- **Found during:** Task 2 full verification run
- **Issue:** `test_label_propagation_empty` cleared the community table and asserted count=0 after `run_label_propagation()`, but the shared session-scoped test DB already had facts from prior test runs, causing the count to be 4 instead of 0
- **Fix:** Used `SAVEPOINT before_empty_test` to snapshot state, then `DELETE FROM fact` within the transaction, ran assertion, then `ROLLBACK TO SAVEPOINT` to restore facts for subsequent tests. The assertion uses the captured count variable, not a post-rollback query
- **Files modified:** tests/test_community.py
- **Commit:** 5331e0c

## Known Stubs

None — all functions are fully implemented with DB-backed assertions.

## Self-Check: PASSED

Checked file existence:
- knowledge/facts.py: FOUND
- knowledge/community.py: FOUND
- tests/test_facts.py: FOUND
- tests/test_community.py: FOUND

Checked commits:
- dcf72b4: FOUND
- ea69df3: FOUND
- 4edba73: FOUND
- aec8236: FOUND
- 5331e0c: FOUND
