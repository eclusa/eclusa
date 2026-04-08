"""Tests for cascade migration proposals (CASC-04, CASC-05).

Wave 1 — all tests implemented.
"""

import json
import pytest
from tests.helpers.topology import seed_linear_cascade

pytestmark = pytest.mark.asyncio


async def _seed_system_actor(conn) -> str:
    """Seed a system actor for migration tests. Returns actor_id."""
    row = await conn.fetchrow(
        "SELECT id FROM actor WHERE identity = 'system-migration-test' LIMIT 1"
    )
    if row:
        return str(row["id"])
    row = await conn.fetchrow("""
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', 'system-migration-test')
        RETURNING id
    """)
    return str(row["id"])


async def _insert_proposal(
    conn,
    cascade_id: str,
    proposed_by: str,
    new_shape: dict,
    reason: str = "test migration",
) -> str:
    """Insert a cascade_migration_proposal and return its ID."""
    row = await conn.fetchrow(
        """
        INSERT INTO cascade_migration_proposal (id, cascade_id, proposed_by, new_shape, reason)
        VALUES (gen_random_uuid(), $1::uuid, $2::uuid, $3::jsonb, $4)
        RETURNING id
    """,
        cascade_id,
        proposed_by,
        json.dumps(new_shape),
        reason,
    )
    return str(row["id"])


async def test_migration_proposal_applied_updates_cascade_shape(conn):
    """apply_pending_migration updates cascade.shape and marks proposal as 'applied'."""
    from executor.cascade import apply_pending_migration

    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    system_actor_id = await _seed_system_actor(conn)

    new_shape = {"version": 2, "description": "updated shape"}
    proposal_id = await _insert_proposal(conn, cascade_id, actor_id, new_shape)

    result = await apply_pending_migration(conn, system_actor_id)
    assert result is True, (
        "apply_pending_migration should return True when migration applied"
    )

    # Verify cascade.shape was updated
    cascade_row = await conn.fetchrow(
        "SELECT shape FROM cascade WHERE id = $1::uuid",
        cascade_id,
    )
    raw_shape = cascade_row["shape"]
    actual_shape = json.loads(raw_shape) if isinstance(raw_shape, str) else raw_shape
    assert actual_shape == new_shape, (
        f"cascade.shape should be updated to new_shape, got {actual_shape}"
    )

    # Verify proposal.status is 'applied'
    proposal_row = await conn.fetchrow(
        "SELECT status, applied_at FROM cascade_migration_proposal WHERE id = $1::uuid",
        proposal_id,
    )
    assert proposal_row["status"] == "applied", (
        f"proposal.status should be 'applied', got '{proposal_row['status']}'"
    )
    assert proposal_row["applied_at"] is not None, "proposal.applied_at should be set"


async def test_migration_creates_ledger_entry_with_old_and_new_shape(conn):
    """After apply_pending_migration, a ledger_entry of type 'cascade_migration' has old and new shape."""
    from executor.cascade import apply_pending_migration

    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    system_actor_id = await _seed_system_actor(conn)

    new_shape = {"version": 3, "stages": ["A", "B", "C", "D"]}
    await _insert_proposal(conn, cascade_id, actor_id, new_shape, reason="add stage D")

    await apply_pending_migration(conn, system_actor_id)

    # Verify ledger entry was written
    ledger_row = await conn.fetchrow(
        """
        SELECT content FROM ledger_entry
        WHERE cascade_id = $1::uuid AND type = 'cascade_migration'
        ORDER BY timestamp DESC LIMIT 1
    """,
        cascade_id,
    )
    assert ledger_row is not None, (
        "A ledger_entry of type 'cascade_migration' should exist"
    )

    raw_content = ledger_row["content"]
    content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
    assert "old_shape" in content, (
        f"ledger content should contain old_shape, got {content}"
    )
    assert "new_shape" in content, (
        f"ledger content should contain new_shape, got {content}"
    )
    assert content["new_shape"] == new_shape, (
        f"ledger content.new_shape should match the applied shape, got {content['new_shape']}"
    )


async def test_migration_not_applied_while_stage_active(conn):
    """If any stage in the cascade is 'active', apply_pending_migration returns False (migration waits)."""
    from executor.cascade import apply_pending_migration

    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_a_id = topo["stage_ids"][0]
    system_actor_id = await _seed_system_actor(conn)

    # Mark stage A as active (simulates a running stage)
    await conn.execute(
        "UPDATE stage SET state = 'active' WHERE id = $1::uuid",
        stage_a_id,
    )

    new_shape = {"version": 2}
    proposal_id = await _insert_proposal(conn, cascade_id, actor_id, new_shape)

    result = await apply_pending_migration(conn, system_actor_id)
    assert result is False, (
        "apply_pending_migration should return False when active stages exist"
    )

    # Proposal should still be pending
    proposal_row = await conn.fetchrow(
        "SELECT status FROM cascade_migration_proposal WHERE id = $1::uuid",
        proposal_id,
    )
    assert proposal_row["status"] == "pending", (
        f"proposal.status should remain 'pending' while stage is active, got '{proposal_row['status']}'"
    )


async def test_migration_validates_depends_on_stage_ids_belong_to_cascade(conn):
    """Migration with new_shape containing a stage depends_on ID from a different cascade raises ValueError."""
    from executor.cascade import apply_pending_migration

    topo1 = await seed_linear_cascade(conn)
    cascade_id = topo1["cascade_id"]
    actor_id = topo1["actor_id"]
    system_actor_id = await _seed_system_actor(conn)

    # Clean slate: mark all previously-pending proposals as 'applied' so this
    # test's invalid proposal is the first one apply_pending_migration processes.
    await conn.execute(
        "UPDATE cascade_migration_proposal SET status = 'applied' WHERE status = 'pending'"
    )

    # Seed a second cascade to get a foreign stage ID
    topo2 = await seed_linear_cascade(conn)
    foreign_stage_id = topo2["stage_ids"][0]

    # new_shape references a stage from the second cascade (invalid)
    new_shape = {
        "stages": [{"id": topo1["stage_ids"][0], "depends_on": [foreign_stage_id]}]
    }
    await _insert_proposal(conn, cascade_id, actor_id, new_shape)

    with pytest.raises(ValueError):
        await apply_pending_migration(conn, system_actor_id)
