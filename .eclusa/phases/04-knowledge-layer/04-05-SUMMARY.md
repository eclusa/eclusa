---
phase: 04-knowledge-layer
plan: "05"
subsystem: database
tags: [asyncpg, pydantic-ai, pgvector, knowledge-graph, episode, entity, TDD]

# Dependency graph
requires:
  - phase: 04-01
    provides: DB schema — episode and entity tables with HNSW indexes
  - phase: 04-04
    provides: embedding pipeline (embed_texts) for entity embeddings

provides:
  - knowledge/ingest.py: ingest_episode() writes episode rows, returns UUID (KG-01)
  - knowledge/resolve.py: resolve_entity() by name-exact + cosine similarity (KG-02)
  - knowledge/extract.py: extract_entities_from_episode() via pydantic-ai Agent, persists new entities (KG-02)
  - RESOLUTION_THRESHOLD = 0.88 exported constant

affects: [04-06, 04-07, 04-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncpg JSONB: serialize via json.dumps() + ::jsonb cast; read returns str — decode with json.loads()"
    - "pgvector embedding in asyncpg: serialize as '[v1,v2,...]' string with ::vector cast"
    - "pydantic-ai TestModel override: agent.override(model=TestModel(custom_output_args=...)) for unit tests"
    - "Entity resolution: name-exact (LOWER()) first, then embedding cosine via <=> operator"

key-files:
  created:
    - knowledge/__init__.py
    - knowledge/ingest.py
    - knowledge/resolve.py
    - knowledge/extract.py
    - tests/test_ingest.py
    - tests/test_extract.py
    - tests/test_resolve.py
  modified: []

key-decisions:
  - "asyncpg returns JSONB columns as strings — json.loads() required for dict comparison in tests (consistent with existing pattern from prior phases)"
  - "pgvector embedding parameter for asyncpg: serialize as '[v1,v2,...]' string with ::vector cast (same pattern as 04-04)"
  - "TestModel uses custom_output_args (not custom_result_args) — verified via inspect.signature in pydantic-ai 1.77.0"
  - "resolve_entity skips embedding step when embedding is empty list — guards against accidentally querying with zero-dimension vector"

patterns-established:
  - "knowledge module: episode -> entity -> fact pipeline entry point"
  - "TDD RED-GREEN: failing import error confirms module absence before implementation"

requirements-completed: [KG-01, KG-02]

# Metrics
duration: 4min
completed: 2026-04-05
---

# Phase 04 Plan 05: Episode Ingestion + Entity Extraction/Resolution Summary

**Episode ingestion (KG-01) and entity extraction/resolution/persistence (KG-02) via pydantic-ai Agent with LOWER()-first then cosine-similarity-second entity deduplication at 0.88 threshold**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-05T04:41:44Z
- **Completed:** 2026-04-05T04:45:31Z
- **Tasks:** 2 (both TDD: RED + GREEN)
- **Files modified:** 7

## Accomplishments

- ingest_episode() inserts raw JSONB episodes to DB unchanged and returns UUID (KG-01)
- resolve_entity() prevents duplicates via case-insensitive name match, then pgvector cosine similarity (RESOLUTION_THRESHOLD = 0.88)
- extract_entities_from_episode() uses pydantic-ai Agent (output_type=EntityList), calls resolve_entity() for each result, INSERTs only truly new entities (KG-02 durable persistence)
- 11 tests fully green (3 ingest, 3 extract, 5 resolve); full suite: 226 passed, 8 skipped (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Episode ingestion tests** - `3855a3f` (test)
2. **Task 1 GREEN: ingest_episode() + knowledge/__init__.py** - `2d6c0aa` (feat)
3. **Task 2 RED: Entity extraction + resolution tests** - `b09365b` (test)
4. **Task 2 GREEN: resolve.py + extract.py** - `50f7c96` (feat)

_Note: TDD tasks have test commit followed by implementation commit_

## Files Created/Modified

- `knowledge/__init__.py` - Empty module init
- `knowledge/ingest.py` - ingest_episode(raw_data, source, reference_ts, conn) -> str UUID
- `knowledge/resolve.py` - resolve_entity(name, embedding, conn) -> str | None; RESOLUTION_THRESHOLD = 0.88
- `knowledge/extract.py` - ExtractedEntity, EntityList, extract_entities_from_episode(); pydantic-ai Agent
- `tests/test_ingest.py` - 3 DB-backed tests (creates row, raw_data preserved, schema_version)
- `tests/test_extract.py` - 3 tests using TestModel.override() (returns list, persists new, deduplicates)
- `tests/test_resolve.py` - 5 tests (exact match, case-insensitive, None, embedding similarity, threshold const)

## Decisions Made

- asyncpg returns JSONB columns as strings — test assertions need `json.loads()` decode for dict comparison
- pgvector embedding serialized as `[v1,v2,...]` string with `::vector` cast for asyncpg compatibility (consistent with 04-04 pattern)
- `TestModel` API in pydantic-ai 1.77.0 uses `custom_output_args` (not `custom_result_args`) — discovered via inspect.signature
- resolve_entity early-returns None when embedding is empty list to avoid querying with zero-dimension vector

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg JSONB returns string, not dict**
- **Found during:** Task 1 (test_ingest_episode_raw_data_preserved)
- **Issue:** asyncpg returns JSONB column as JSON string, not dict; test assertion `stored_data == raw_data` failed
- **Fix:** Added `json.loads()` decode in test when `isinstance(stored_data, str)`
- **Files modified:** tests/test_ingest.py
- **Verification:** All 3 ingest tests pass
- **Committed in:** 2d6c0aa (Task 1 GREEN commit)

**2. [Rule 1 - Bug] TestModel API mismatch — custom_result_args vs custom_output_args**
- **Found during:** Task 2 (test_extract_persists_new_entities)
- **Issue:** Plan specified `custom_result_args` but pydantic-ai 1.77.0 TestModel uses `custom_output_args`; TypeError at instantiation
- **Fix:** Used `inspect.signature(TestModel.__init__)` to find correct parameter name, updated tests
- **Files modified:** tests/test_extract.py
- **Verification:** All 3 extract tests pass
- **Committed in:** 50f7c96 (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs — API mismatches discovered during test run)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep. Core implementation matches plan exactly.

## Issues Encountered

None beyond the two auto-fixed API mismatches above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Episode ingestion and entity extraction/resolution are fully implemented and tested
- knowledge/extract.py uses placeholder empty embedding `[]` for resolve_entity — 04-06 (facts) will integrate embedding pipeline from 04-04
- Ready for 04-06: fact creation with bi-temporal timestamps and edge invalidation
- Ready for 04-07: community detection using entity graph

---
*Phase: 04-knowledge-layer*
*Completed: 2026-04-05*
