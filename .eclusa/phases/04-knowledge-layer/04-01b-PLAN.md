---
phase: 04-knowledge-layer
plan: "01b"
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/test_parsers_openapi.py
  - tests/test_parsers_prisma.py
  - tests/test_parsers_sql_ddl.py
  - tests/test_parsers_graphql_sdl.py
  - tests/test_parsers_protobuf.py
  - tests/test_embed.py
  - tests/test_ingest.py
  - tests/test_extract.py
  - tests/test_resolve.py
  - tests/test_facts.py
  - tests/test_community.py
  - tests/test_search.py
  - tests/fixtures/sample.openapi.yaml
  - tests/fixtures/sample.prisma
  - tests/fixtures/sample.sql
  - tests/fixtures/sample.graphql
  - tests/fixtures/sample.proto
  - tests/fixtures/__init__.py
autonomous: true
requirements: [COMMONS-03, COMMONS-04, KG-01, KG-02, KG-03, KG-04, KG-05, KG-06]

must_haves:
  truths:
    - "All Wave 0 test stubs collect without import errors (pytest --collect-only passes)"
    - "12 stub test files are visible to pytest with no import errors"
    - "5 schema fixture files exist and are syntactically valid for their respective formats"
  artifacts:
    - path: "tests/test_parsers_openapi.py"
      provides: "Wave 0 stub for OpenAPI parser tests"
    - path: "tests/test_search.py"
      provides: "Wave 0 stub for hybrid search tests"
    - path: "tests/fixtures/sample.openapi.yaml"
      provides: "Real OpenAPI 3.0.3 fixture with 1 path and 1 schema"
    - path: "tests/fixtures/sample.prisma"
      provides: "Prisma schema fixture with 2 models and a relation"
  key_links:
    - from: "tests/test_parsers_openapi.py"
      to: "schema_commons/parsers/openapi.py"
      via: "stub — import deferred until Wave 2 plan"
      pattern: "pytestmark.*skip"
---

<objective>
Create all Wave 0 test stubs and schema fixture files so downstream plans can enter TDD immediately. Runs in parallel with 04-01 at Wave 1.

Purpose: Wave 0 stubs let subsequent plans (04-02 through 04-07) follow the established TDD pattern from Phases 2-3. Fixture files are needed by parser tests in 04-02 and 04-03.

Output: 12 stub test files + 5 fixture files. All collect without import errors.
</objective>

<execution_context>
@$HOME/.claude/eclusa/workflows/execute-plan.md
@$HOME/.claude/eclusa/templates/summary.md
</execution_context>

<context>
@.eclusa/PROJECT.md
@.eclusa/ROADMAP.md
@.eclusa/STATE.md
@.eclusa/phases/04-knowledge-layer/04-CONTEXT.md
@.eclusa/phases/04-knowledge-layer/04-RESEARCH.md

<interfaces>
From tests/conftest.py (pattern from Phase 1-3):
- Testcontainers paradedb/paradedb:latest fixture for all DB tests
- `conn` fixture returns asyncpg.Connection
- All async tests use pytest-asyncio with asyncio_mode = "auto"

Wave 0 stub pattern (from Phase 3 Plan 01):
```python
import pytest
pytestmark = pytest.mark.skip(reason="Wave 0 stub — implement in later plan")

def test_placeholder():
    pass
```
NO imports from modules that don't exist yet (schema_commons/parsers, knowledge/, schema_commons/embed).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Wave 0 test stubs + schema fixtures</name>
  <files>
    tests/test_parsers_openapi.py,
    tests/test_parsers_prisma.py,
    tests/test_parsers_sql_ddl.py,
    tests/test_parsers_graphql_sdl.py,
    tests/test_parsers_protobuf.py,
    tests/test_embed.py,
    tests/test_ingest.py,
    tests/test_extract.py,
    tests/test_resolve.py,
    tests/test_facts.py,
    tests/test_community.py,
    tests/test_search.py,
    tests/fixtures/sample.openapi.yaml,
    tests/fixtures/sample.prisma,
    tests/fixtures/sample.sql,
    tests/fixtures/sample.graphql,
    tests/fixtures/sample.proto,
    tests/fixtures/__init__.py
  </files>
  <read_first>
    - tests/conftest.py (existing test infrastructure: conn fixture, skip markers, asyncio_mode)
    - .eclusa/phases/03-compute-primitives/03-01-SUMMARY.md (Wave 0 stub pattern: pytestmark skip + no imports from non-existent modules)
    - .eclusa/phases/04-knowledge-layer/04-RESEARCH.md (project structure lines 155-197, fixture content)
  </read_first>
  <action>
    Follow the exact Wave 0 pattern from Phase 3 Plan 01: each stub file uses module-level pytestmark:
    ```python
    import pytest
    pytestmark = pytest.mark.skip(reason="Wave 0 stub — implement in later plan")
    ```
    NO imports from schema_commons/parsers, knowledge/, or schema_commons/embed (those modules don't exist yet).

    Create test stubs with placeholder test function names that match the behaviors they'll eventually test:
    - test_parsers_openapi.py: test_parse_openapi_entities, test_parse_openapi_operations, test_parse_openapi_warnings
    - test_parsers_prisma.py: test_parse_prisma_models, test_parse_prisma_relations
    - test_parsers_sql_ddl.py: test_parse_sql_ddl_tables, test_parse_sql_ddl_constraints
    - test_parsers_graphql_sdl.py: test_parse_graphql_types, test_parse_graphql_mutations
    - test_parsers_protobuf.py: test_parse_proto_messages, test_parse_proto_services
    - test_embed.py: test_embed_schema_ir, test_embed_dimension_1024, test_embed_batch
    - test_ingest.py: test_ingest_episode_creates_row, test_ingest_episode_raw_data_preserved
    - test_extract.py: test_extract_entities_returns_list, test_extract_uses_test_model
    - test_resolve.py: test_resolve_exact_name_match, test_resolve_embedding_similarity, test_resolve_none_when_no_match
    - test_facts.py: test_create_fact, test_invalidate_prior_fact_on_contradiction, test_old_fact_preserved
    - test_community.py: test_label_propagation_clusters, test_community_written_to_db
    - test_search.py: test_hybrid_search_returns_results, test_hybrid_search_scores, test_search_empty_db

    Create fixture files with minimal but real content:
    - tests/fixtures/sample.openapi.yaml: OpenAPI 3.0.3 spec with 1 path (/users GET), 1 schema (User with id+name fields)
    - tests/fixtures/sample.prisma: Prisma schema with 2 models (User, Post) with relation
    - tests/fixtures/sample.sql: CREATE TABLE user (id UUID PRIMARY KEY, name TEXT NOT NULL); CREATE TABLE post (id UUID PRIMARY KEY, user_id UUID REFERENCES user(id));
    - tests/fixtures/sample.graphql: GraphQL SDL with type User { id: ID!, name: String! }, type Query { users: [User!]! }
    - tests/fixtures/sample.proto: proto3 with message User { string id = 1; string name = 2; } and service UserService

    Create tests/fixtures/__init__.py as empty file if it doesn't exist.
  </action>
  <verify>
    <automated>uv run pytest --collect-only -q 2>&1 | tail -5</automated>
  </verify>
  <done>All stub test files collect without import errors; `pytest --collect-only` shows 12+ stub test files collected; fixture files are well-formed</done>
</task>

</tasks>

<verification>
After task completes:
1. `uv run pytest --collect-only -q 2>&1 | grep "error"` — zero import errors
2. `uv run pytest --collect-only -q 2>&1 | grep "test_parsers\|test_embed\|test_ingest\|test_extract\|test_resolve\|test_facts\|test_community\|test_search" | wc -l` — 12 or more lines
3. Fixture files exist: `ls tests/fixtures/` shows all 5 sample files
</verification>

<success_criteria>
- All 12 Wave 0 stub test files collect without errors
- 5 schema fixture files exist and are syntactically valid for their respective formats
- No regressions in existing test suite
</success_criteria>

<output>
After completion, create `.eclusa/phases/04-knowledge-layer/04-01b-SUMMARY.md`
</output>
