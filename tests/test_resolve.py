"""
tests/test_resolve.py — Tests for entity resolution (KG-02, D-14).

Verifies:
- resolve_entity returns existing entity_id on exact name match
- resolve_entity matches case-insensitively (LOWER() comparison)
- resolve_entity returns None when no match found
- resolve_entity returns entity_id when cosine similarity >= RESOLUTION_THRESHOLD
"""

import asyncpg
import pytest

from knowledge.resolve import resolve_entity, RESOLUTION_THRESHOLD


@pytest.mark.asyncio
async def test_resolve_exact_name_match(conn: asyncpg.Connection):
    """resolve_entity returns existing entity_id on exact name match."""
    entity_id = await conn.fetchval(
        "INSERT INTO entity (id, name, type, summary, created_at, updated_at) "
        "VALUES (gen_random_uuid(), 'TestEntity', 'concept', 'A test entity', NOW(), NOW()) "
        "RETURNING id::text"
    )

    result = await resolve_entity("TestEntity", [], conn)

    assert str(result) == str(entity_id)


@pytest.mark.asyncio
async def test_resolve_case_insensitive(conn: asyncpg.Connection):
    """resolve_entity matches case-insensitively (LOWER() comparison)."""
    entity_id = await conn.fetchval(
        "INSERT INTO entity (id, name, type, summary, created_at, updated_at) "
        "VALUES (gen_random_uuid(), 'CamelCaseEntity', 'concept', 'Testing case', NOW(), NOW()) "
        "RETURNING id::text"
    )

    result = await resolve_entity("camelcaseentity", [], conn)

    assert str(result) == str(entity_id)


@pytest.mark.asyncio
async def test_resolve_none_when_no_match(conn: asyncpg.Connection):
    """resolve_entity returns None when no name match and embedding is empty."""
    result = await resolve_entity("CompletelyUnknownEntityXYZ12345", [], conn)

    assert result is None


@pytest.mark.asyncio
async def test_resolve_embedding_similarity(conn: asyncpg.Connection):
    """resolve_entity returns entity_id when cosine similarity >= RESOLUTION_THRESHOLD."""
    # Use a unique embedding to avoid collisions with other tests' entities
    import random
    rng = random.Random(42424242)
    embedding = [rng.uniform(-1, 1) for _ in range(1024)]
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

    entity_id = await conn.fetchval(
        f"INSERT INTO entity (id, name, type, summary, embedding, created_at, updated_at) "
        f"VALUES (gen_random_uuid(), 'EmbeddingTestEntity', 'concept', 'Embedding test', "
        f"'{embedding_str}'::vector, NOW(), NOW()) "
        f"RETURNING id::text"
    )

    # Query with the same embedding — cosine similarity should be 1.0 (identical)
    result = await resolve_entity("NoMatchByName_EmbedTestXYZ", embedding, conn)

    assert str(result) == str(entity_id)


@pytest.mark.asyncio
async def test_resolve_threshold_constant():
    """RESOLUTION_THRESHOLD is 0.88 as specified (KG-02, D-14)."""
    assert RESOLUTION_THRESHOLD == 0.88
