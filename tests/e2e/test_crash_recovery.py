"""EXEC-E2E-03: Crash recovery — no duplicate dispatches after kill/restart.

Proves:
  - Orphaned 'active' stages are recovered to 'pending' by recover_stale_active_stages
  - Recovered stages dispatch normally in the next cycle
  - Completed stages are never re-dispatched after recovery
  - No duplicate ledger entries from the recovery path
"""

import pytest

from executor.loop import single_poll_cycle
from executor.recovery import recover_stale_active_stages
from tests.e2e.conftest import cleanup_cascade, seed_cascade_with_deps

pytestmark = pytest.mark.asyncio


async def _get_stage_state(conn, stage_id: str) -> str:
    """Query the current state of a stage by ID."""
    row = await conn.fetchrow(
        "SELECT state FROM stage WHERE id = $1::uuid", stage_id
    )
    return str(row["state"]) if row else "NOT_FOUND"


async def _get_cascade_state(conn, cascade_id: str) -> str:
    """Query the current state of a cascade by ID."""
    row = await conn.fetchrow(
        "SELECT state FROM cascade WHERE id = $1::uuid", cascade_id
    )
    return str(row["state"]) if row else "NOT_FOUND"


async def test_crash_recovery_no_duplicate_dispatches(e2e_pool, db_conn, seed_actor):
    """Simulate a crash mid-dispatch and verify recovery without duplicates.

    Sequence:
      1. Seed 5-stage cascade, dispatch A (cycle 1)
      2. Manually set stage B to 'active' with old created_at (simulates crash)
      3. Run recover_stale_active_stages -> B returns to 'pending'
      4. Dispatch cycle 2 -> B and D both dispatch (B recovered, D was pending)
      5. Dispatch cycle 3 -> C and E dispatch
      6. Cascade completes
      7. Verify no duplicate recovery ledger entries for B
    """
    data = await seed_cascade_with_deps(db_conn, seed_actor)
    cascade_id = data["cascade_id"]
    stages = data["stages"]

    try:
        # --- Cycle 1: dispatch and resolve stage A ---
        await single_poll_cycle(e2e_pool, seed_actor)

        state_a = await _get_stage_state(db_conn, stages["A"])
        assert state_a == "resolved", f"Stage A should be resolved, got {state_a}"

        # --- Simulate crash: set B to 'active' with old created_at ---
        # This simulates: executor claimed B, started dispatch, then crashed.
        # The created_at is set 5 minutes in the past to exceed the stale threshold.
        await db_conn.execute(
            """
            UPDATE stage
            SET state = 'active', created_at = NOW() - interval '5 minutes'
            WHERE id = $1::uuid
            """,
            stages["B"],
        )

        state_b_before = await _get_stage_state(db_conn, stages["B"])
        assert state_b_before == "active", (
            f"Stage B should be active (simulated crash), got {state_b_before}"
        )

        # --- Run recovery with a low threshold to catch the stale stage ---
        recovered = await recover_stale_active_stages(
            db_conn, threshold_seconds=1, actor_id=seed_actor
        )

        # Verify recovery found exactly stage B
        assert len(recovered) >= 1, "Recovery should find at least stage B"
        recovered_ids = {str(r["id"]) for r in recovered}
        assert stages["B"] in recovered_ids, (
            f"Stage B ({stages['B']}) should be in recovered set: {recovered_ids}"
        )

        # Verify B is back to 'pending'
        state_b_after = await _get_stage_state(db_conn, stages["B"])
        assert state_b_after == "pending", (
            f"Stage B should be pending after recovery, got {state_b_after}"
        )

        # --- Cycle 2: B (recovered) and D (still pending) should dispatch ---
        await single_poll_cycle(e2e_pool, seed_actor)

        state_b = await _get_stage_state(db_conn, stages["B"])
        state_d = await _get_stage_state(db_conn, stages["D"])
        assert state_b == "resolved", f"Stage B should be resolved after cycle 2, got {state_b}"
        assert state_d == "resolved", f"Stage D should be resolved after cycle 2, got {state_d}"

        # --- Cycle 3: C and E should dispatch ---
        await single_poll_cycle(e2e_pool, seed_actor)

        state_c = await _get_stage_state(db_conn, stages["C"])
        state_e = await _get_stage_state(db_conn, stages["E"])
        assert state_c == "resolved", f"Stage C should be resolved after cycle 3, got {state_c}"
        assert state_e == "resolved", f"Stage E should be resolved after cycle 3, got {state_e}"

        # --- Cascade should be completed ---
        cascade_state = await _get_cascade_state(db_conn, cascade_id)
        assert cascade_state == "completed", (
            f"Cascade should be completed, got {cascade_state}"
        )

        # --- Verify no duplicate recovery ledger entries for stage B ---
        # Count 'crash_recovery' reason entries for stage B
        recovery_entries = await db_conn.fetchval(
            """
            SELECT COUNT(*) FROM ledger_entry
            WHERE stage_id = $1::uuid
              AND type = 'stage_state_changed'
              AND content->>'reason' = 'crash_recovery'
            """,
            stages["B"],
        )
        assert recovery_entries == 1, (
            f"Stage B should have exactly 1 crash_recovery ledger entry, got {recovery_entries}"
        )

    finally:
        await cleanup_cascade(db_conn, cascade_id)


async def test_no_double_dispatch_after_restart(e2e_pool, db_conn, seed_actor):
    """Completed stages are never re-dispatched after executor restart.

    Sequence:
      1. Seed cascade, run all cycles to completion
      2. Run another single_poll_cycle -> returns empty
      3. Run recover_stale_active_stages -> returns empty
      4. This proves: completed stages are not re-dispatched
    """
    data = await seed_cascade_with_deps(db_conn, seed_actor)
    cascade_id = data["cascade_id"]
    stages = data["stages"]

    try:
        # Run all cycles to completion
        for _ in range(10):
            dispatched = await single_poll_cycle(e2e_pool, seed_actor)
            if not dispatched:
                break

        # Verify all stages resolved
        for name, stage_id in stages.items():
            state = await _get_stage_state(db_conn, stage_id)
            assert state == "resolved", (
                f"Stage {name} should be resolved, got {state}"
            )

        # Verify cascade completed
        cascade_state = await _get_cascade_state(db_conn, cascade_id)
        assert cascade_state == "completed", (
            f"Cascade should be completed, got {cascade_state}"
        )

        # Record resolved_at timestamps for all stages
        timestamps = {}
        for name, stage_id in stages.items():
            row = await db_conn.fetchrow(
                "SELECT resolved_at FROM stage WHERE id = $1::uuid", stage_id
            )
            timestamps[name] = row["resolved_at"]

        # --- Run another poll cycle: should return empty ---
        extra_dispatched = await single_poll_cycle(e2e_pool, seed_actor)
        assert extra_dispatched == [], (
            f"No stages should dispatch after completion, got {len(extra_dispatched)}"
        )

        # --- Run recovery: should return empty ---
        recovered = await recover_stale_active_stages(
            db_conn, threshold_seconds=1, actor_id=seed_actor
        )
        assert recovered == [], (
            f"No stale stages should exist after clean completion, got {len(recovered)}"
        )

        # --- Verify resolved_at timestamps unchanged ---
        for name, stage_id in stages.items():
            row = await db_conn.fetchrow(
                "SELECT resolved_at FROM stage WHERE id = $1::uuid", stage_id
            )
            assert row["resolved_at"] == timestamps[name], (
                f"Stage {name} resolved_at should not change after re-poll"
            )

    finally:
        await cleanup_cascade(db_conn, cascade_id)
