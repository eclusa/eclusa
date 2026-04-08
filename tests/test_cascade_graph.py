"""Tests for cascade graph traversal (CASC-01, CASC-02, CASC-03, CASC-06, CASC-07, D-19).

Wave 1 — all tests implemented.
"""

import json
import pytest
from tests.helpers.topology import (
    seed_linear_cascade,
    seed_branching_cascade,
    seed_nested_cascade,
)
from executor.cascade import (
    claim_ready_stages,
    check_cascade_completion,
    retry_stage,
    MaxRetriesExceeded,
)

pytestmark = pytest.mark.asyncio


async def test_ready_stages_skip_blocked_dependencies(conn):
    """Stage A has no deps (ready). B depends on A (blocked). C depends on B (blocked).
    After resolving A, only B is ready. After resolving B, only C is ready.
    """
    topo = await seed_linear_cascade(conn)
    stage_a_id, stage_b_id, stage_c_id = topo["stage_ids"]

    # Initially only stage A is ready (no dependencies)
    ready = await claim_ready_stages(conn, limit=10)
    ready_ids = [str(r["id"]) for r in ready]
    assert stage_a_id in ready_ids, f"Stage A should be ready, got {ready_ids}"
    assert stage_b_id not in ready_ids, "Stage B should NOT be ready (depends on A)"
    assert stage_c_id not in ready_ids, "Stage C should NOT be ready (depends on B)"

    # Resolve stage A → B becomes ready
    await conn.execute(
        "UPDATE stage SET state = 'resolved' WHERE id = $1::uuid",
        stage_a_id,
    )
    # Return B+C to pending (claim_ready_stages marked them active in the first call)
    # Actually, B and C were never active — only A was claimed. But A is now resolved.
    # Reset A's state change: A is now resolved, B should be pending still.
    ready2 = await claim_ready_stages(conn, limit=10)
    ready2_ids = [str(r["id"]) for r in ready2]
    assert stage_b_id in ready2_ids, (
        f"Stage B should be ready after A resolved, got {ready2_ids}"
    )
    assert stage_c_id not in ready2_ids, "Stage C should NOT be ready (depends on B)"

    # Resolve stage B → C becomes ready
    await conn.execute(
        "UPDATE stage SET state = 'resolved' WHERE id = $1::uuid",
        stage_b_id,
    )
    ready3 = await claim_ready_stages(conn, limit=10)
    ready3_ids = [str(r["id"]) for r in ready3]
    assert stage_c_id in ready3_ids, (
        f"Stage C should be ready after B resolved, got {ready3_ids}"
    )


async def test_branching_cascade_sibling_progresses_independently(conn):
    """root resolved → branch_a and branch_b both ready.
    Mark branch_a 'blocked'. branch_b should still be claimable.
    """
    topo = await seed_branching_cascade(conn)
    stage_ids = topo["stage_ids"]
    root_id = stage_ids["root"]
    branch_a_id = stage_ids["branch_a"]
    branch_b_id = stage_ids["branch_b"]

    # Resolve root
    await conn.execute(
        "UPDATE stage SET state = 'resolved' WHERE id = $1::uuid",
        root_id,
    )

    # Claim both branches — mark branch_a as blocked after claiming
    ready = await claim_ready_stages(conn, limit=10)
    ready_ids = [str(r["id"]) for r in ready]
    assert branch_a_id in ready_ids, "branch_a should be ready after root resolved"
    assert branch_b_id in ready_ids, "branch_b should be ready after root resolved"

    # Mark branch_a blocked (simulates a gate blocking it)
    await conn.execute(
        "UPDATE stage SET state = 'blocked' WHERE id = $1::uuid",
        branch_a_id,
    )
    # Reset branch_b to pending (it was claimed as active)
    await conn.execute(
        "UPDATE stage SET state = 'pending' WHERE id = $1::uuid",
        branch_b_id,
    )

    # branch_b should still be claimable; branch_a is blocked
    ready2 = await claim_ready_stages(conn, limit=10)
    ready2_ids = [str(r["id"]) for r in ready2]
    assert branch_b_id in ready2_ids, (
        "branch_b should be claimable while branch_a is blocked"
    )
    assert branch_a_id not in ready2_ids, "branch_a is blocked — should not be claimed"


async def test_nested_cascade_treated_as_regular_cascade(conn):
    """Child cascade stages appear in claim_ready_stages — executor sees them as regular stages."""
    topo = await seed_nested_cascade(conn)
    child_cascade_id = topo["child_cascade_id"]

    # Seed a pending stage in the child cascade
    child_stage_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}')
        RETURNING id
    """,
        child_cascade_id,
    )
    child_stage_id = str(child_stage_row["id"])

    # claim_ready_stages should find the child cascade stage
    ready = await claim_ready_stages(conn, limit=10)
    ready_ids = [str(r["id"]) for r in ready]
    assert child_stage_id in ready_ids, (
        f"Child cascade stage should be claimable by executor, got {ready_ids}"
    )


async def test_cascade_completes_when_all_stages_terminal(conn):
    """When all 3 stages are resolved, check_cascade_completion marks cascade 'completed'."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_a_id, stage_b_id, stage_c_id = topo["stage_ids"]

    # Resolve all stages
    for sid in [stage_a_id, stage_b_id, stage_c_id]:
        await conn.execute(
            "UPDATE stage SET state = 'resolved' WHERE id = $1::uuid",
            sid,
        )

    await check_cascade_completion(conn, cascade_id, actor_id)

    row = await conn.fetchrow(
        "SELECT state FROM cascade WHERE id = $1::uuid", cascade_id
    )
    assert str(row["state"]) == "completed", (
        f"Expected 'completed', got '{row['state']}'"
    )


async def test_cascade_fails_when_stage_fails_and_policy_is_fail_cascade(conn):
    """failure_policy='fail_cascade': failing stage A → cascade fails, B+C skipped."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_a_id, stage_b_id, stage_c_id = topo["stage_ids"]

    # Set failure_policy to fail_cascade (it's already the default, but be explicit)
    await conn.execute(
        "UPDATE cascade SET failure_policy = 'fail_cascade' WHERE id = $1::uuid",
        cascade_id,
    )

    # Mark stage A failed (simulates execution failure)
    await conn.execute(
        "UPDATE stage SET state = 'failed' WHERE id = $1::uuid",
        stage_a_id,
    )

    await check_cascade_completion(conn, cascade_id, actor_id)

    cascade_row = await conn.fetchrow(
        "SELECT state FROM cascade WHERE id = $1::uuid", cascade_id
    )
    assert str(cascade_row["state"]) == "failed", (
        f"Cascade should be 'failed' with fail_cascade policy, got '{cascade_row['state']}'"
    )

    # B and C should be skipped
    for sid in [stage_b_id, stage_c_id]:
        stage_row = await conn.fetchrow(
            "SELECT state FROM stage WHERE id = $1::uuid", sid
        )
        assert str(stage_row["state"]) == "skipped", (
            f"Stage {sid} should be 'skipped' when cascade fails, got '{stage_row['state']}'"
        )


async def test_cascade_skips_stage_when_policy_is_skip(conn):
    """failure_policy='skip': failing stage A → B+C skipped, cascade completes."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_a_id, stage_b_id, stage_c_id = topo["stage_ids"]

    # Set failure_policy to skip
    await conn.execute(
        "UPDATE cascade SET failure_policy = 'skip' WHERE id = $1::uuid",
        cascade_id,
    )

    # Mark stage A failed
    await conn.execute(
        "UPDATE stage SET state = 'failed' WHERE id = $1::uuid",
        stage_a_id,
    )

    await check_cascade_completion(conn, cascade_id, actor_id)

    # B and C should be skipped
    for sid in [stage_b_id, stage_c_id]:
        stage_row = await conn.fetchrow(
            "SELECT state FROM stage WHERE id = $1::uuid", sid
        )
        assert str(stage_row["state"]) == "skipped", (
            f"Stage {sid} should be 'skipped' with skip policy, got '{stage_row['state']}'"
        )

    # Cascade should complete (all terminal: 1 failed + 2 skipped)
    cascade_row = await conn.fetchrow(
        "SELECT state FROM cascade WHERE id = $1::uuid", cascade_id
    )
    assert str(cascade_row["state"]) == "completed", (
        f"Cascade should be 'completed' with skip policy, got '{cascade_row['state']}'"
    )


async def test_stage_retry_increments_count(conn):
    """retry_stage increments retry_count, resets state to 'pending', writes ledger entry."""
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_a_id = topo["stage_ids"][0]

    # Mark stage active (as if it were claimed and running)
    await conn.execute(
        "UPDATE stage SET state = 'active' WHERE id = $1::uuid",
        stage_a_id,
    )

    await retry_stage(conn, stage_a_id, actor_id)

    stage_row = await conn.fetchrow(
        "SELECT state, retry_count FROM stage WHERE id = $1::uuid",
        stage_a_id,
    )
    assert str(stage_row["state"]) == "pending", (
        f"Stage state should be 'pending' after retry, got '{stage_row['state']}'"
    )
    assert stage_row["retry_count"] == 1, (
        f"retry_count should be 1 after one retry, got {stage_row['retry_count']}"
    )

    # Verify ledger entry was written
    ledger_row = await conn.fetchrow(
        """
        SELECT content FROM ledger_entry
        WHERE stage_id = $1::uuid AND type = 'stage_state_changed'
        ORDER BY timestamp DESC LIMIT 1
    """,
        stage_a_id,
    )
    assert ledger_row is not None, (
        "A ledger_entry of type 'stage_state_changed' should exist"
    )
    raw_content = ledger_row["content"]
    # asyncpg may return JSONB as a string or dict depending on codec configuration
    content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
    assert "retry_count" in content, (
        f"ledger content should contain retry_count, got {content}"
    )
    assert content["retry_count"] == 1, (
        f"ledger content.retry_count should be 1, got {content['retry_count']}"
    )


async def test_stage_exceeds_max_retries(conn):
    """When retry_count >= 3, retry_stage raises MaxRetriesExceeded — no DB state changed."""
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_a_id = topo["stage_ids"][0]

    # Set retry_count to 3 (at the limit)
    await conn.execute(
        "UPDATE stage SET retry_count = 3, state = 'active' WHERE id = $1::uuid",
        stage_a_id,
    )

    with pytest.raises(MaxRetriesExceeded):
        await retry_stage(conn, stage_a_id, actor_id)

    # Verify DB state was NOT changed
    stage_row = await conn.fetchrow(
        "SELECT state, retry_count FROM stage WHERE id = $1::uuid",
        stage_a_id,
    )
    assert stage_row["retry_count"] == 3, (
        f"retry_count should remain 3 after failed retry attempt, got {stage_row['retry_count']}"
    )
    assert str(stage_row["state"]) == "active", (
        f"Stage state should remain 'active' after failed retry, got '{stage_row['state']}'"
    )
