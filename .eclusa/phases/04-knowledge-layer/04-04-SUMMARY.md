---
phase: 04-knowledge-layer
plan: "04"
subsystem: schema_commons
tags: [embedding, pgvector, httpx, tdd, batch-processing]
requirements: [COMMONS-04]

dependency_graph:
  requires: [04-01]
  provides: [embed_texts, embed_schema_ir]
  affects: [schema_commons, entity_table]

tech_stack:
  added: []
  patterns:
    - httpx AsyncClient with mocked responses for test isolation
    - pgvector string format serialization for asyncpg compatibility
    - SELECT-then-INSERT/UPDATE upsert when no UNIQUE constraint exists

key_files:
  created:
    - schema_commons/embed.py
  modified:
    - tests/test_embed.py

decisions:
  - "SELECT-then-INSERT/UPDATE upsert because entity table has no UNIQUE constraint on name (Phase 1 DDL omitted it)"
  - "Embedding list serialized as pgvector string [0.1,0.2,...] for asyncpg compatibility — asyncpg has no native vector codec without registration"
  - "EMBEDDING_BATCH_SIZE=20 default; 25 entities → 2 API calls (20+5) verified by test"

metrics:
  duration: 3min
  completed: 2026-04-05
  tasks: 1
  files: 2
---

# Phase 04 Plan 04: Embedding Pipeline Summary

**One-liner:** Batched httpx embedding pipeline writing 1024-dim vectors to entity table via SELECT-then-upsert with pgvector string serialization for asyncpg.

## What Was Built

`schema_commons/embed.py` with two public functions:

- **`embed_texts(texts, client)`** — calls the embedding API in batches of `EMBEDDING_BATCH_SIZE` (default 20), always passes `dimensions=1024`, sorts by index to guarantee order, returns `list[list[float]]`
- **`embed_schema_ir(ir, conn, client)`** — builds one text string per IR entity, calls `embed_texts`, then upserts each entity into the `entity` table by name (SELECT-then-INSERT/UPDATE pattern)

## Decisions Made

1. **No `ON CONFLICT` clause:** The entity table has no UNIQUE constraint on `name` (Phase 1 DDL confirmed). The plan explicitly anticipated this and specified SELECT-then-INSERT/UPDATE. Tracked as deferred item DI-04-01.

2. **pgvector string format:** asyncpg cannot encode a Python `list` as `vector` without a registered custom codec. Embedding is serialized as `"[0.1,0.2,...]"` string; SQL `::vector` cast handles conversion. Simple and correct.

3. **Index-sorted API results:** API response data is sorted by `index` field before extending results, guaranteeing input-order correspondence even if the API returns out-of-order.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg cannot encode list as vector**
- **Found during:** GREEN phase (first test run)
- **Issue:** `asyncpg.exceptions.DataError: expected str, got list` when passing Python list to `$4::vector` parameter
- **Fix:** Serialize embedding list to pgvector string format `"[v1,v2,...]"` before passing to asyncpg
- **Files modified:** `schema_commons/embed.py`
- **Commit:** a52198a

**2. [Rule 1 - Bug] Test assertion iterated string as characters**
- **Found during:** GREEN phase (second test run)
- **Issue:** `list(row["embedding"])` converted the vector string to characters (4097 items), not float values
- **Fix:** Updated test to parse string with `strip("[]").split(",")` for dimension count
- **Files modified:** `tests/test_embed.py`
- **Commit:** a52198a

## Known Stubs

None — all functionality is fully implemented and tested.

## Deferred Items

**DI-04-01:** Add UNIQUE constraint on `entity.name` via migration so `ON CONFLICT (name) DO UPDATE` can be used instead of SELECT-then-upsert. Tracked in `deferred-items.md`. Safe for single-tenant single-executor deployment.

## Commits

| Hash | Message |
|------|---------|
| c90fcd4 | test(04-04): add failing tests for embed pipeline — TDD RED phase |
| a52198a | feat(04-04): implement embed.py — batched embedding pipeline + upsert to entity table |

## Self-Check

Verified below.
