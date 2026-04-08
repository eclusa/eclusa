"""Tests for narrowing dispatch and gate surfacing (EXEC-05, EXEC-06, EXEC-07).

Wave 1 implementation — all tests active.
"""

import pytest
from tests.helpers.topology import seed_linear_cascade

from executor.dispatch import dispatch_narrowing, dispatch_stage, resolve_gate

pytestmark = pytest.mark.asyncio


async def test_dispatch_narrowing_stub_resolves(conn):
    """dispatch_narrowing marks the stage resolved and writes a stage_state_changed ledger entry."""
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_a_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]

    # Manually set stage A to active (simulating claim)
    await conn.execute(
        "UPDATE stage SET state = 'active' WHERE id = $1::uuid", stage_a_id
    )

    stage_row = {
        "id": stage_a_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": None,
    }

    await dispatch_narrowing(conn, stage_row, actor_id)

    # Stage should now be resolved
    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", stage_a_id)
    assert row["state"] == "resolved"

    # A stage_state_changed ledger entry must exist for this stage
    ledger_row = await conn.fetchrow(
        "SELECT type, schema_version FROM ledger_entry WHERE stage_id = $1::uuid AND type = 'stage_state_changed'",
        stage_a_id,
    )
    assert ledger_row is not None
    assert ledger_row["type"] == "stage_state_changed"
    assert ledger_row["schema_version"] == "0002"


async def test_dispatch_gate_auto_resolvable(conn):
    """Auto-resolvable gate resolves immediately via dispatch_stage with gate_auto_resolved ledger entry."""
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    cascade_id = topo["cascade_id"]

    # Insert a gate stage with auto_resolve=true
    gate_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'active', '{}', '{"auto_resolve": "true"}'::jsonb)
        RETURNING id
    """,
        cascade_id,
    )
    gate_id = str(gate_row["id"])

    stage_row = {
        "id": gate_id,
        "type": "gate",
        "cascade_id": cascade_id,
        "input": {"auto_resolve": "true"},
    }

    await dispatch_stage(conn, stage_row, actor_id)

    # Gate should be resolved
    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", gate_id)
    assert row["state"] == "resolved"

    # A gate_auto_resolved ledger entry must exist
    ledger_row = await conn.fetchrow(
        "SELECT type, schema_version FROM ledger_entry WHERE stage_id = $1::uuid AND type = 'gate_auto_resolved'",
        gate_id,
    )
    assert ledger_row is not None
    assert ledger_row["schema_version"] == "0002"


async def test_dispatch_gate_surfaces_when_not_auto_resolvable(conn):
    """Non-auto-resolvable gate surfaces to 'blocked' with a gate_surfaced ledger entry."""
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    cascade_id = topo["cascade_id"]

    # Insert a gate stage with no auto_resolve
    gate_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'active', '{}', '{}'::jsonb)
        RETURNING id
    """,
        cascade_id,
    )
    gate_id = str(gate_row["id"])

    stage_row = {
        "id": gate_id,
        "type": "gate",
        "cascade_id": cascade_id,
        "input": {},
    }

    await dispatch_stage(conn, stage_row, actor_id)

    # Gate should be blocked
    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", gate_id)
    assert row["state"] == "blocked"

    # A gate_surfaced ledger entry must exist
    ledger_row = await conn.fetchrow(
        "SELECT type, schema_version FROM ledger_entry WHERE stage_id = $1::uuid AND type = 'gate_surfaced'",
        gate_id,
    )
    assert ledger_row is not None
    assert ledger_row["schema_version"] == "0002"


async def test_gate_resolution_fires_notify(conn):
    """resolve_gate marks a gate stage resolved and writes a gate_resolved ledger entry."""
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    cascade_id = topo["cascade_id"]

    # Insert a blocked gate stage
    gate_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'blocked', '{}', '{}'::jsonb)
        RETURNING id
    """,
        cascade_id,
    )
    gate_id = str(gate_row["id"])

    await resolve_gate(conn, gate_id, actor_id)

    # Gate should be resolved
    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", gate_id)
    assert row["state"] == "resolved"

    # A gate_resolved ledger entry must exist
    ledger_row = await conn.fetchrow(
        "SELECT type, schema_version FROM ledger_entry WHERE stage_id = $1::uuid AND type = 'gate_resolved'",
        gate_id,
    )
    assert ledger_row is not None
    assert ledger_row["schema_version"] == "0002"


async def test_stage_state_transition_writes_ledger_entry(conn):
    """Every dispatch path writes exactly one ledger_entry per state transition with schema_version='0002'."""
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    cascade_id = topo["cascade_id"]
    stage_id = topo["stage_ids"][1]  # Use stage B

    # Set to active
    await conn.execute(
        "UPDATE stage SET state = 'active' WHERE id = $1::uuid", stage_id
    )

    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": None,
    }

    # Count ledger entries before
    count_before = await conn.fetchval(
        "SELECT COUNT(*) FROM ledger_entry WHERE stage_id = $1::uuid", stage_id
    )

    await dispatch_narrowing(conn, stage_row, actor_id)

    # Count ledger entries after
    count_after = await conn.fetchval(
        "SELECT COUNT(*) FROM ledger_entry WHERE stage_id = $1::uuid", stage_id
    )

    # Exactly one new ledger entry must have been written
    assert count_after - count_before == 1

    # Verify it has the correct schema_version
    ledger_row = await conn.fetchrow(
        "SELECT schema_version FROM ledger_entry WHERE stage_id = $1::uuid ORDER BY timestamp DESC LIMIT 1",
        stage_id,
    )
    assert ledger_row["schema_version"] == "0002"
