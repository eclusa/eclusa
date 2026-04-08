"""tests/test_community.py — Label propagation community detection (KG-05).

Tests verify:
- Empty fact table creates no community rows (graceful empty case)
- 3 entities connected in a chain (A->B, B->C) cluster into 1 community
- 2 disconnected pairs (A->B, C->D) create 2 communities
- Re-running label propagation replaces communities (no doubling)
"""

import pytest

from knowledge.community import run_label_propagation


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


async def _insert_fact(conn, source: str, target: str) -> str:
    """Helper to insert a minimal fact (no embedding) between two entities."""
    return await conn.fetchval(
        """
        INSERT INTO fact (
            id, source_entity, target_entity, predicate,
            t_valid, t_created, source_episodes, schema_version
        ) VALUES (
            gen_random_uuid(), $1::uuid, $2::uuid, 'test_relation',
            NOW(), NOW(), '{}'::uuid[], '0001'
        ) RETURNING id::text
        """,
        source,
        target,
    )


@pytest.mark.asyncio
async def test_label_propagation_empty(conn):
    """With no facts, run_label_propagation completes without error and inserts no communities.

    Uses a transaction that is rolled back to isolate from shared test DB state.
    The fact table is truncated within this transaction, run is verified, then rolled back.
    """
    # Use a savepoint to test with an empty fact table in isolation
    async with conn.transaction():
        # Snapshot state before test
        await conn.execute(
            "DELETE FROM fact WHERE predicate = 'test_relation_empty_test'"
        )
        await conn.execute("DELETE FROM community")
        await conn.execute("SAVEPOINT before_empty_test")
        await conn.execute("DELETE FROM fact")

        await run_label_propagation(conn)

        count = await conn.fetchval("SELECT COUNT(*) FROM community")

        # Rollback to restore the fact data for other tests
        await conn.execute("ROLLBACK TO SAVEPOINT before_empty_test")

    assert count == 0, "No communities expected when fact table is empty"


@pytest.mark.asyncio
async def test_label_propagation_clusters(conn):
    """3 entities connected in a chain (A->B, B->C) must form 1 community with all 3 entity_ids."""
    await conn.execute("DELETE FROM community")

    entity_a = await _insert_entity(conn, "comm_entity_A1")
    entity_b = await _insert_entity(conn, "comm_entity_B1")
    entity_c = await _insert_entity(conn, "comm_entity_C1")

    await _insert_fact(conn, entity_a, entity_b)
    await _insert_fact(conn, entity_b, entity_c)

    await run_label_propagation(conn)

    # Fetch all communities to find the one containing our entities
    rows = await conn.fetch("SELECT entity_ids FROM community")
    all_entity_ids = set()
    for row in rows:
        all_entity_ids.update(str(uid) for uid in row["entity_ids"])

    assert entity_a in all_entity_ids, "Entity A must be in a community"
    assert entity_b in all_entity_ids, "Entity B must be in a community"
    assert entity_c in all_entity_ids, "Entity C must be in a community"

    # All three must be in the same community
    for row in rows:
        ids = {str(uid) for uid in row["entity_ids"]}
        if entity_a in ids:
            assert entity_b in ids, "B should be in same community as A"
            assert entity_c in ids, "C should be in same community as A"
            break


@pytest.mark.asyncio
async def test_label_propagation_two_components(conn):
    """2 disconnected pairs (A->B, C->D) must create 2 separate community rows."""
    await conn.execute("DELETE FROM community")

    entity_a = await _insert_entity(conn, "comm_entity_A2")
    entity_b = await _insert_entity(conn, "comm_entity_B2")
    entity_c = await _insert_entity(conn, "comm_entity_C2")
    entity_d = await _insert_entity(conn, "comm_entity_D2")

    await _insert_fact(conn, entity_a, entity_b)  # component 1
    await _insert_fact(conn, entity_c, entity_d)  # component 2

    await run_label_propagation(conn)

    # Each component should be in a different community
    rows = await conn.fetch("SELECT entity_ids FROM community")
    component_sets = [{str(uid) for uid in row["entity_ids"]} for row in rows]

    # Find the communities containing our entities
    comp1 = next((s for s in component_sets if entity_a in s), None)
    comp2 = next((s for s in component_sets if entity_c in s), None)

    assert comp1 is not None, "Component 1 (A, B) must be in a community"
    assert comp2 is not None, "Component 2 (C, D) must be in a community"
    assert comp1 != comp2, "The two components must be in separate communities"
    assert entity_b in comp1, "B must be with A"
    assert entity_d in comp2, "D must be with C"


@pytest.mark.asyncio
async def test_label_propagation_replaces(conn):
    """Running label propagation twice must replace communities, not double them."""
    await conn.execute("DELETE FROM community")

    entity_a = await _insert_entity(conn, "comm_entity_A3")
    entity_b = await _insert_entity(conn, "comm_entity_B3")
    await _insert_fact(conn, entity_a, entity_b)

    # Run twice
    await run_label_propagation(conn)
    await run_label_propagation(conn)

    # Count communities containing our test entities
    rows = await conn.fetch("SELECT entity_ids FROM community")
    matching = [
        row for row in rows if any(str(uid) == entity_a for uid in row["entity_ids"])
    ]

    assert len(matching) == 1, (
        "After two runs, entities must appear in exactly one community (no doubling)"
    )
