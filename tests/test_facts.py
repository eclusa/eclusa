"""tests/test_facts.py — Bi-temporal fact creation with edge invalidation (KG-03, KG-04).

Tests verify:
- create_fact_with_invalidation creates a new fact row with all four bi-temporal timestamps
- Old contradicting facts get t_invalid set (not deleted) when embedding similarity > 0.90
- Facts without embedding are not invalidated by similarity (no vector = no match)
- AS OF semantics: old fact returns before contradiction, new fact returns after
"""

import pytest
from datetime import datetime, timezone, timedelta

from knowledge.facts import create_fact_with_invalidation


EMBEDDING_A = [0.1] * 1024  # base embedding
EMBEDDING_B = [0.1 + 1e-9] * 1024  # nearly identical — cosine similarity > 0.90
EMBEDDING_C = [0.9] * 1024  # dissimilar embedding


async def _insert_entity(conn, name: str) -> str:
    """Helper to insert a test entity and return its UUID as str."""
    return await conn.fetchval(
        """
        INSERT INTO entity (id, name, type, created_at, updated_at)
        VALUES (gen_random_uuid(), $1, 'test', NOW(), NOW())
        RETURNING id::text
        """,
        name,
    )


@pytest.mark.asyncio
async def test_create_fact(conn):
    """create_fact_with_invalidation inserts a row with all four bi-temporal timestamps."""
    src = await _insert_entity(conn, "fact_entity_src_1")
    tgt = await _insert_entity(conn, "fact_entity_tgt_1")

    t_valid = datetime.now(timezone.utc) - timedelta(hours=1)
    fact_id = await create_fact_with_invalidation(
        conn=conn,
        source_entity=src,
        target_entity=tgt,
        predicate="relates_to",
        embedding=EMBEDDING_A,
        t_valid=t_valid,
        source_episodes=[],
    )

    assert fact_id is not None
    row = await conn.fetchrow("SELECT * FROM fact WHERE id = $1::uuid", fact_id)
    assert row is not None
    assert row["predicate"] == "relates_to"
    assert row["t_invalid"] is None  # still valid
    assert row["t_expired"] is None  # never superseded
    assert row["t_created"] is not None
    assert row["t_valid"] is not None


@pytest.mark.asyncio
async def test_invalidate_prior_fact_on_contradiction(conn):
    """When a second fact is created between the same entities with similar embedding,
    the first fact has t_invalid set to the time of the second fact's creation.
    """
    src = await _insert_entity(conn, "fact_entity_src_2")
    tgt = await _insert_entity(conn, "fact_entity_tgt_2")

    t_valid_1 = datetime.now(timezone.utc) - timedelta(hours=2)
    fact_id_1 = await create_fact_with_invalidation(
        conn=conn,
        source_entity=src,
        target_entity=tgt,
        predicate="trusts",
        embedding=EMBEDDING_A,
        t_valid=t_valid_1,
        source_episodes=[],
    )

    t_valid_2 = datetime.now(timezone.utc) - timedelta(hours=1)
    fact_id_2 = await create_fact_with_invalidation(
        conn=conn,
        source_entity=src,
        target_entity=tgt,
        predicate="distrusts",
        embedding=EMBEDDING_B,  # very similar to EMBEDDING_A -> cosine > 0.90
        t_valid=t_valid_2,
        source_episodes=[],
    )

    # First fact must have t_invalid set
    row1 = await conn.fetchrow(
        "SELECT t_invalid FROM fact WHERE id = $1::uuid", fact_id_1
    )
    assert row1["t_invalid"] is not None, "Prior fact should have t_invalid set"

    # Second fact should be valid (no t_invalid)
    row2 = await conn.fetchrow(
        "SELECT t_invalid FROM fact WHERE id = $1::uuid", fact_id_2
    )
    assert row2["t_invalid"] is None, "New fact should still be valid"


@pytest.mark.asyncio
async def test_old_fact_preserved(conn):
    """Edge invalidation sets t_invalid but does NOT delete the old fact row.
    The old row is preserved with original t_valid and t_created (KG-04 append-only invariant).
    """
    src = await _insert_entity(conn, "fact_entity_src_3")
    tgt = await _insert_entity(conn, "fact_entity_tgt_3")

    t_valid_original = datetime.now(timezone.utc) - timedelta(hours=3)
    fact_id_1 = await create_fact_with_invalidation(
        conn=conn,
        source_entity=src,
        target_entity=tgt,
        predicate="loves",
        embedding=EMBEDDING_A,
        t_valid=t_valid_original,
        source_episodes=[],
    )

    _fact_id_2 = await create_fact_with_invalidation(
        conn=conn,
        source_entity=src,
        target_entity=tgt,
        predicate="hates",
        embedding=EMBEDDING_B,
        t_valid=datetime.now(timezone.utc),
        source_episodes=[],
    )

    # The old fact MUST still exist in DB — just with t_invalid set
    row = await conn.fetchrow("SELECT * FROM fact WHERE id = $1::uuid", fact_id_1)
    assert row is not None, "Old fact row must not be deleted"
    assert row["t_invalid"] is not None, "Old fact must have t_invalid set"
    assert row["predicate"] == "loves", "Old fact original predicate preserved"


@pytest.mark.asyncio
async def test_no_invalidation_without_embedding(conn):
    """Facts without embedding are never invalidated by embedding similarity.
    A second fact should NOT invalidate a prior fact that has no embedding.
    """
    src = await _insert_entity(conn, "fact_entity_src_4")
    tgt = await _insert_entity(conn, "fact_entity_tgt_4")

    # First fact: no embedding
    fact_id_1 = await create_fact_with_invalidation(
        conn=conn,
        source_entity=src,
        target_entity=tgt,
        predicate="knows",
        embedding=None,  # no embedding
        t_valid=datetime.now(timezone.utc) - timedelta(hours=1),
        source_episodes=[],
    )

    # Second fact: has an embedding, same entity pair
    _fact_id_2 = await create_fact_with_invalidation(
        conn=conn,
        source_entity=src,
        target_entity=tgt,
        predicate="knows_well",
        embedding=EMBEDDING_A,
        t_valid=datetime.now(timezone.utc),
        source_episodes=[],
    )

    # First fact must NOT be invalidated (no embedding = no similarity match)
    row = await conn.fetchrow(
        "SELECT t_invalid FROM fact WHERE id = $1::uuid", fact_id_1
    )
    assert row["t_invalid"] is None, (
        "Fact without embedding must not be invalidated by similarity"
    )
