---
phase: 04-knowledge-layer
plan: "02"
subsystem: schema_commons
tags: [openapi, sql-ddl, graphql, pyyaml, sqlglot, graphql-core, parser, SchemaIR]

# Dependency graph
requires:
  - phase: 04-01
    provides: SchemaIR canonical IR model (ir.py), fixture files (sample.openapi.yaml, sample.sql, sample.graphql)
provides:
  - parse_openapi(text: str) -> SchemaIR — OpenAPI 3.x to SchemaIR
  - parse_sql_ddl(text: str) -> SchemaIR — SQL DDL to SchemaIR via sqlglot
  - parse_graphql_sdl(text: str) -> SchemaIR — GraphQL SDL to SchemaIR via graphql-core
  - schema_commons/parsers/ package with __init__.py
  - 37 fully green tests covering all three parsers
affects: [04-03, 04-04, 04-05, 04-06, 04-07, 04-08]

# Tech tracking
tech-stack:
  added: []  # pyyaml, sqlglot, graphql-core already in dependencies from plan 04-01
  patterns:
    - "Parser pure-function pattern: parse_X(text: str) -> SchemaIR — no IO, no side effects (D-01, D-02)"
    - "Error-as-warning pattern: never raise, collect ParseWarning and return partial IR (D-03)"
    - "source_ref dot-path pattern: each IR element points to original spec location (D-06)"
    - "TDD RED→GREEN: write failing tests importing non-existent module, then implement until green"

key-files:
  created:
    - schema_commons/parsers/__init__.py
    - schema_commons/parsers/openapi.py
    - schema_commons/parsers/sql_ddl.py
    - schema_commons/parsers/graphql_sdl.py
    - tests/test_parsers_openapi.py
    - tests/test_parsers_sql_ddl.py
    - tests/test_parsers_graphql_sdl.py
  modified: []

key-decisions:
  - "sqlglot ColumnConstraint.kind holds the actual constraint type — is_pk check uses isinstance(c.kind, exp.PrimaryKeyColumnConstraint), not isinstance(c, exp.PrimaryKeyColumnConstraint)"
  - "graphql-core str(field_def.type) gives the canonical GraphQL type string (e.g. 'ID!', '[Post!]!') — no custom _gql_type_str helper needed"
  - "GraphQL nullable detection: isinstance(field_def.type, GraphQLNonNull) is the correct check — if the top-level wrapper is NonNull, nullable=False"
  - "Query/Mutation/Subscription root types go to operations, not entities — OPERATION_ROOT_TYPES frozenset guards this boundary"

patterns-established:
  - "Parser module pattern: one public function per module, all private helpers prefixed _"
  - "Fixture-based tests: tests read from tests/fixtures/ using Path(__file__).parent / 'fixtures' / 'filename'"
  - "Malformed input tests: assert isinstance(result, SchemaIR) and len(result.warnings) >= 1 and result.entities == []"

requirements-completed: [COMMONS-02, COMMONS-03]

# Metrics
duration: 3min
completed: 2026-04-05
---

# Phase 04 Plan 02: OpenAPI + SQL DDL + GraphQL SDL parsers — SchemaIR output via pyyaml, sqlglot, graphql-core

**Three schema parsers shipping: OpenAPI 3.x, SQL DDL, and GraphQL SDL each return a canonical SchemaIR with entities, fields, relations, and operations — never raising on malformed input.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-05T04:35:45Z
- **Completed:** 2026-04-05T04:38:50Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `parse_openapi(text)` walks `components.schemas` for entities/fields and `paths` for operations; malformed YAML collects as ParseWarning
- `parse_sql_ddl(text)` uses sqlglot to walk CREATE TABLE statements; extracts PRIMARY KEY, NOT NULL, column-level REFERENCES → IREntity, IRField, IRRelation
- `parse_graphql_sdl(text)` uses graphql-core; object types → IREntity, Query/Mutation roots → IROperation; introspection and built-in scalars excluded
- 37 tests (10 + 12 + 15) covering all behaviors specified in must_haves: entities, operations, fields, nullable, primary/foreign keys, relations, source_ref, error handling

## Task Commits

Each task was committed atomically:

1. **Task 1: parse_openapi — OpenAPI 3.x to SchemaIR** - `4eef8ed` (feat)
2. **Task 2: parse_sql_ddl — SQL DDL to SchemaIR via sqlglot** - `c8ec23c` (feat)
3. **Task 3: parse_graphql_sdl — GraphQL SDL to SchemaIR via graphql-core** - `cafb8f4` (feat)

**Plan metadata:** (docs commit hash — see below)

_Note: TDD tasks have test → implementation commits per phase (tests and implementation combined in single commit per task for clarity)._

## Files Created/Modified

- `schema_commons/parsers/__init__.py` — Package marker for parsers subpackage
- `schema_commons/parsers/openapi.py` — `parse_openapi(text: str) -> SchemaIR`
- `schema_commons/parsers/sql_ddl.py` — `parse_sql_ddl(text: str) -> SchemaIR`
- `schema_commons/parsers/graphql_sdl.py` — `parse_graphql_sdl(text: str) -> SchemaIR`
- `tests/test_parsers_openapi.py` — 10 tests (replaced Wave 0 stub)
- `tests/test_parsers_sql_ddl.py` — 12 tests (replaced Wave 0 stub)
- `tests/test_parsers_graphql_sdl.py` — 15 tests (replaced Wave 0 stub)

## Decisions Made

- **sqlglot ColumnConstraint.kind API:** The constraint check uses `isinstance(c.kind, exp.PrimaryKeyColumnConstraint)` — the `.kind` attribute holds the concrete constraint type, not the `ColumnConstraint` wrapper itself. The plan's code used `isinstance(c, ...)` which works because `find_all(exp.ColumnConstraint)` returns wrappers.
- **graphql-core str() for type strings:** `str(field_def.type)` produces canonical GraphQL type strings (`ID!`, `[Post!]!`, etc.) — no custom helper needed.
- **GraphQL nullable = not NonNull at top level:** `isinstance(field_def.type, GraphQLNonNull)` correctly detects non-null. A nullable field like `user(id: ID!): User` has `User` at top level (not wrapped in NonNull).

## Deviations from Plan

None — plan executed exactly as written. The sqlglot API verification step found that `isinstance(c.kind, ...)` was the correct pattern (matching what the plan specified), and `str(field_def.type)` eliminated the need for the custom `_gql_type_str` helper from the plan's graphql_sdl action (simplification, not deviation).

## Issues Encountered

None — all three parsers worked correctly on first implementation. Test suite (215 total) ran clean with no regressions (15 pre-existing skips from Wave 0 stubs in 04-03 plans).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All three parsers ready for 04-03 (Prisma + Protobuf parsers) which runs in parallel
- `schema_commons/parsers/` package structure established — 04-03 adds `prisma.py` and `protobuf.py`
- Parser pattern (pure function, D-01/D-02/D-03/D-06) documented as established pattern for 04-03 to follow
- Full suite green — 04-04 (embedding + indexing) can import from all 5 parsers once 04-03 ships

## Self-Check: PASSED

- FOUND: schema_commons/parsers/__init__.py
- FOUND: schema_commons/parsers/openapi.py
- FOUND: schema_commons/parsers/sql_ddl.py
- FOUND: schema_commons/parsers/graphql_sdl.py
- FOUND: tests/test_parsers_openapi.py
- FOUND: tests/test_parsers_sql_ddl.py
- FOUND: tests/test_parsers_graphql_sdl.py
- FOUND commit: 4eef8ed (parse_openapi)
- FOUND commit: c8ec23c (parse_sql_ddl)
- FOUND commit: cafb8f4 (parse_graphql_sdl)

---
*Phase: 04-knowledge-layer*
*Completed: 2026-04-05*
