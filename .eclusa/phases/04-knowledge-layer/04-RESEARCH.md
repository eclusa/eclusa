# Phase 4: Knowledge Layer - Research

**Researched:** 2026-04-05
**Domain:** Schema parsing, temporal knowledge graph, hybrid search (pgvector + pg_search BM25 + BFS RRF)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Parser architecture**
- D-01: One parser module per format under `schema_commons/parsers/` — each returns the same canonical IR
- D-02: Parsers are pure Python functions: `parse_openapi(text) -> SchemaIR`, no state, no side effects
- D-03: Parser errors are collected, not thrown — a partial parse with warnings is better than a crash
- D-04: Each parser has its own test file with real-world fixture files

**Intermediate Representation (IR)**
- D-05: SchemaIR is a Pydantic model with: `entities: list[Entity]`, `fields: list[Field]`, `relations: list[Relation]`, `operations: list[Operation]`, `constraints: list[Constraint]`
- D-06: Each IR element has a `source_ref: str` pointing back to the original spec location
- D-07: IR is JSON-serializable — stored as JSONB in the embedding row alongside the vector

**Embedding pipeline**
- D-08: Embeddings generated via API call during ingestion (httpx to embedding endpoint)
- D-09: One embedding per IR entity (not per field) — entity-level granularity for matching
- D-10: Embeddings stored in the `entity` table's `embedding` column (pgvector, HNSW index already exists)
- D-11: Embedding model configurable via environment variable (default: text-embedding-3-small)

**Temporal knowledge graph**
- D-12: Episode tier: raw ingested data preserved exactly as received, stored in `episode` table
- D-13: Entity extraction: LLM call against episode content produces structured entity list
- D-14: Entity resolution: match extracted entities against existing entities by name + embedding similarity
- D-15: Fact creation: edges between entities with bi-temporal timestamps per Phase 1 D-10
- D-16: Edge invalidation: new contradicting fact sets `t_invalid = now()` on prior fact — old fact preserved
- D-17: Community detection: label propagation on entity graph, stored in `community` table

**Hybrid search**
- D-18: Single SQL query combining three signals: pgvector cosine similarity, pg_search BM25, BFS graph traversal
- D-19: Reciprocal Rank Fusion (RRF) in SQL for combining scores — `1/(k+rank)` per signal, k=60
- D-20: BFS graph traversal via recursive CTE limited to 2 hops from seed entities
- D-21: Search returns ranked list with per-signal scores for transparency
- D-22: No external reranker service — RRF is sufficient at single-tenant scale

**Object storage**
- D-23: Local filesystem storage under `./storage/` with S3-compatible interface (abstract class)
- D-24: Files keyed by content hash (blake3) for natural deduplication
- D-25: Phase 3's SnapshotStore already defines the interface — reuse and extend

### Claude's Discretion

- Exact Pydantic model field types for IR elements
- Embedding batch size and rate limiting
- Label propagation hyperparameters (iterations, threshold)
- RRF k parameter tuning (start with k=60, calibrate later)
- Parser library choices for each format (e.g., pyyaml for OpenAPI, tree-sitter for others)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COMMONS-01 | pgvector-backed index of typed domain knowledge with HNSW indexes | HNSW indexes on `entity.embedding` and `fact.embedding` exist from Phase 1 migration — no new DDL needed |
| COMMONS-02 | Parser layer normalizes sources to IR (entities, fields, relations, operations, constraints) | D-05 locks the SchemaIR shape; pyyaml / sqlglot / graphql-core / proto-schema-parser provide the parsing substrate |
| COMMONS-03 | Parsers for: OpenAPI specs, Prisma schemas, SQL DDL, GraphQL SDL, protobuf definitions | One dedicated library per format; all pure-Python and no-compile (confirmed by source checks) |
| COMMONS-04 | Embedding pipeline stores normalized IR with vector embeddings | httpx async call to embedding API; asyncpg upsert into `entity` table's vector column |
| COMMONS-05 | Matching stage queries schema commons and returns ranked matches for domain concepts | Single hybrid search SQL function combining cosine + BM25 + BFS via RRF |
| KG-01 | Episode tier: raw ingested data preserved exactly as received with reference timestamp | `episode` table + `ingest_episode()` function |
| KG-02 | Entity tier: durable concepts extracted from episodes via LLM, with entity resolution | pydantic-ai Agent with structured output; cosine similarity threshold for resolution |
| KG-03 | Fact tier: edges between entities with bi-temporal timestamps | `fact` table with four timestamp columns — already in Phase 1 schema |
| KG-04 | Edge invalidation: new contradicting fact sets t_invalid on old fact (old fact preserved) | UPDATE `fact.t_invalid = now()` before INSERT of new fact |
| KG-05 | Community tier: clusters of strongly connected entities via label propagation | Pure-Python label propagation over entity adjacency loaded from `fact` table |
| KG-06 | Hybrid search: cosine similarity + BM25 full-text + BFS graph traversal, reranked | Single SQL CTE using pgvector `<=>`, pg_search `|||`, and recursive CTE; RRF scoring |
| INFRA-03 | Object storage for workspace snapshots (keyed by session_id) | Extend `harness/snapshot.py` SnapshotStore to use blake3 content-hash keying |
</phase_requirements>

---

## Summary

Phase 4 implements the knowledge layer: parsers that normalize five schema formats into a shared IR, an embedding pipeline that writes entity-level vectors into the existing `entity` table, a temporal knowledge graph with episode ingestion and LLM-driven entity extraction, and a hybrid search function that fuses cosine similarity, BM25, and graph traversal via RRF in a single SQL query.

All necessary database tables and indexes exist from the Phase 1 migration (HNSW on `entity.embedding` and `fact.embedding`, BM25 index `entity_bm25` on name and summary). This phase is purely application code — no schema migrations are required. The pg_search BM25 index was created using the 0.22+ USING bm25 API and queries use the v2 API (`|||` operator, `pdb.score()` function). Entity resolution is the hardest calibration problem: the similarity threshold between 0.85 and 0.92 must be chosen empirically with test fixtures.

Object storage (INFRA-03) is a small extension of the existing `SnapshotStore` in `harness/snapshot.py` — add blake3 content-hash keying as D-24 requires and a `./storage/` base path with an abstract interface for future S3 swap.

**Primary recommendation:** Build in strict wave order — IR model first, then one parser, then the embedding pipeline, then KG ingestion, then hybrid search, then object storage. Never build hybrid search before parsers exist; the test fixtures for search depend on parsers having run.

---

## Standard Stack

### Core (all already in pyproject.toml except parser libs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyyaml | 6.x | OpenAPI YAML parsing | Standard YAML parser; OpenAPI 3.x is YAML-first. Already present transitively in many Python stacks. |
| openapi-spec-validator | 0.7.x | OpenAPI spec validation | Validates 2.0, 3.0, 3.1 before parsing; raises structured errors. Python-openapi org. |
| sqlglot | 26.x | SQL DDL parsing to AST | No-dependency pure-Python SQL parser supporting 30+ dialects. Returns CREATE TABLE as `ast.Table` with columns, constraints. Most actively maintained SQL AST library as of 2026. |
| graphql-core | 3.2.x | GraphQL SDL parsing | Official Python port of graphql-js reference implementation. `parse()` returns DocumentNode AST. `build_ast_schema()` builds a typed schema. |
| proto-schema-parser | 2.1.0 | Protobuf .proto parsing | Pure-Python, no protoc dependency. Produces File/Message/Field AST. Supports proto2, proto3, editions. Actively maintained (November 2025 release). |
| httpx | 0.28.1 | Embedding API calls | Already in pyproject.toml. AsyncClient for batched embedding requests. |
| pydantic-ai | 1.77.0 | LLM entity extraction | Already in pyproject.toml. `Agent(model, output_type=EntityList)` for structured entity extraction. |
| asyncpg | 0.31.0 | DB writes in hot path | Already in pyproject.toml. Direct SQL INSERT/UPDATE for episode/entity/fact/community. |
| blake3 | 1.0.x | Content hashing for storage | Already in pyproject.toml (>=1.0.8). Used for D-24 content-addressed object store. |

### Parser Libraries to Add

```bash
uv add pyyaml openapi-spec-validator sqlglot graphql-core proto-schema-parser
```

**Version verification (run before writing Standard Stack table):**
```bash
npm view pyyaml version  # use: pip index versions pyyaml
uv add --dry-run pyyaml openapi-spec-validator sqlglot graphql-core proto-schema-parser
```

### Prisma Schema Parser — Special Case

No maintained pure-Python Prisma schema parser exists with an AST interface comparable to the other four format parsers. `prisma-client-py` generates client code but does not expose a parse-and-return API. `jmsv/prisma-to-python` is experimental.

**Recommended approach:** Hand-roll a regex/tokenizer-based Prisma parser (~150 lines). Prisma schema syntax is a regular DSL:

```
model User {
  id    Int    @id
  name  String
}
```

The parser needs: model blocks, field name/type pairs, `@id`, `@unique`, `@relation` attributes. This is Claude's Discretion per CONTEXT.md and is well within the "don't hand-roll for hard problems" threshold — Prisma's syntax is simple enough for a targeted parser.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlglot | sqlparse | sqlparse is tokenizer-only, not an AST parser; sqlglot produces typed AST nodes per dialect |
| proto-schema-parser | betterproto | betterproto requires running protoc for code generation; proto-schema-parser is parse-only |
| graphql-core | strawberry | strawberry is for building servers; graphql-core is the reference spec implementation |
| Hand-rolled Prisma parser | tree-sitter Prisma grammar | tree-sitter requires compiled C extension; too heavy for a 150-line DSL |

---

## Architecture Patterns

### Recommended Project Structure

```
schema_commons/
├── __init__.py
├── ir.py                  # SchemaIR, Entity, Field, Relation, Operation, Constraint Pydantic models
├── parsers/
│   ├── __init__.py
│   ├── openapi.py         # parse_openapi(text: str) -> SchemaIR
│   ├── prisma.py          # parse_prisma(text: str) -> SchemaIR
│   ├── sql_ddl.py         # parse_sql_ddl(text: str) -> SchemaIR
│   ├── graphql_sdl.py     # parse_graphql_sdl(text: str) -> SchemaIR
│   └── protobuf.py        # parse_protobuf(text: str) -> SchemaIR
└── embed.py               # embed_schema_ir(ir: SchemaIR, conn: asyncpg.Connection) -> None

knowledge/
├── __init__.py
├── ingest.py              # ingest_episode(raw_data, source, reference_ts, conn) -> str
├── extract.py             # extract_entities(episode_id, raw_data, conn) -> list[Entity]
├── resolve.py             # resolve_entity(name, embedding, conn) -> str | None
├── facts.py               # create_fact(), invalidate_prior_fact()
├── community.py           # run_label_propagation(conn) -> None
└── search.py              # hybrid_search(query_text, query_embedding, conn) -> list[SearchResult]

storage/
├── __init__.py
└── object_store.py        # ObjectStore ABC + LocalObjectStore(blake3-keyed)

tests/
├── test_schema_ir.py      # IR model validation
├── test_parsers_openapi.py
├── test_parsers_prisma.py
├── test_parsers_sql_ddl.py
├── test_parsers_graphql_sdl.py
├── test_parsers_protobuf.py
├── test_embed.py          # embedding pipeline with mock httpx
├── test_ingest.py         # episode ingestion
├── test_extract.py        # entity extraction (mock LLM)
├── test_resolve.py        # entity resolution (DB-backed)
├── test_facts.py          # fact creation + invalidation
├── test_community.py      # label propagation
├── test_search.py         # hybrid search (DB-backed)
└── test_object_store.py   # object store blake3 keying
```

### Pattern 1: SchemaIR Pydantic Model (D-05 through D-07)

```python
# schema_commons/ir.py
from pydantic import BaseModel
from typing import Literal

class IRElement(BaseModel):
    source_ref: str  # D-06: points back to original spec location

class IREntity(IRElement):
    name: str
    description: str | None = None
    type: Literal["model", "message", "type", "table", "interface"] = "model"

class IRField(IRElement):
    entity_name: str
    field_name: str
    field_type: str
    nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_ref: str | None = None

class IRRelation(IRElement):
    from_entity: str
    to_entity: str
    relation_type: Literal["one_to_one", "one_to_many", "many_to_many", "unknown"]

class IROperation(IRElement):
    name: str
    method: str | None = None  # GET/POST for REST, query/mutation for GraphQL
    path: str | None = None

class IRConstraint(IRElement):
    entity_name: str
    constraint_type: str
    expression: str

class ParseWarning(BaseModel):
    location: str
    message: str

class SchemaIR(BaseModel):
    """Canonical IR — JSON-serializable (D-07). Errors collected, not thrown (D-03)."""
    source_format: Literal["openapi", "prisma", "sql_ddl", "graphql_sdl", "protobuf"]
    entities: list[IREntity] = []
    fields: list[IRField] = []
    relations: list[IRRelation] = []
    operations: list[IROperation] = []
    constraints: list[IRConstraint] = []
    warnings: list[ParseWarning] = []  # D-03: partial parse with warnings
```

### Pattern 2: Parser Function Signature (D-01, D-02)

Each parser module exports exactly one public function with this signature:

```python
# schema_commons/parsers/openapi.py
import yaml
from openapi_spec_validator import validate

def parse_openapi(text: str) -> SchemaIR:
    """Parse an OpenAPI 2.0/3.x YAML or JSON spec into SchemaIR.
    Collects warnings rather than raising — D-03.
    """
    ir = SchemaIR(source_format="openapi")
    try:
        spec = yaml.safe_load(text)
        validate(spec)
    except Exception as exc:
        ir.warnings.append(ParseWarning(location="root", message=str(exc)))
        return ir  # partial parse — return what we have
    # ... walk paths, components/schemas, build IR elements
    return ir
```

```python
# schema_commons/parsers/sql_ddl.py
import sqlglot

def parse_sql_ddl(text: str) -> SchemaIR:
    ir = SchemaIR(source_format="sql_ddl")
    try:
        statements = sqlglot.parse(text)
    except Exception as exc:
        ir.warnings.append(ParseWarning(location="root", message=str(exc)))
        return ir
    for stmt in statements:
        if isinstance(stmt, sqlglot.exp.Create) and stmt.kind == "TABLE":
            # Walk columns, primary keys, foreign keys
            ...
    return ir
```

```python
# schema_commons/parsers/graphql_sdl.py
from graphql import parse as gql_parse, build_ast_schema

def parse_graphql_sdl(text: str) -> SchemaIR:
    ir = SchemaIR(source_format="graphql_sdl")
    try:
        doc = gql_parse(text)
        schema = build_ast_schema(doc)
    except Exception as exc:
        ir.warnings.append(ParseWarning(location="root", message=str(exc)))
        return ir
    for type_name, type_def in schema.type_map.items():
        if type_name.startswith("__"):
            continue  # skip introspection types
        # Walk fields, interfaces, directives
        ...
    return ir
```

```python
# schema_commons/parsers/protobuf.py
from proto_schema_parser.parser import Parser as ProtoParser

def parse_protobuf(text: str) -> SchemaIR:
    ir = SchemaIR(source_format="protobuf")
    try:
        proto_file = ProtoParser().parse(text)
    except Exception as exc:
        ir.warnings.append(ParseWarning(location="root", message=str(exc)))
        return ir
    for element in proto_file.file_elements:
        # Walk Message, Service, Field elements
        ...
    return ir
```

### Pattern 3: Embedding Pipeline (D-08 through D-11)

```python
# schema_commons/embed.py
import os
import json
import asyncpg
import httpx

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "https://api.openai.com/v1/embeddings")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "20"))

async def embed_texts(texts: list[str], client: httpx.AsyncClient) -> list[list[float]]:
    """Call embedding API in batches. Returns list of 1024-dim vectors."""
    results = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        resp = await client.post(
            EMBEDDING_URL,
            json={"model": EMBEDDING_MODEL, "input": batch, "dimensions": 1024},
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        results.extend(item["embedding"] for item in data)
    return results
```

**IMPORTANT:** The `entity` table uses `vector(1024)`. The embedding model must return exactly 1024 dimensions. For `text-embedding-3-small`, pass `"dimensions": 1024` — this model supports Matryoshka Representation Learning and can be truncated to any dimension.

### Pattern 4: pg_search v2 BM25 Query Syntax (verified from ParadeDB docs)

The Phase 1 migration created the BM25 index with the 0.22+ USING bm25 API (correct). Queries use the **v2 API** (default since 0.20.0, December 2025):

```sql
-- BM25 full-text search with score (v2 API)
SELECT id, name, summary, pdb.score(id) AS bm25_score
FROM entity
WHERE name ||| $1 OR summary ||| $1
ORDER BY pdb.score(id) DESC
LIMIT 20;
```

The `|||` operator is disjunction (OR behavior). `&&&` is conjunction (AND). `pdb.score(id)` returns the BM25 relevance score. The old `@@@` operator and `paradedb.score()` function are the legacy v1 API — do not use them in new code.

**CRITICAL:** The `||| $1` parameterized form with asyncpg works, but the search string cannot use SQL escaping tricks — pass the query string directly as the parameter value.

### Pattern 5: Hybrid Search RRF in SQL (D-18 through D-22)

```sql
-- schema_commons/queries/hybrid_search.sql
-- Three signals: cosine similarity, BM25, BFS graph traversal
-- RRF fusion: 1/(k+rank) per signal, k=60 (D-19)
-- BFS limited to 2 hops from seed entities (D-20)

WITH
  -- Signal 1: vector cosine similarity
  cosine AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS r
    FROM entity
    WHERE embedding IS NOT NULL
    LIMIT 40
  ),
  -- Signal 2: BM25 full-text (pg_search v2 API)
  bm25 AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY pdb.score(id) DESC) AS r
    FROM entity
    WHERE name ||| $2 OR summary ||| $2
    LIMIT 40
  ),
  -- Signal 3: BFS graph traversal from seed entities (2 hops, D-20)
  seed_entities AS (
    SELECT id FROM entity WHERE name ||| $2 LIMIT 5
  ),
  bfs AS (
    SELECT DISTINCT e.id, 1 AS hop
    FROM fact f
    JOIN entity e ON e.id = f.target_entity
    WHERE f.source_entity IN (SELECT id FROM seed_entities)
      AND f.t_invalid IS NULL  -- only currently valid facts
    UNION
    SELECT DISTINCT e.id, 2 AS hop
    FROM fact f
    JOIN entity e ON e.id = f.target_entity
    JOIN bfs b ON b.id = f.source_entity
    WHERE f.t_invalid IS NULL
      AND b.hop < 2
  ),
  bfs_ranked AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY MIN(hop)) AS r
    FROM bfs
    GROUP BY id
    LIMIT 40
  ),
  -- RRF fusion
  rrf AS (
    SELECT id, 1.0 / (60.0 + r) AS s FROM cosine
    UNION ALL
    SELECT id, 1.0 / (60.0 + r) AS s FROM bm25
    UNION ALL
    SELECT id, 1.0 / (60.0 + r) AS s FROM bfs_ranked
  )
SELECT
  e.id,
  e.name,
  e.type,
  e.summary,
  SUM(s) AS rrf_score
FROM rrf
JOIN entity e USING (id)
GROUP BY e.id, e.name, e.type, e.summary
ORDER BY rrf_score DESC
LIMIT $3;
```

**Note on the BFS recursive CTE:** The BFS above uses two explicit SELECTs instead of a `WITH RECURSIVE` block because the 2-hop limit is hard and simple; a recursive CTE is not needed for fixed-depth traversal. If the hop depth becomes configurable, convert to `WITH RECURSIVE` with a depth column and `CYCLE` guard (see db/queries/trace_chain.sql for the established pattern).

### Pattern 6: LLM Entity Extraction (D-13, KG-02)

```python
# knowledge/extract.py
from pydantic import BaseModel
from pydantic_ai import Agent

class ExtractedEntity(BaseModel):
    name: str
    type: str  # "person", "project", "api", "decision", "rule", etc.
    summary: str

class EntityList(BaseModel):
    entities: list[ExtractedEntity]

_agent = Agent("anthropic:claude-haiku-4-5", output_type=EntityList)  # cheap model

async def extract_entities_from_episode(raw_text: str) -> list[ExtractedEntity]:
    """Single LLM call: extract structured entity list from episode content."""
    result = await _agent.run(
        f"Extract all named entities (people, projects, APIs, business rules, "
        f"decisions) from the following content. Be concise in summaries.\n\n{raw_text}"
    )
    return result.output.entities
```

### Pattern 7: Entity Resolution (D-14, KG-02)

Entity resolution is name-first, embedding-second:

```python
# knowledge/resolve.py
import asyncpg

RESOLUTION_THRESHOLD = 0.88  # cosine similarity — calibrate with test fixtures

async def resolve_entity(
    name: str,
    embedding: list[float],
    conn: asyncpg.Connection,
) -> str | None:
    """Return existing entity_id if name matches exactly or embedding cosine >= threshold.
    Returns None if no match — caller should create a new entity.
    """
    # Step 1: exact name match
    row = await conn.fetchrow("SELECT id FROM entity WHERE LOWER(name) = LOWER($1)", name)
    if row:
        return str(row["id"])

    # Step 2: embedding similarity above threshold
    row = await conn.fetchrow(
        """
        SELECT id, 1 - (embedding <=> $1::vector) AS similarity
        FROM entity
        WHERE embedding IS NOT NULL
          AND 1 - (embedding <=> $1::vector) >= $2
        ORDER BY embedding <=> $1::vector
        LIMIT 1
        """,
        embedding,
        RESOLUTION_THRESHOLD,
    )
    return str(row["id"]) if row else None
```

### Pattern 8: Edge Invalidation (D-16, KG-04)

```python
# knowledge/facts.py
import asyncpg
from datetime import datetime, timezone

async def create_fact_with_invalidation(
    conn: asyncpg.Connection,
    source_entity: str,
    target_entity: str,
    predicate: str,
    embedding: list[float],
    t_valid: datetime,
    source_episodes: list[str],
) -> str:
    """Create a new fact. Invalidates any prior fact on same entity pair
    with a semantically contradicting predicate (detected by high embedding similarity).
    Old facts are preserved (t_invalid set, not deleted) — KG-04.
    """
    now = datetime.now(timezone.utc)
    async with conn.transaction():
        # Step 1: find similar existing facts between same entities
        similar = await conn.fetch(
            """
            SELECT id FROM fact
            WHERE source_entity = $1::uuid
              AND target_entity = $2::uuid
              AND t_invalid IS NULL
              AND 1 - (embedding <=> $3::vector) > 0.90
            """,
            source_entity, target_entity, embedding,
        )
        # Step 2: invalidate contradicting facts
        for row in similar:
            await conn.execute(
                "UPDATE fact SET t_invalid = $1 WHERE id = $2::uuid",
                now, str(row["id"]),
            )
        # Step 3: insert new fact
        ...
```

### Pattern 9: Label Propagation for Communities (D-17, KG-05)

Label propagation runs in pure Python over adjacency loaded from the `fact` table:

```python
# knowledge/community.py
import asyncpg
import random

async def run_label_propagation(
    conn: asyncpg.Connection,
    max_iterations: int = 10,
) -> None:
    """Label propagation community detection.
    1. Load entity adjacency from fact table (currently valid facts only).
    2. Assign each entity its own label initially.
    3. Each iteration: each entity adopts the plurality label of its neighbors.
    4. Repeat until stable or max_iterations reached.
    5. Write communities to community table.
    """
    rows = await conn.fetch(
        "SELECT source_entity::text, target_entity::text FROM fact WHERE t_invalid IS NULL"
    )
    # Build adjacency dict
    adjacency: dict[str, set[str]] = {}
    for row in rows:
        adjacency.setdefault(row["source_entity"], set()).add(row["target_entity"])
        adjacency.setdefault(row["target_entity"], set()).add(row["source_entity"])

    labels = {entity: entity for entity in adjacency}  # start: self-label

    for _ in range(max_iterations):
        stable = True
        entities = list(adjacency.keys())
        random.shuffle(entities)  # random update order reduces oscillation
        for entity in entities:
            neighbors = adjacency.get(entity, set())
            if not neighbors:
                continue
            # Count neighbor labels
            label_counts: dict[str, int] = {}
            for neighbor in neighbors:
                label = labels.get(neighbor, neighbor)
                label_counts[label] = label_counts.get(label, 0) + 1
            # Adopt plurality label
            new_label = max(label_counts, key=label_counts.__getitem__)
            if new_label != labels[entity]:
                labels[entity] = new_label
                stable = False
        if stable:
            break

    # Group by label and write communities
    communities: dict[str, list[str]] = {}
    for entity, label in labels.items():
        communities.setdefault(label, []).append(entity)

    async with conn.transaction():
        await conn.execute("DELETE FROM community")  # replace on each run
        for community_id, members in communities.items():
            await conn.execute(
                """
                INSERT INTO community (id, name, entity_ids, created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2::uuid[], NOW(), NOW())
                """,
                f"community_{community_id[:8]}",
                members,
            )
```

### Anti-Patterns to Avoid

- **Don't store SchemaIR as text:** Store as JSONB via `ir.model_dump_json()` — the `entity` table stores IR context alongside the embedding row.
- **Don't call embedding API per-entity synchronously:** Batch using `EMBEDDING_BATCH_SIZE` (default 20) to avoid rate limits.
- **Don't run label propagation synchronously in a web request:** Schedule it as an async task; communities are eventually consistent.
- **Don't use recursive CTE for 2-hop BFS without a depth guard:** Use the fixed-depth join pattern OR the `CYCLE` clause. Never leave a recursive CTE without termination.
- **Don't use the old pg_search v1 API (`@@@` operator, `paradedb.score()`):** The `entity_bm25` index was built with the 0.22+ API. Query with `|||` and `pdb.score(id)`.
- **Don't resolve entities by name alone:** Entities with identical names but different types (e.g., two APIs named "UserService" in different contexts) need embedding similarity to disambiguate.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenAPI YAML parsing | Custom YAML walker | pyyaml + openapi-spec-validator | $ref resolution, multi-file specs, 2.0/3.0/3.1 differences |
| SQL DDL parsing | Regex on CREATE TABLE | sqlglot | Handles all dialects, inline constraints, multi-column PKs, quoted identifiers |
| GraphQL SDL parsing | Regex on type blocks | graphql-core `parse()` | Handles interfaces, unions, directives, built-in scalars, SDL extensions |
| Protobuf parsing | Split on `message` keyword | proto-schema-parser | Nested messages, oneof, repeated, map types, services/RPCs |
| Vector similarity search ranking | Custom scoring | pgvector HNSW + `<=>` | HNSW iterative scan avoids over-filtering on filtered queries (0.8.0+) |
| BM25 search | tsvector/GIN | pg_search `|||` | pg_search BM25 produces calibrated scores suitable for RRF fusion; tsvector rank is not directly comparable |
| RRF fusion | Python post-processing | Single SQL CTE | Avoids a second round-trip; SQL GROUP BY handles multi-signal aggregation correctly |

**Key insight:** Parsing is the domain of combinatorial edge cases. A regex that handles 90% of OpenAPI specs will silently fail on `$ref`, discriminators, and `allOf`. Use the official parsing library for each format — that's exactly what they exist for.

---

## Runtime State Inventory

> Not applicable: This is a greenfield phase. No rename/refactor/migration of runtime state involved.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All modules | Yes | 3.12.8 | — |
| Docker | Testcontainers (tests) | Yes | 29.2.1 | — |
| paradedb/paradedb:latest | pg_search + pgvector (test fixture) | Yes (pulled in prior phases) | PostgreSQL 18 | — |
| OPENAI_API_KEY env var | Embedding pipeline (D-08, D-11) | Unknown — runtime env | — | Use mock httpx responses in tests; skip in CI without key |
| EMBEDDING_MODEL env var | Embedding pipeline (D-11) | Default: text-embedding-3-small | — | Default applied in code |
| Anthropic API key | LLM entity extraction (D-13) | Unknown — runtime env | — | Use pydantic-ai TestModel in tests (established pattern in Phase 3) |

**Missing dependencies with no fallback:**
- None that block test execution — all API calls are mockable via pydantic-ai TestModel and httpx RESPX.

**Missing dependencies with fallback:**
- OPENAI_API_KEY: tests mock the httpx embedding calls; real key required for integration tests only.
- Anthropic API key: pydantic-ai TestModel provides deterministic structured output for unit tests.

---

## Common Pitfalls

### Pitfall 1: Entity Resolution Threshold Too Low (false merges)
**What goes wrong:** Setting the cosine similarity threshold too low (e.g., 0.75) causes distinct entities to merge. "User" (a database entity) and "user" (a business concept) collapse into one. All downstream facts then reference the wrong entity.
**Why it happens:** Embedding space clustering — generic words like "user", "order", "payment" cluster near each other regardless of context.
**How to avoid:** Start the threshold at 0.88–0.92. Use name-exact-match as the primary gate — only fall back to embedding similarity when names differ. Provide test fixtures with known-distinct same-name entities to calibrate before shipping.
**Warning signs:** Community sizes explode (all entities merge into one community); fact predicate diversity collapses.

### Pitfall 2: pg_search v1/v2 API Mismatch
**What goes wrong:** Using `@@@` operator (v1 API) against an index created with `USING bm25` (0.22+ API). Different versions of the API are incompatible: the index and query operator must match.
**Why it happens:** ParadeDB's 0.11.0 query syntax rewrite was followed by another v2 API change in 0.20.0 (December 2025). Training data and docs may reference the old `@@@` syntax.
**How to avoid:** Always use `|||` operator and `pdb.score(id)` for new queries. The Phase 1 migration uses `USING bm25` (0.22+) for index creation. The paradedb/paradedb:latest Docker image (PostgreSQL 18) ships the current version — queries and index must use matching APIs.
**Warning signs:** BM25 queries return zero results or throw `operator does not exist` errors.

### Pitfall 3: Embedding Dimension Mismatch
**What goes wrong:** `text-embedding-3-small` without `"dimensions": 1024` returns 1536-dimension vectors by default. The `entity.embedding` column is `vector(1024)`. The INSERT fails with a dimension mismatch error.
**Why it happens:** OpenAI's newer embedding models support Matryoshka truncation but require the `dimensions` parameter explicitly.
**How to avoid:** Always pass `"dimensions": 1024` in the embedding API call. Assert in tests that returned vectors have exactly 1024 dimensions before attempting any DB write.
**Warning signs:** `ERROR: expected 1024 dimensions, not 1536` on INSERT.

### Pitfall 4: BFS Graph Traversal Without Valid-Fact Filter
**What goes wrong:** BFS traversal that doesn't filter `WHERE f.t_invalid IS NULL` returns invalidated (historical) facts as graph edges, making the entity graph appear more connected than it actually is. Communities grow incorrectly. Search results include stale relationships.
**Why it happens:** The bi-temporal schema stores both current and historical facts in the same table. A query without the validity filter returns all facts across all time.
**How to avoid:** Every query over the `fact` table that intends to read current knowledge must include `AND f.t_invalid IS NULL`. This is a convention that must appear in code review checklists.
**Warning signs:** Community detection produces unusually large or completely connected communities.

### Pitfall 5: Parser Partial Output Not Surfaced
**What goes wrong:** D-03 says parsers collect errors rather than throw. But if warnings are silently discarded, operators have no visibility into which parts of the spec failed to parse. Schema commons shows entities from 60% of the spec with no indication the remaining 40% was skipped.
**Why it happens:** The calling code logs the SchemaIR but doesn't check `ir.warnings`.
**How to avoid:** Log `ir.warnings` at WARNING level in the ingestion pipeline. Surface warning count in the episode row or a separate audit column. Write test cases that verify specific warning messages for malformed inputs.

### Pitfall 6: Label Propagation Oscillation Without Random Shuffle
**What goes wrong:** In symmetric graphs, deterministic label propagation can oscillate indefinitely — nodes flip between two equally-ranked labels on every iteration, never reaching stable communities.
**Why it happens:** When two adjacent nodes have equal-count competing labels, the update order determines which wins. If the order is deterministic, they flip on every pass.
**How to avoid:** Shuffle the entity update order randomly on each iteration (established practice for LPA). Set `max_iterations` as a hard cap. A community table that is "good enough" is better than one that never converges.

---

## Code Examples

### BM25 Query with Score

```sql
-- Source: ParadeDB docs (verified 2026-04-05), v2 API
SELECT id, name, summary, pdb.score(id) AS bm25_score
FROM entity
WHERE name ||| $1 OR summary ||| $1
ORDER BY pdb.score(id) DESC
LIMIT 20;
```

### pgvector Cosine Similarity Query

```sql
-- Source: pgvector README (HIGH confidence)
-- <=> is cosine distance; lower = more similar; 1 - (e <=> q) = cosine similarity
SELECT id, name, 1 - (embedding <=> $1::vector) AS cosine_sim
FROM entity
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1::vector
LIMIT 20;
```

### RRF Fusion Pattern

```sql
-- Source: ParadeDB hybrid search manual (MEDIUM confidence), verified pattern
WITH
  cosine AS (SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS r FROM entity WHERE embedding IS NOT NULL LIMIT 40),
  bm25   AS (SELECT id, ROW_NUMBER() OVER (ORDER BY pdb.score(id) DESC) AS r FROM entity WHERE name ||| $2 OR summary ||| $2 LIMIT 40),
  rrf    AS (SELECT id, 1.0 / (60.0 + r) AS s FROM cosine UNION ALL SELECT id, 1.0 / (60.0 + r) AS s FROM bm25)
SELECT e.id, e.name, SUM(s) AS score FROM rrf JOIN entity e USING (id) GROUP BY e.id, e.name ORDER BY score DESC LIMIT $3;
```

### pydantic-ai Structured Output (established Phase 3 pattern)

```python
# From judgment/pass_.py — exact same pattern for entity extraction
from pydantic import BaseModel
from pydantic_ai import Agent

class EntityList(BaseModel):
    entities: list[ExtractedEntity]

agent = Agent("anthropic:claude-haiku-4-5", output_type=EntityList)
result = await agent.run(prompt)
entities = result.output.entities  # validated by pydantic-ai
```

### Object Store (extend harness/snapshot.py pattern)

```python
# storage/object_store.py
import blake3
from pathlib import Path

class ObjectStore:
    """Abstract interface for blob storage (D-23). Swappable to S3 in Phase 6."""

    async def put(self, data: bytes) -> str:
        raise NotImplementedError

    async def get(self, key: str) -> bytes:
        raise NotImplementedError


class LocalObjectStore(ObjectStore):
    """Content-addressed local filesystem store. Key = blake3 hex digest (D-24)."""

    def __init__(self, base_dir: str = "./storage") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _key(self, data: bytes) -> str:
        return blake3.blake3(data).hexdigest()

    async def put(self, data: bytes) -> str:
        key = self._key(data)
        path = self._base / key[:2] / key  # two-level sharding avoids large flat dirs
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        path = self._base / key[:2] / key
        return path.read_bytes()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pg_search `@@@` operator + `paradedb.score()` | `|||` / `&&&` / `###` operators + `pdb.score()` | v0.20.0 (Dec 2025) | v1 API queries fail against v2 indexes |
| pg_search `paradedb.create_bm25()` CALL | `CREATE INDEX USING bm25(...)` | v0.22+ | Phase 1 migration already uses new API |
| pgvector IVFFlat for HNSW workloads | HNSW (all new projects) | 0.5.0+ | HNSW has better recall/speed; Phase 1 already uses HNSW |
| External vector DB for knowledge graphs | pgvector in same Postgres instance | 2024+ | Eliminates synchronization lag, preserves ACID guarantees |
| NetworkX for community detection | Pure Python label propagation (in-process) | Project preference | No heavy graph library dependency; adequate at single-tenant scale |

**Deprecated/outdated:**
- `paradedb.score()`: Replaced by `pdb.score()` in v2 API.
- `@@@` operator: The old v1 query operator, replaced by typed operators (`|||`, `&&&`, etc.).
- IVFFlat for schema commons: HNSW is the current recommended index type for read-heavy similarity search.

---

## Open Questions

1. **pg_search `|||` with asyncpg parameterization**
   - What we know: `|||` is the v2 API disjunction operator; asyncpg uses `$1` positional parameters.
   - What's unclear: Whether asyncpg sends the parameter as a typed string that pg_search's `|||` operator correctly accepts, or whether a cast is needed (e.g., `name ||| $1::text`).
   - Recommendation: Write a targeted integration test in Wave 0 that executes a BM25 `|||` query with a positional parameter against the testcontainer DB. If it fails, try `$1::text` cast.

2. **Embedding API rate limits in batch ingestion**
   - What we know: OpenAI `text-embedding-3-small` has rate limits (tokens per minute, requests per minute).
   - What's unclear: Whether the default batch size of 20 is safe under rapid ingestion of many schema files.
   - Recommendation: Start with batch size 20 and add `tenacity`-based exponential backoff on 429 responses. The config is Claude's Discretion per CONTEXT.md.

3. **Entity resolution threshold calibration**
   - What we know: 0.85–0.92 is the industry-typical range for text embedding entity resolution.
   - What's unclear: The right threshold for Eclusa's domain (schema entities, business concepts, people). The optimal value depends on the embedding model's clustering behavior in this specific domain.
   - Recommendation: Start with 0.88, include it as a named constant `RESOLUTION_THRESHOLD`, and write tests with known-distinct and known-same entities at the boundary.

4. **pdb.score() availability in parameterized asyncpg queries**
   - What we know: `pdb.score(id)` is a pg_search function introduced in v2 API.
   - What's unclear: Whether it works correctly when the BM25 query is part of a larger CTE (as in the hybrid search query), not a standalone top-level `WHERE` clause.
   - Recommendation: Test the full hybrid search CTE against the testcontainer before committing it to the plan. Simpler fallback: run BM25 and cosine as separate queries and merge in Python if the SQL fusion fails.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio 1.3.0+ |
| Config file | `pytest.ini` — `asyncio_mode = auto` |
| Quick run command | `pytest tests/test_schema_ir.py tests/test_parsers_openapi.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMMONS-01 | HNSW index on entity.embedding exists and returns results | integration | `pytest tests/test_embed.py -x` | Wave 0 |
| COMMONS-02 | SchemaIR Pydantic model validates and serializes | unit | `pytest tests/test_schema_ir.py -x` | Wave 0 |
| COMMONS-03 | Each parser produces SchemaIR from real fixture files | unit | `pytest tests/test_parsers_openapi.py tests/test_parsers_sql_ddl.py ... -x` | Wave 0 |
| COMMONS-04 | Embedding pipeline writes vectors to entity table | integration | `pytest tests/test_embed.py -x` | Wave 0 |
| COMMONS-05 | Hybrid search returns ranked results for a query | integration | `pytest tests/test_search.py -x` | Wave 0 |
| KG-01 | Episode ingestion writes episode row with raw_data | integration | `pytest tests/test_ingest.py -x` | Wave 0 |
| KG-02 | Entity extraction returns EntityList; resolution finds existing entity | unit+integration | `pytest tests/test_extract.py tests/test_resolve.py -x` | Wave 0 |
| KG-03 | Fact row written with four bi-temporal timestamps | integration | `pytest tests/test_facts.py -x` | Wave 0 |
| KG-04 | Creating contradicting fact sets t_invalid on prior fact | integration | `pytest tests/test_facts.py::test_edge_invalidation -x` | Wave 0 |
| KG-05 | Label propagation assigns community ids; communities written to DB | integration | `pytest tests/test_community.py -x` | Wave 0 |
| KG-06 | Hybrid search CTE returns ranked list with per-signal scores | integration | `pytest tests/test_search.py::test_hybrid_returns_scores -x` | Wave 0 |
| INFRA-03 | LocalObjectStore put/get roundtrip with blake3 key | unit | `pytest tests/test_object_store.py -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_schema_ir.py tests/test_parsers_openapi.py -x -q` (fast unit tests)
- **Per wave merge:** `pytest tests/ -x -q` (full suite including DB integration tests)
- **Phase gate:** Full suite green before `/eclusa:verify-work`

### Wave 0 Gaps

All test files are new — none exist yet:

- [ ] `tests/test_schema_ir.py` — covers COMMONS-02
- [ ] `tests/test_parsers_openapi.py` — covers COMMONS-03 (OpenAPI)
- [ ] `tests/test_parsers_prisma.py` — covers COMMONS-03 (Prisma)
- [ ] `tests/test_parsers_sql_ddl.py` — covers COMMONS-03 (SQL DDL)
- [ ] `tests/test_parsers_graphql_sdl.py` — covers COMMONS-03 (GraphQL SDL)
- [ ] `tests/test_parsers_protobuf.py` — covers COMMONS-03 (protobuf)
- [ ] `tests/test_embed.py` — covers COMMONS-01, COMMONS-04
- [ ] `tests/test_ingest.py` — covers KG-01
- [ ] `tests/test_extract.py` — covers KG-02 (LLM extraction, mocked)
- [ ] `tests/test_resolve.py` — covers KG-02 (entity resolution)
- [ ] `tests/test_facts.py` — covers KG-03, KG-04
- [ ] `tests/test_community.py` — covers KG-05
- [ ] `tests/test_search.py` — covers COMMONS-05, KG-06
- [ ] `tests/test_object_store.py` — covers INFRA-03
- [ ] `tests/fixtures/` — real-world schema fixtures for parsers (OpenAPI, SQL DDL, GraphQL SDL, .proto, Prisma)
- [ ] Parser libraries install: `uv add pyyaml openapi-spec-validator sqlglot graphql-core proto-schema-parser`

---

## Project Constraints (from CLAUDE.md)

| Constraint | Applies to Phase 4 |
|------------|-------------------|
| Single Postgres instance — no external vector DB | All KG and schema commons data goes into existing Postgres tables |
| `uv add` for packages, never `pip install` | All new parser libs added via `uv add` |
| `asyncpg` for executor hot path; raw SQL for predictability | All DB writes in `knowledge/` use asyncpg directly, no SQLAlchemy ORM |
| `pydantic-ai` for agent harnesses | Entity extraction and any LLM calls use `pydantic-ai Agent` |
| `ruff check . && ruff format .` | Apply to all new Python files |
| `pyright` strict mode | All new modules must be type-annotated |
| `docker-compose up` single command bootstrap | Phase adds no new services; storage is local filesystem |
| `LangChain / LangGraph` — NEVER | Entity extraction uses pydantic-ai, not any chain framework |
| Qdrant / Weaviate / Chroma — NEVER | pgvector only |

---

## Sources

### Primary (HIGH confidence)

- ParadeDB docs (docs.paradedb.com/documentation/getting-started/quickstart) — v2 API `|||` operator, `pdb.score()`, `CREATE INDEX USING bm25` confirmed
- ParadeDB blog (paradedb.com/blog/v2api, December 2025) — v2 API as default since 0.20.0, operator mapping, `pdb.score()` function confirmed
- ParadeDB hybrid search manual (paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual) — RRF CTE pattern with ROW_NUMBER confirmed
- pgvector README (github.com/pgvector/pgvector) — `<=>` cosine distance operator, HNSW index confirmed
- graphql-core docs (graphql-core-3.readthedocs.io) — `parse()` + `build_ast_schema()` API confirmed
- proto-schema-parser GitHub (github.com/criccomini/proto-schema-parser) — pure Python, proto2/proto3, v2.1.0 (November 2025)
- sqlglot GitHub (github.com/tobymao/sqlglot) — no-dependency SQL AST parser, CREATE TABLE support confirmed
- pydantic-ai docs (ai.pydantic.dev/output/) — `output_type=` structured output pattern confirmed
- `db/models/knowledge.py` — exact column names and types for Episode, Entity, Fact, Community
- `alembic/versions/0001_initial_schema.py` — HNSW indexes, BM25 index DDL confirmed as created in Phase 1
- `harness/snapshot.py` — SnapshotStore pattern for object store extension
- `judgment/pass_.py` — established pydantic-ai Agent pattern for LLM calls

### Secondary (MEDIUM confidence)

- Neon pg_search docs (neon.com/docs/extensions/pg_search) — `@@@` operator shown as primary; cross-checks against ParadeDB docs reveal this is the v1 API preserved for compatibility
- DEV Community hybrid search post (dev.to, February 2026) — RRF pattern independently verified
- openapi-spec-validator GitHub (github.com/python-openapi/openapi-spec-validator, 1 week ago) — active maintenance confirmed

### Tertiary (LOW confidence, flag for validation)

- Entity resolution cosine threshold 0.88–0.92 — from AWS blog and academic papers; needs empirical validation against Eclusa's specific embedding model and domain
- Label propagation oscillation fix (random shuffle) — from Wikipedia LPA article + standard ML textbook guidance; behavior in practice depends on graph topology

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — parser library choices verified against PyPI/GitHub, pg_search v2 API verified from official ParadeDB docs
- Architecture: HIGH — all patterns grounded in existing Phase 1/3 codebase + official library docs
- Pitfalls: MEDIUM-HIGH — pg_search API mismatch and entity resolution threshold are verified risks; threshold calibration is empirical

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (parser libs stable; pg_search API may have minor updates — re-verify if paradedb/paradedb Docker image changes)
