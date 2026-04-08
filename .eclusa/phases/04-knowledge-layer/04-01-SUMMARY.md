---
phase: 04-knowledge-layer
plan: "01"
subsystem: schema-commons, infra
tags: [pydantic, blake3, object-store, schema-ir, openapi, prisma, graphql, protobuf, sqlglot]

# Dependency graph
requires:
  - phase: 03-compute-primitives
    provides: harness/snapshot.py SnapshotStore pattern (mirrored for ObjectStore)
provides:
  - SchemaIR Pydantic model (D-05/D-06/D-07) — canonical IR contract for all five parsers
  - ObjectStore ABC + LocalObjectStore — blake3-keyed filesystem storage (INFRA-03)
  - Parser dependencies installed: pyyaml, openapi-spec-validator, sqlglot, graphql-core, proto-schema-parser
affects: [04-02, 04-03, 04-04, 04-05, 04-06, 04-07, 04-08, 07-scc-match]

# Tech tracking
tech-stack:
  added:
    - pyyaml>=6.0.3
    - openapi-spec-validator>=0.8.4
    - sqlglot>=30.2.1
    - graphql-core>=3.2.8
    - proto-schema-parser>=2.1.0
  patterns:
    - SchemaIR as the parser/system contract — all parsers return SchemaIR, all consumers depend on SchemaIR
    - IRElement base class carries source_ref for traceability back to original spec location
    - Content-addressed storage (blake3 hexdigest) enables natural deduplication without coordination
    - 2-char hex shard prefix (key[:2]/) keeps directory sizes bounded to 256 shards

key-files:
  created:
    - schema_commons/__init__.py
    - schema_commons/ir.py
    - storage/__init__.py
    - storage/object_store.py
    - tests/test_schema_ir.py
    - tests/test_object_store.py
  modified:
    - pyproject.toml (parser deps added)
    - uv.lock

key-decisions:
  - "blake3.blake3(data).hexdigest() is the correct API — not blake3.hash(data) as shown in plan"
  - "LocalObjectStore shards files under key[:2]/ for inode efficiency at scale"
  - "ObjectStore ABC enforces interface contract for future S3/MinIO backend swap"
  - "SnapshotStore (session_id keyed) and ObjectStore (content-hash keyed) solve different problems — kept separate"

patterns-established:
  - "Pattern: IRElement base gives all IR types a source_ref field for D-06 compliance"
  - "Pattern: SchemaIR.warnings: list[ParseWarning] enables D-03 partial parse — return IR + warnings, never crash"
  - "Pattern: ObjectStore ABC allows LocalObjectStore → S3 swap with no calling-code changes"

requirements-completed: [COMMONS-01, INFRA-03]

# Metrics
duration: 4min
completed: 2026-04-05
---

# Phase 4 Plan 01: Knowledge Layer IR + Object Store Summary

**SchemaIR Pydantic IR contract (6 element types, 5 source formats) + LocalObjectStore with blake3 content-addressed filesystem storage**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-05T04:29:39Z
- **Completed:** 2026-04-05T04:33:41Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- SchemaIR canonical IR model established: IREntity, IRField, IRRelation, IROperation, IRConstraint, ParseWarning — the contract all five parsers will return and all consumers will depend on
- LocalObjectStore satisfies INFRA-03: blake3-keyed, sharded 2-char prefix, ObjectStore ABC for future backend swap
- Five parser dependencies installed: pyyaml, openapi-spec-validator, sqlglot, graphql-core, proto-schema-parser

## Task Commits

Each task was committed atomically:

1. **Task 1: Install parser deps + define SchemaIR model** - `56145c2` (feat)
2. **Task 2: LocalObjectStore with blake3 keying (INFRA-03)** - `938d553` (feat)

**Plan metadata:** (docs commit follows)

_Note: Both tasks used TDD — tests written first (RED), then implementation (GREEN)_

## Files Created/Modified

- `/home/lynxnathan/code/eclusa/schema_commons/__init__.py` - Package init
- `/home/lynxnathan/code/eclusa/schema_commons/ir.py` - SchemaIR, IREntity, IRField, IRRelation, IROperation, IRConstraint, ParseWarning Pydantic models
- `/home/lynxnathan/code/eclusa/storage/__init__.py` - Package init
- `/home/lynxnathan/code/eclusa/storage/object_store.py` - ObjectStore ABC + LocalObjectStore with blake3 keying
- `/home/lynxnathan/code/eclusa/tests/test_schema_ir.py` - 25 IR model unit tests
- `/home/lynxnathan/code/eclusa/tests/test_object_store.py` - 18 object store tests
- `/home/lynxnathan/code/eclusa/pyproject.toml` - Parser dependencies added
- `/home/lynxnathan/code/eclusa/uv.lock` - Lockfile updated

## Decisions Made

- **blake3 API deviation:** The plan referenced `blake3.hash(data).hexdigest()` but the actual API is `blake3.blake3(data).hexdigest()`. Fixed in both implementation and test — auto-corrected as Rule 1 (bug fix).
- **SnapshotStore separation:** D-25 says "reuse and extend" SnapshotStore, but the two stores solve different problems (session_id keyed vs content-hash keyed). Created ObjectStore as a parallel ABC rather than inheriting SnapshotStore — better separation of concerns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected blake3 API from blake3.hash() to blake3.blake3()**
- **Found during:** Task 2 (LocalObjectStore implementation)
- **Issue:** Plan's RESEARCH.md showed `blake3.hash(data).hexdigest()` but actual blake3 Python package API is `blake3.blake3(data).hexdigest()`
- **Fix:** Used correct API in both `storage/object_store.py` and `tests/test_object_store.py`
- **Files modified:** storage/object_store.py, tests/test_object_store.py
- **Verification:** All 18 object store tests pass
- **Committed in:** 938d553 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - API bug)
**Impact on plan:** Essential fix — wrong API would have caused immediate AttributeError at runtime. No scope creep.

## Issues Encountered

None beyond the blake3 API fix documented above.

## Known Stubs

None — all models are fully functional. SchemaIR lists default to `[]` (not hardcoded empty — they accept data correctly as proven by tests). LocalObjectStore put/get verified against real filesystem.

## Next Phase Readiness

- SchemaIR contract is defined — 04-02 through 04-06 (parsers) can now implement against this interface
- ObjectStore is ready — 04-07/04-08 or any future harness code can use LocalObjectStore for binary artifact storage
- All parser dependencies are installed — no additional setup needed for parser work
- 43 new tests added (25 schema IR + 18 object store), all green, no regressions in existing 88-test suite

## Self-Check: PASSED

All created files confirmed present on disk. Both task commits (56145c2, 938d553) confirmed in git history.

---
*Phase: 04-knowledge-layer*
*Completed: 2026-04-05*
