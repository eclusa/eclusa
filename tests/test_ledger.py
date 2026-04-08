"""Test ledger append-only enforcement — REVOKE + trigger defense-in-depth."""

import uuid
import pytest
import asyncpg
from ulid import ULID


def new_uuid() -> uuid.UUID:
    return ULID().to_uuid()


@pytest.mark.asyncio
async def test_ledger_entry_is_append_only(conn):
    """UPDATE and DELETE on ledger_entry must both raise RaiseError with 'append-only'.

    Verifies D-07, D-08: defense-in-depth enforcement via trigger.
    """
    actor_id = await conn.fetchval(
        "INSERT INTO actor (id, type, identity) VALUES (gen_random_uuid(), 'system', 'append-only-test') RETURNING id"
    )
    row_id = await conn.fetchval(
        "INSERT INTO ledger_entry (id, actor_id, type) VALUES (gen_random_uuid(), $1, 'schema_migration') RETURNING id",
        actor_id,
    )

    # UPDATE must be blocked
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await conn.execute(
            "UPDATE ledger_entry SET content = '{\"x\":1}' WHERE id = $1", row_id
        )

    # DELETE must be blocked
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await conn.execute("DELETE FROM ledger_entry WHERE id = $1", row_id)


@pytest.mark.asyncio
async def test_schema_version_present(conn):
    """INSERT into ledger_entry WITHOUT specifying schema_version must default to '0001'.

    Verifies D-05, SCHEMA-03: schema_version must be present from first migration.
    """
    actor_id = await conn.fetchval(
        """
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', 'schema-ver-test')
        RETURNING id
        """
    )
    schema_ver = await conn.fetchval(
        """
        INSERT INTO ledger_entry (id, actor_id, type)
        VALUES (gen_random_uuid(), $1, 'schema_migration')
        RETURNING schema_version
        """,
        actor_id,
    )
    assert schema_ver == "0001", f"Expected schema_version='0001', got {schema_ver!r}"


# Alias for backwards compatibility
test_schema_version_default_on_insert = test_schema_version_present


@pytest.mark.asyncio
async def test_ledger_entry_can_insert(conn):
    """Sanity: a valid ledger_entry row can be inserted and queried back."""
    actor_id = await conn.fetchval(
        "INSERT INTO actor (id, type, identity) VALUES (gen_random_uuid(), 'system', 'insert-test') RETURNING id"
    )
    entry_id = await conn.fetchval(
        "INSERT INTO ledger_entry (id, actor_id, type) VALUES (gen_random_uuid(), $1, 'schema_migration') RETURNING id",
        actor_id,
    )
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM ledger_entry WHERE id = $1", entry_id
    )
    assert count == 1, f"Expected 1 ledger_entry row, got {count}"


@pytest.mark.asyncio
async def test_ledger_trigger_blocks_update(conn):
    """UPDATE on ledger_entry must raise an exception containing 'append-only'."""
    actor_id = await conn.fetchval(
        "INSERT INTO actor (id, type, identity) VALUES (gen_random_uuid(), 'system', 'trigger-test') RETURNING id"
    )
    entry_id = await conn.fetchval(
        "INSERT INTO ledger_entry (id, actor_id, type) VALUES (gen_random_uuid(), $1, 'schema_migration') RETURNING id",
        actor_id,
    )
    with pytest.raises(asyncpg.exceptions.RaiseError) as exc_info:
        await conn.execute(
            "UPDATE ledger_entry SET content = '{}' WHERE id = $1", entry_id
        )
    assert "append-only" in str(exc_info.value).lower(), (
        f"Expected 'append-only' in exception message, got: {exc_info.value}"
    )


@pytest.mark.asyncio
async def test_ledger_trigger_blocks_delete(conn):
    """DELETE on ledger_entry must raise an exception containing 'append-only'."""
    actor_id = await conn.fetchval(
        "INSERT INTO actor (id, type, identity) VALUES (gen_random_uuid(), 'system', 'delete-test') RETURNING id"
    )
    entry_id = await conn.fetchval(
        "INSERT INTO ledger_entry (id, actor_id, type) VALUES (gen_random_uuid(), $1, 'schema_migration') RETURNING id",
        actor_id,
    )
    with pytest.raises(asyncpg.exceptions.RaiseError) as exc_info:
        await conn.execute("DELETE FROM ledger_entry WHERE id = $1", entry_id)
    assert "append-only" in str(exc_info.value).lower(), (
        f"Expected 'append-only' in exception message, got: {exc_info.value}"
    )


@pytest.mark.asyncio
async def test_trigger_exists(conn):
    """enforce_ledger_immutability trigger must exist on ledger_entry."""
    result = await conn.fetchrow(
        """
        SELECT trigger_name FROM information_schema.triggers
        WHERE event_object_table = 'ledger_entry'
          AND trigger_name = 'enforce_ledger_immutability'
        """
    )
    assert result is not None, (
        "enforce_ledger_immutability trigger not found on ledger_entry"
    )


@pytest.mark.asyncio
async def test_immutability_function_exists(conn):
    """ledger_entry_immutability_guard function must exist."""
    result = await conn.fetchrow(
        """
        SELECT routine_name FROM information_schema.routines
        WHERE routine_name = 'ledger_entry_immutability_guard'
        """
    )
    assert result is not None, "ledger_entry_immutability_guard function not found"
