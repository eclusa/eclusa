---
phase: 04-knowledge-layer
plan: "07"
subsystem: knowledge-layer
tags: [hybrid-search, pgvector, pg_search, BM25, BFS, RRF, schema-commons]
dependency_graph:
  requires: [04-04, 04-05, 04-06]
  provides: [KG-06, COMMONS-05, D-21]
  affects: [phase-05-adapters, phase-07-scc-match]
tech_stack:
  added: []
  patterns: [asyncpg-vector-string-serialization, single-sql-rrf-fusion, pydantic-search-result]
key_files:
  created:
    - knowledge/search.py
    - schema_commons/queries/hybrid_search.sql
  modified:
    - tests/test_search.py
decisions:
  - asyncpg requires vector embedding serialized as '[v1,v2,...]' string — no native vector codec without registration (same pattern as resolve.py, facts.py)
  - BFS uses two explicit UNION hops (not WITH RECURSIVE) — fixed 2-hop depth per D-20, simpler than RECURSIVE keyword
  - search_schema_commons delegates entirely to hybrid_search — COMMONS-05 is a thin alias, not a separate implementation
metrics:
  duration: "~3 minutes"
  completed_date: "2026-04-05"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 4 Plan 07: Hybrid Search Summary

**One-liner:** Hybrid search with cosine + BM25 + BFS via RRF in a single SQL CTE, exposing per-signal scores (cosine_score, bm25_score, bfs_score) per D-21 decision.

## What Was Built

### knowledge/search.py

`SearchResult` Pydantic model with 8 fields including per-signal scores (D-21). Two async functions:
- `hybrid_search(query_text, query_embedding, conn, limit=10)` — primary search function
- `search_schema_commons(query_text, query_embedding, conn, limit=10)` — COMMONS-05 alias

### schema_commons/queries/hybrid_search.sql

Single SQL CTE combining three ranking signals:
1. **cosine CTE**: `embedding <=> $1::vector` with `1 - cosine_distance` as cosine_score
2. **bm25 CTE**: `name ||| $2 OR summary ||| $2` with `pdb.score(id)` as bm25_score (pg_search v2 API)
3. **BFS CTEs**: `seed_entities` → 2-hop explicit UNION (not RECURSIVE) → `bfs_ranked` with `1/(60+hop)` as bfs_score
4. **rrf CTE**: `1/(60+rank)` for each signal, UNION ALL
5. **Final SELECT**: GROUP BY entity, SUM(rrf.s) for rrf_score, LEFT JOINs for per-signal scores

Parameters: `$1 = query_embedding::vector`, `$2 = query_text (text)`, `$3 = limit (int)`

## Tests

8 new tests in `tests/test_search.py`:
- `test_hybrid_search_empty_db` — empty table returns []
- `test_hybrid_search_returns_results` — "User" entity appears in results
- `test_hybrid_search_scores` — rrf_score > 0, per-signal floats >= 0.0
- `test_search_schema_commons_alias` — same results as hybrid_search
- `test_search_result_has_per_signal_scores` — SearchResult model fields
- `test_hybrid_search_ordered_by_rrf_score` — results ordered DESC
- `test_hybrid_search_empty_query_text_graceful` — no crash on empty query
- `test_bfs_score_zero_without_facts` — bfs_score=0.0 when no facts

Full suite: **242 passed**.

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| 06f21b8 | test | TDD RED — 8 failing tests for hybrid search |
| 4fb3d01 | feat | GREEN — hybrid search SQL + Python wrapper, all 8 tests pass |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg vector serialization as string**
- **Found during:** Task 1 GREEN phase (first test run)
- **Issue:** Plan comment said "pass query_embedding as list[float]" but asyncpg has no native vector codec — expects `'[v1,v2,...]'` string like all other vector params in this codebase (resolve.py, facts.py)
- **Fix:** Added `embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"` before `conn.fetch()` call
- **Files modified:** knowledge/search.py
- **Commit:** 4fb3d01

This matches the established Phase 4 pattern from STATE.md: "Embedding list serialized as pgvector string [v1,v2,...] for asyncpg compatibility — asyncpg has no native vector codec without registration"

## Success Criteria Verification

- [x] KG-06: `hybrid_search()` fuses cosine + BM25 + BFS via RRF in a single SQL query; returns ranked SearchResult list
- [x] D-21: SearchResult exposes `cosine_score`, `bm25_score`, `bfs_score` per-signal scores (all floats, 0.0 when signal absent)
- [x] COMMONS-05: `search_schema_commons()` provides matching stage query — delegates to hybrid_search
- [x] All Phase 4 tests pass — 242 passed, 0 failures
- [x] Empty entity table returns [] — no crash
- [x] Results ordered by rrf_score descending

## Known Stubs

None — implementation is complete and wired to real DB.

## Self-Check: PASSED

- knowledge/search.py: FOUND
- schema_commons/queries/hybrid_search.sql: FOUND
- tests/test_search.py: FOUND
- Commit 06f21b8 (RED): FOUND
- Commit 4fb3d01 (GREEN): FOUND
- Full test suite 242 passed: VERIFIED
