"""E2E tests for knowledge layer: OpenAPI ingestion, hybrid search, fact invalidation.

Proves:
  - KG-E2E-01: OpenAPI spec parsed to SchemaIR -> entities inserted with embeddings ->
    hybrid search returns ranked results with cosine, BM25, and RRF scores all non-zero.
  - KG-E2E-02: Contradicting fact invalidates prior fact (t_invalid set) and AS OF
    temporal queries return correct facts at different timestamps.

Uses FAKE embeddings (deterministic 1024-dim vectors via hash seeding) -- never calls
a real embedding API.  All tests clean up their own data via try/finally.
"""

import asyncio
import hashlib
import math
import struct
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest

from knowledge.facts import create_fact_with_invalidation
from knowledge.search import hybrid_search
from schema_commons.parsers.openapi import parse_openapi

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Fake embedding helpers (stdlib only, no numpy)
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 1024


def _fake_embedding(seed_text: str) -> list[float]:
    """Generate a deterministic 1024-dim unit vector from a text seed.

    Uses SHA-256 digest expanded via counter hashing to fill 1024 floats in
    [-1, 1], then L2-normalises so cosine similarity works correctly.
    """
    raw: list[float] = []
    block = 0
    while len(raw) < EMBEDDING_DIM:
        h = hashlib.sha256(f"{seed_text}:{block}".encode()).digest()
        # Each SHA-256 digest = 32 bytes = 8 floats (4 bytes each via struct)
        for i in range(0, 32, 4):
            # Unpack as unsigned 32-bit int, map to [-1, 1]
            val = struct.unpack("<I", h[i : i + 4])[0]
            raw.append((val / 0xFFFFFFFF) * 2 - 1)
        block += 1

    raw = raw[:EMBEDDING_DIM]

    # L2 normalise
    norm = math.sqrt(sum(v * v for v in raw))
    if norm > 0:
        raw = [v / norm for v in raw]
    return raw


# ---------------------------------------------------------------------------
# Rich OpenAPI spec for search differentiation (5 entities, multiple ops)
# ---------------------------------------------------------------------------

RICH_OPENAPI_SPEC = """\
openapi: "3.0.3"
info:
  title: E-Commerce API
  version: "2.0.0"
paths:
  /users:
    get:
      operationId: listUsers
      summary: List all users
      responses:
        "200":
          description: OK
  /users/{id}:
    get:
      operationId: getUser
      summary: Get a single user by ID
      responses:
        "200":
          description: OK
  /orders:
    post:
      operationId: createOrder
      summary: Create a new order
      responses:
        "201":
          description: Created
  /products:
    get:
      operationId: listProducts
      summary: List products in the catalog
      responses:
        "200":
          description: OK
  /payments:
    post:
      operationId: processPayment
      summary: Process a payment for an order
      responses:
        "200":
          description: OK
  /inventory:
    get:
      operationId: checkInventory
      summary: Check inventory levels
      responses:
        "200":
          description: OK
components:
  schemas:
    User:
      type: object
      description: "A registered user of the platform"
      required: [id, name, email]
      properties:
        id:
          type: integer
        name:
          type: string
        email:
          type: string
    Order:
      type: object
      description: "A purchase order placed by a user"
      required: [id, user_id, total]
      properties:
        id:
          type: integer
        user_id:
          type: integer
        total:
          type: number
    Product:
      type: object
      description: "A product available in the catalog"
      required: [id, name, price]
      properties:
        id:
          type: integer
        name:
          type: string
        price:
          type: number
    Payment:
      type: object
      description: "A payment transaction for an order"
      required: [id, order_id, amount]
      properties:
        id:
          type: integer
        order_id:
          type: integer
        amount:
          type: number
    Inventory:
      type: object
      description: "Inventory tracking for a product"
      required: [id, product_id, quantity]
      properties:
        id:
          type: integer
        product_id:
          type: integer
        quantity:
          type: integer
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def e2e_pool():
    """Per-test asyncpg pool connected to the live docker-compose DB."""
    from tests.e2e.conftest import E2E_DSN

    try:
        pool = await asyncpg.create_pool(E2E_DSN, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"docker-compose db not running: {exc}")
        return
    yield pool
    await pool.close()


@pytest.fixture
async def db_conn(e2e_pool):
    """Per-test asyncpg connection from the pool."""
    async with e2e_pool.acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Test 1: OpenAPI parse verification (pure, no DB)
# ---------------------------------------------------------------------------


async def test_openapi_parse_to_schema_ir():
    """Parse sample.openapi.yaml and verify SchemaIR contains expected entities/ops."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample.openapi.yaml"
    text = fixture_path.read_text()

    ir = parse_openapi(text)

    # Format check
    assert ir.source_format == "openapi"

    # Entities: at least User
    assert len(ir.entities) >= 1
    entity_names = [e.name for e in ir.entities]
    assert "User" in entity_names

    # Operations: at least listUsers
    assert len(ir.operations) >= 1
    op_names = [o.name for o in ir.operations]
    assert "listUsers" in op_names

    # No warnings on a clean spec
    assert len(ir.warnings) == 0


# ---------------------------------------------------------------------------
# Test 2: OpenAPI entities ingested and searchable via hybrid search (KG-E2E-01)
# ---------------------------------------------------------------------------


async def test_openapi_entities_ingested_and_searchable(db_conn):
    """Parse a rich OpenAPI spec, insert entities with fake embeddings,
    and verify hybrid_search returns ranked results with cosine + BM25 + RRF."""

    ir = parse_openapi(RICH_OPENAPI_SPEC)
    assert len(ir.entities) >= 5, f"Expected >= 5 entities, got {len(ir.entities)}"

    inserted_ids: list[str] = []

    try:
        # Insert each entity with a fake embedding
        for ent in ir.entities:
            emb = _fake_embedding(ent.name)
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            eid = await db_conn.fetchval(
                """
                INSERT INTO entity (id, name, type, summary, embedding, created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2, $3, $4::vector, NOW(), NOW())
                RETURNING id::text
                """,
                ent.name,
                ent.type,
                ent.description,
                emb_str,
            )
            inserted_ids.append(eid)

        # Search for "User" with its deterministic fake embedding
        user_emb = _fake_embedding("User")
        results = await hybrid_search("User", user_emb, db_conn, limit=10)

        # Basic assertions
        assert len(results) > 0, "hybrid_search returned no results"
        first = results[0]
        assert "User" in first.name, f"Expected first result to contain 'User', got '{first.name}'"

        # RRF score must be positive
        assert first.rrf_score > 0, f"rrf_score should be > 0, got {first.rrf_score}"

        # Cosine score must be positive (we inserted embeddings)
        assert first.cosine_score > 0, f"cosine_score should be > 0, got {first.cosine_score}"

        # BM25 score: the BM25 index on entity.name should match "User"
        has_bm25 = any(r.bm25_score > 0 for r in results)
        assert has_bm25, "Expected at least one result with bm25_score > 0"

    finally:
        # Cleanup: delete all inserted entities
        if inserted_ids:
            await db_conn.execute(
                "DELETE FROM entity WHERE id = ANY($1::uuid[])", inserted_ids
            )


# ---------------------------------------------------------------------------
# Test 3: Fact invalidation + AS OF temporal queries (KG-E2E-02)
# ---------------------------------------------------------------------------


async def test_fact_invalidation_and_as_of(db_conn):
    """Create two facts between the same entities; the second contradicts the first
    (same embedding -> cosine=1.0 > INVALIDATION_THRESHOLD=0.90).

    Verify:
      - Old fact has t_invalid set (preserved, not deleted).
      - New fact has t_invalid IS NULL.
      - AS OF query before contradiction returns only old fact.
      - AS OF query after contradiction returns only new fact.
    """

    entity_a_id: str | None = None
    entity_b_id: str | None = None
    episode_id: str | None = None
    fact_1_id: str | None = None
    fact_2_id: str | None = None

    try:
        # --- Setup: create two entities and an episode ---
        emb_a = _fake_embedding("EntityA_test_invalidation")
        emb_b = _fake_embedding("EntityB_test_invalidation")
        emb_a_str = "[" + ",".join(str(v) for v in emb_a) + "]"
        emb_b_str = "[" + ",".join(str(v) for v in emb_b) + "]"

        entity_a_id = await db_conn.fetchval(
            """
            INSERT INTO entity (id, name, type, summary, embedding, created_at, updated_at)
            VALUES (gen_random_uuid(), 'TestEntityA', 'model', 'Test entity A', $1::vector, NOW(), NOW())
            RETURNING id::text
            """,
            emb_a_str,
        )

        entity_b_id = await db_conn.fetchval(
            """
            INSERT INTO entity (id, name, type, summary, embedding, created_at, updated_at)
            VALUES (gen_random_uuid(), 'TestEntityB', 'model', 'Test entity B', $1::vector, NOW(), NOW())
            RETURNING id::text
            """,
            emb_b_str,
        )

        episode_id = await db_conn.fetchval(
            """
            INSERT INTO episode (id, source, raw_data, reference_ts, schema_version)
            VALUES (gen_random_uuid(), 'e2e-test', '{}'::jsonb, NOW(), '0001')
            RETURNING id::text
            """,
        )

        # --- Fact 1: "owns" relationship ---
        fact_embedding = _fake_embedding("owns_relationship")
        t1 = datetime.now(timezone.utc)

        fact_1_id = await create_fact_with_invalidation(
            conn=db_conn,
            source_entity=entity_a_id,
            target_entity=entity_b_id,
            predicate="owns",
            embedding=fact_embedding,
            t_valid=t1,
            source_episodes=[episode_id],
        )

        # Small delay to ensure timestamp differentiation
        await asyncio.sleep(0.05)
        t_between = datetime.now(timezone.utc)
        await asyncio.sleep(0.05)

        # --- Fact 2: contradicting fact with SAME embedding (cosine=1.0) ---
        # Using the identical embedding guarantees cosine similarity = 1.0,
        # which exceeds INVALIDATION_THRESHOLD (0.90).
        t2_before = datetime.now(timezone.utc)

        fact_2_id = await create_fact_with_invalidation(
            conn=db_conn,
            source_entity=entity_a_id,
            target_entity=entity_b_id,
            predicate="leases",
            embedding=fact_embedding,  # Same embedding -> cosine = 1.0
            t_valid=t2_before,
            source_episodes=[episode_id],
        )

        await asyncio.sleep(0.05)
        t2_after = datetime.now(timezone.utc)

        # --- Assertion: old fact has t_invalid set ---
        row1 = await db_conn.fetchrow(
            "SELECT t_invalid FROM fact WHERE id = $1::uuid", fact_1_id
        )
        assert row1 is not None, f"Fact 1 {fact_1_id} not found in DB"
        assert row1["t_invalid"] is not None, (
            f"Fact 1 t_invalid should be set after contradiction, got NULL"
        )

        # --- Assertion: new fact has t_invalid IS NULL ---
        row2 = await db_conn.fetchrow(
            "SELECT t_invalid FROM fact WHERE id = $1::uuid", fact_2_id
        )
        assert row2 is not None, f"Fact 2 {fact_2_id} not found in DB"
        assert row2["t_invalid"] is None, (
            f"Fact 2 t_invalid should be NULL (current fact), got {row2['t_invalid']}"
        )

        # --- AS OF query BEFORE contradiction (at t_between) ---
        # At t_between: fact_1 already created, fact_2 not yet created.
        # fact_1 was NOT yet invalidated at t_between (invalidation happens when fact_2 is created).
        # But t_invalid is set to a timestamp close to fact_2 creation, so we check:
        #   t_created <= t_between AND (t_invalid IS NULL OR t_invalid > t_between)
        rows_before = await db_conn.fetch(
            """
            SELECT id::text FROM fact
            WHERE source_entity = $1::uuid AND target_entity = $2::uuid
              AND t_created <= $3
              AND (t_invalid IS NULL OR t_invalid > $3)
            """,
            entity_a_id,
            entity_b_id,
            t_between,
        )
        ids_before = {r["id"] for r in rows_before}
        assert fact_1_id in ids_before, (
            f"AS OF before contradiction should include fact_1 ({fact_1_id}), got {ids_before}"
        )
        assert fact_2_id not in ids_before, (
            f"AS OF before contradiction should NOT include fact_2 ({fact_2_id}), got {ids_before}"
        )

        # --- AS OF query AFTER contradiction (at t2_after) ---
        rows_after = await db_conn.fetch(
            """
            SELECT id::text FROM fact
            WHERE source_entity = $1::uuid AND target_entity = $2::uuid
              AND t_created <= $3
              AND (t_invalid IS NULL OR t_invalid > $3)
            """,
            entity_a_id,
            entity_b_id,
            t2_after,
        )
        ids_after = {r["id"] for r in rows_after}
        assert fact_2_id in ids_after, (
            f"AS OF after contradiction should include fact_2 ({fact_2_id}), got {ids_after}"
        )
        assert fact_1_id not in ids_after, (
            f"AS OF after contradiction should NOT include fact_1 ({fact_1_id}), got {ids_after}"
        )

    finally:
        # Cleanup: delete facts first (FK to entity), then entities, then episode
        if fact_2_id:
            await db_conn.execute("DELETE FROM fact WHERE id = $1::uuid", fact_2_id)
        if fact_1_id:
            await db_conn.execute("DELETE FROM fact WHERE id = $1::uuid", fact_1_id)
        if entity_a_id:
            await db_conn.execute("DELETE FROM entity WHERE id = $1::uuid", entity_a_id)
        if entity_b_id:
            await db_conn.execute("DELETE FROM entity WHERE id = $1::uuid", entity_b_id)
        if episode_id:
            await db_conn.execute("DELETE FROM episode WHERE id = $1::uuid", episode_id)
