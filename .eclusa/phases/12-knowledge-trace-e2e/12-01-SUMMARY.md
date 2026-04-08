---
phase: 12-knowledge-trace-e2e
plan: 01
subsystem: testing
tags: [e2e, knowledge-graph, hybrid-search, pgvector, bm25, openapi, fact-invalidation, bi-temporal]

# Dependency graph
requires:
  - phase: 04-schema-commons-knowledge
    provides: "Knowledge layer (parsers, embedding, hybrid search, facts, entity resolution)"
  - phase: 01-schema-bootstrap
    provides: "Entity/fact/episode tables with pgvector HNSW + pg_search BM25 indexes"
provides:
  - "E2E verification that OpenAPI ingestion, hybrid search, and fact invalidation work against live DB"
  - "Deterministic fake embedding helper for test isolation (no API key dependency)"
affects: [12-knowledge-trace-e2e, 14-metrics-calibration]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Deterministic fake 1024-dim embeddings via SHA-256 hash expansion + L2 normalization"]

key-files:
  created:
    - tests/e2e/test_knowledge_search.py
  modified: []

key-decisions:
  - "Fake embeddings via hashlib SHA-256 expansion (no numpy, no API calls) for deterministic E2E tests"
  - "Same embedding vector for contradicting facts guarantees cosine=1.0 > INVALIDATION_THRESHOLD"
  - "AS OF queries use t_created (not t_valid) for transactional timeline correctness"

patterns-established:
  - "Fake embedding pattern: hash seed text, expand to 1024 floats, L2 normalize"
  - "Knowledge E2E cleanup: delete facts first (FK), then entities, then episodes"

requirements-completed: [KG-E2E-01, KG-E2E-02]

# Metrics
duration: 2min
completed: 2026-04-06
---

# Phase 12 Plan 01: Knowledge Search E2E Summary

**OpenAPI ingestion + hybrid search (cosine+BM25+RRF) + bi-temporal fact invalidation verified against live Postgres with fake embeddings**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-06T15:49:42Z
- **Completed:** 2026-04-06T15:51:41Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- OpenAPI spec parsed to SchemaIR with entities and operations (parse_openapi verified)
- 5 entities inserted with deterministic fake 1024-dim embeddings; hybrid_search returns ranked results with cosine_score > 0, bm25_score > 0, and rrf_score > 0
- Contradicting fact correctly sets t_invalid on prior fact (old fact preserved, not deleted)
- AS OF temporal queries at two timestamps return the correct fact at each point in time

## Task Commits

Each task was committed atomically:

1. **Task 1: E2E test for OpenAPI ingestion + hybrid search + fact invalidation** - `eebc469` (test)

## Files Created/Modified
- `tests/e2e/test_knowledge_search.py` - 3 E2E tests: parse verification, hybrid search with all three signals, fact invalidation with AS OF temporal queries

## Decisions Made
- Used deterministic fake embeddings (SHA-256 hash expansion + L2 normalization) instead of calling real embedding API -- keeps tests fast, deterministic, and API-key-free
- For fact invalidation test, used identical embedding vectors for both facts to guarantee cosine similarity = 1.0, well above the INVALIDATION_THRESHOLD of 0.90
- AS OF queries check t_created (transactional timeline) not t_valid (event timeline) for correct bi-temporal semantics

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None.

## Next Phase Readiness
- Knowledge layer E2E verified: parsers, search, and fact invalidation all work against live DB
- Ready for 12-02 (trace chain E2E) which depends on cascade/ledger tables

## Self-Check: PASSED

- FOUND: tests/e2e/test_knowledge_search.py (453 lines, exceeds 200 minimum)
- FOUND: commit eebc469
- All 3 tests pass against live DB

---
*Phase: 12-knowledge-trace-e2e*
*Completed: 2026-04-06*
