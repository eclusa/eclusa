# Phase 4: Knowledge Layer - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Schema commons: parsers that normalize five schema formats (OpenAPI, Prisma, SQL DDL, GraphQL SDL, protobuf) into a canonical IR, stored with vector embeddings in pgvector for semantic matching. Temporal knowledge graph: episode → entity → fact tiers with bi-temporal timestamps and edge invalidation. Hybrid search: cosine similarity + BM25 + BFS graph traversal, reranked via RRF in pure SQL. Object storage for workspace snapshots.

</domain>

<decisions>
## Implementation Decisions

### Parser architecture
- **D-01:** One parser module per format under `schema_commons/parsers/` — each returns the same canonical IR
- **D-02:** Parsers are pure Python functions: `parse_openapi(text) -> SchemaIR`, no state, no side effects
- **D-03:** Parser errors are collected, not thrown — a partial parse with warnings is better than a crash
- **D-04:** Each parser has its own test file with real-world fixture files

### Intermediate Representation (IR)
- **D-05:** SchemaIR is a Pydantic model with: `entities: list[Entity]`, `fields: list[Field]`, `relations: list[Relation]`, `operations: list[Operation]`, `constraints: list[Constraint]`
- **D-06:** Each IR element has a `source_ref: str` pointing back to the original spec location
- **D-07:** IR is JSON-serializable — stored as JSONB in the embedding row alongside the vector

### Embedding pipeline
- **D-08:** Embeddings generated via API call during ingestion (httpx to embedding endpoint)
- **D-09:** One embedding per IR entity (not per field) — entity-level granularity for matching
- **D-10:** Embeddings stored in the `entity` table's `embedding` column (pgvector, HNSW index already exists)
- **D-11:** Embedding model configurable via environment variable (default: text-embedding-3-small)

### Temporal knowledge graph
- **D-12:** Episode tier: raw ingested data preserved exactly as received, stored in `episode` table
- **D-13:** Entity extraction: LLM call against episode content produces structured entity list
- **D-14:** Entity resolution: match extracted entities against existing entities by name + embedding similarity
- **D-15:** Fact creation: edges between entities with bi-temporal timestamps per Phase 1 D-10
- **D-16:** Edge invalidation: new contradicting fact sets `t_invalid = now()` on prior fact — old fact preserved
- **D-17:** Community detection: label propagation on entity graph, stored in `community` table

### Hybrid search
- **D-18:** Single SQL query combining three signals: pgvector cosine similarity, pg_search BM25, BFS graph traversal
- **D-19:** Reciprocal Rank Fusion (RRF) in SQL for combining scores — `1/(k+rank)` per signal, k=60
- **D-20:** BFS graph traversal via recursive CTE limited to 2 hops from seed entities
- **D-21:** Search returns ranked list with per-signal scores for transparency
- **D-22:** No external reranker service — RRF is sufficient at single-tenant scale

### Object storage
- **D-23:** Local filesystem storage under `./storage/` with S3-compatible interface (abstract class)
- **D-24:** Files keyed by content hash (blake3) for natural deduplication
- **D-25:** Phase 3's SnapshotStore already defines the interface — reuse and extend

### Claude's Discretion
- Exact Pydantic model field types for IR elements
- Embedding batch size and rate limiting
- Label propagation hyperparameters (iterations, threshold)
- RRF k parameter tuning (start with k=60, calibrate later)
- Parser library choices for each format (e.g., pyyaml for OpenAPI, tree-sitter for others)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Knowledge layer specification
- `eclusa.md` §4 — Temporal knowledge layer: episode/entity/fact/community tiers
- `eclusa.md` §4.1 — Fact entity with bi-temporal timestamps, edge invalidation
- `eclusa.md` §4.2 — Hybrid search: cosine + BM25 + BFS + RRF fusion
- `eclusa.md` §3.8 — Schema commons: parser layer, IR, embedding pipeline

### Existing schema (Phase 1 output)
- `db/models/knowledge.py` — Episode, Entity, Fact, Community SQLAlchemy models
- `db/models/domain.py` — Artifact model (parsers create artifacts)
- `alembic/versions/0001_initial_schema.py` — DDL for KG tables with HNSW indexes + BM25 index

### Research findings
- `.eclusa/research/STACK.md` — pgvector 0.8.2 HNSW, pg_search BM25, RRF fusion in SQL
- `.eclusa/research/ARCHITECTURE.md` — Knowledge layer component boundaries
- `.eclusa/research/PITFALLS.md` — pgvector HNSW memory under concurrent writes, pg_search BM25 scale

### Prior phase code
- `harness/snapshot.py` — SnapshotStore interface (reuse for object storage)
- `tests/conftest.py` — Testcontainers Postgres fixture

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `db/models/knowledge.py` — Episode, Entity, Fact, Community models with all columns
- `harness/snapshot.py` — SnapshotStore abstract class (extend for general object storage)
- `tests/conftest.py` — Testcontainers fixture with pgvector + pg_search extensions
- `db/queries/trace_chain.sql` — Recursive CTE pattern (reference for BFS traversal)

### Established Patterns
- asyncpg for direct SQL (Phases 1-3)
- Pydantic models for data structures (Phase 3: VerdictModel)
- blake3 hashing (Phase 3: context_hash)
- TDD: stubs → red → implement → green (Phases 2-3)

### Integration Points
- Phase 3 `judgment/context_prep.py` — context preparation uses entity knowledge
- Phase 5 adapters will query schema commons for intent grounding
- Phase 7 SCC Match stage queries schema commons for domain concept matching

</code_context>

<specifics>
## Specific Ideas

- The RFC says parsers normalize to a single IR — the IR is the contract between parsers and the rest of the system
- pg_search BM25 index already exists on entity text columns (Phase 1 DDL) — just needs to be queried
- Hybrid search is a single SQL query, not a multi-step pipeline — keep it in one file, one function
- Entity resolution is the hard part — similarity threshold needs calibration with real data

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-knowledge-layer*
*Context gathered: 2026-04-05*
