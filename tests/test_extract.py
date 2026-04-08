"""
tests/test_extract.py — Tests for entity extraction + persistence (KG-02, D-13).

Verifies:
- extract_entities_from_episode returns list[ExtractedEntity]
- Uses pydantic-ai TestModel in tests (no real API key needed)
- Persists new entities to entity table (KG-02 durable persistence)
- Deduplicates existing entities (resolve_entity returns existing id — no INSERT)
"""

import asyncpg
import pytest
from pydantic_ai.models.test import TestModel

from knowledge.extract import (
    ExtractedEntity,
    EntityList,
    extract_entities_from_episode,
    _agent,
)


@pytest.mark.asyncio
async def test_extract_entities_returns_list(conn: asyncpg.Connection):
    """extract_entities_from_episode returns list[ExtractedEntity] using TestModel."""
    with _agent.override(model=TestModel()):
        result = await extract_entities_from_episode(
            "Nathan leads the Eclusa project", conn
        )

    assert isinstance(result, list)
    assert all(isinstance(e, ExtractedEntity) for e in result)


@pytest.mark.asyncio
async def test_extract_persists_new_entities(conn: asyncpg.Connection):
    """New entities extracted by LLM are persisted to entity table (KG-02)."""
    # Use TestModel with custom output to control exactly what entity is "extracted"
    custom_output = EntityList(
        entities=[
            ExtractedEntity(
                name="UniqueEntityForPersistTest",
                type="concept",
                summary="Test persistence",
            )
        ]
    )

    with _agent.override(
        model=TestModel(custom_output_text=None, custom_output_args=custom_output)
    ):
        result = await extract_entities_from_episode("some episode text", conn)

    assert len(result) > 0

    # Verify the entity was persisted to DB
    row = await conn.fetchrow(
        "SELECT id, name FROM entity WHERE name = 'UniqueEntityForPersistTest'"
    )
    assert row is not None, "Entity should have been persisted to entity table"


@pytest.mark.asyncio
async def test_extract_deduplicates_existing_entities(conn: asyncpg.Connection):
    """If entity already exists, no duplicate INSERT (resolve_entity returns existing id)."""
    # Pre-insert an entity
    existing_name = "ExistingEntityDedupeTest"
    await conn.execute(
        "INSERT INTO entity (id, name, type, summary, created_at, updated_at) "
        "VALUES (gen_random_uuid(), $1, 'concept', 'Pre-existing', NOW(), NOW())",
        existing_name,
    )

    # Count entities before extraction
    count_before = await conn.fetchval(
        "SELECT COUNT(*) FROM entity WHERE name = $1", existing_name
    )
    assert count_before == 1

    # Mock LLM to return the same existing entity
    custom_output = EntityList(
        entities=[
            ExtractedEntity(name=existing_name, type="concept", summary="Pre-existing")
        ]
    )

    with _agent.override(
        model=TestModel(custom_output_text=None, custom_output_args=custom_output)
    ):
        await extract_entities_from_episode(
            "episode text mentioning existing entity", conn
        )

    # Count should NOT have increased
    count_after = await conn.fetchval(
        "SELECT COUNT(*) FROM entity WHERE name = $1", existing_name
    )
    assert count_after == 1, f"Entity count should stay 1, got {count_after}"
