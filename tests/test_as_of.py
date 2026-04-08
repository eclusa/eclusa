"""Test AS OF TIMESTAMP ledger query — point-in-time historical state retrieval."""

import asyncio
import pathlib
import pytest

QUERIES = pathlib.Path("db/queries")


@pytest.mark.asyncio
async def test_as_of_timestamp_query(conn):
    """as_of.sql returns the most recent ledger entry for an entity at a given timestamp.

    Seeds two ledger entries for the same cascade_id. Queries between them.
    Verifies the earlier entry is returned and the later one is excluded.
    """
    # Seed actor
    actor_id = await conn.fetchval(
        "INSERT INTO actor (id, type, identity) VALUES (gen_random_uuid(), 'system', 'as-of-test') RETURNING id"
    )

    # Seed intent
    intent_id = await conn.fetchval(
        "INSERT INTO intent (id, source, raw, created_by) VALUES (gen_random_uuid(), 'api', 'as-of test', $1) RETURNING id",
        actor_id,
    )

    # Seed cascade
    cascade_id = await conn.fetchval(
        "INSERT INTO cascade (id, intent_id, shape, state) VALUES (gen_random_uuid(), $1, '{}'::jsonb, 'active') RETURNING id",
        intent_id,
    )

    # Insert ledger_entry #1 — captures actual DB timestamp after insert
    ledger_entry_1_id = await conn.fetchval(
        """
        INSERT INTO ledger_entry (id, actor_id, cascade_id, type)
        VALUES (gen_random_uuid(), $1, $2, 'cascade_created')
        RETURNING id
        """,
        actor_id,
        cascade_id,
    )

    # Capture T_between — after entry 1, before entry 2
    t_between = await conn.fetchval("SELECT NOW()")

    # Small delay to ensure T_between is strictly between the two inserts
    await asyncio.sleep(0.01)

    # Insert ledger_entry #2
    ledger_entry_2_id = await conn.fetchval(
        """
        INSERT INTO ledger_entry (id, actor_id, cascade_id, type)
        VALUES (gen_random_uuid(), $1, $2, 'cascade_state_changed')
        RETURNING id
        """,
        actor_id,
        cascade_id,
    )

    # Execute AS OF query with cascade_id and T_between
    as_of_sql = (QUERIES / "as_of.sql").read_text()
    result = await conn.fetchrow(as_of_sql, cascade_id, t_between)

    assert result is not None, (
        "as_of.sql returned no rows — expected ledger_entry_1 to be returned"
    )
    assert result["id"] == ledger_entry_1_id, (
        f"Expected earlier entry {ledger_entry_1_id}, got {result['id']}"
    )
    assert result["id"] != ledger_entry_2_id, (
        f"Later entry {ledger_entry_2_id} should not appear at T_between"
    )
