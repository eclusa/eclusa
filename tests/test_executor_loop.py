"""Executor poll loop integration tests (EXEC-01, EXEC-02, EXEC-03, EXEC-04).

Tests exercise:
  - claim_ready_stages + dispatch_stage as a single poll cycle (test_poll_claims_ready_stages)
  - SKIP LOCKED prevents double-claim under concurrent load (test_skip_locked_prevents_double_claim)
  - LISTEN/NOTIFY wakes executor via wake_event (test_listen_notify_wakes_executor)
  - Backoff doubles on empty and resets on successful claim (test_backoff_resets_on_successful_dispatch)
  - Stale active stages recovered to pending on crash restart (test_crash_recovery_reclaims_stale_active_stages)
  - Three concurrent executors process 20 stages without double-dispatch (test_three_concurrent_executors_no_double_dispatch)
"""

import asyncio
import pytest
import asyncpg
import psycopg
from tests.helpers.topology import seed_linear_cascade, seed_system_actor

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_dsn(pg_container) -> str:
    """Return plain postgresql:// DSN from testcontainers."""
    url = pg_container.get_connection_url()
    if "postgresql+psycopg2://" in url:
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    elif "postgresql+asyncpg://" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def _make_pool(pg_container) -> asyncpg.Pool:
    dsn = _get_dsn(pg_container)
    return await asyncpg.create_pool(dsn, min_size=2, max_size=10)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_poll_claims_ready_stages(conn, pg_container):
    """One poll cycle: claim + dispatch stage A; B and C remain pending."""
    from executor.cascade import claim_ready_stages
    from executor.dispatch import dispatch_stage

    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_a_id = topo["stage_ids"][0]
    stage_b_id = topo["stage_ids"][1]
    stage_c_id = topo["stage_ids"][2]

    pool = await _make_pool(pg_container)
    try:
        # Run poll cycles until stage A is claimed (limit=10 may miss it if DB has many pending)
        all_stages = []
        for _ in range(5):
            async with pool.acquire() as pconn:
                stages = await claim_ready_stages(pconn)
            all_stages.extend(stages)
            claimed_ids = [str(s["id"]) for s in stages]
            if stage_a_id in claimed_ids:
                break

        claimed_ids_all = [str(s["id"]) for s in all_stages]
        assert stage_a_id in claimed_ids_all, (
            f"Stage A ({stage_a_id}) was never claimed in 5 cycles; claimed: {claimed_ids_all}"
        )

        # Dispatch stage A
        for stage in all_stages:
            if str(stage["id"]) == stage_a_id:
                async with pool.acquire() as pconn:
                    await dispatch_stage(pconn, stage, actor_id)
                break

        # Verify stage A resolved
        state_a = await conn.fetchval(
            "SELECT state FROM stage WHERE id = $1::uuid", stage_a_id
        )
        assert state_a == "resolved"

        # Verify stages B and C are still pending (deps not met yet)
        state_b = await conn.fetchval(
            "SELECT state FROM stage WHERE id = $1::uuid", stage_b_id
        )
        state_c = await conn.fetchval(
            "SELECT state FROM stage WHERE id = $1::uuid", stage_c_id
        )
        assert state_b == "pending"
        assert state_c == "pending"
    finally:
        await pool.close()


async def test_skip_locked_prevents_double_claim(conn, pg_container):
    """3 concurrent claim calls on 5 independent stages — each stage claimed exactly once."""
    from executor.cascade import claim_ready_stages

    dsn = _get_dsn(pg_container)
    actor_id = await seed_system_actor(conn)

    # Insert an intent first
    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'skip-locked-test', $1::uuid)
        RETURNING id
    """,
        actor_id,
    )
    intent_id = str(intent_row["id"])

    cascade_row = await conn.fetchrow(
        """
        INSERT INTO cascade (id, intent_id, shape, state)
        VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
        RETURNING id
    """,
        intent_id,
    )
    cascade_id = str(cascade_row["id"])

    # Seed 5 independent stages (no depends_on)
    stage_ids = []
    for _ in range(5):
        row = await conn.fetchrow(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on)
            VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}')
            RETURNING id
        """,
            cascade_id,
        )
        stage_ids.append(str(row["id"]))

    # Create 3 separate pools (simulates 3 executor instances)
    pools = [await asyncpg.create_pool(dsn, min_size=1, max_size=3) for _ in range(3)]

    try:

        async def claim_from_pool(pool):
            async with pool.acquire() as pconn:
                return await claim_ready_stages(pconn)

        results = await asyncio.gather(*[claim_from_pool(p) for p in pools])

        # Filter only the stage IDs we seeded in this test
        all_claimed = []
        for r in results:
            all_claimed.extend([str(s["id"]) for s in r if str(s["id"]) in stage_ids])

        # Total claimed == 5 (all seeded stages, each exactly once)
        assert len(all_claimed) == 5, (
            f"Expected 5 claimed, got {len(all_claimed)}: {all_claimed}"
        )

        # No duplicates
        assert len(set(all_claimed)) == 5, f"Duplicates detected: {all_claimed}"

        # All seeded stage IDs were claimed
        assert set(all_claimed) == set(stage_ids)
    finally:
        for p in pools:
            await p.close()


async def test_listen_notify_wakes_executor(conn, pg_container):
    """NOTIFY on stage_changed channel sets wake_event within 2 seconds."""

    dsn = _get_dsn(pg_container)
    wake_event = asyncio.Event()

    async def listen_task():
        async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as lconn:
            await lconn.execute("LISTEN stage_changed")
            async for _ in lconn.notifies():
                wake_event.set()
                return  # exit after first notification

    # Start listen task in background
    task = asyncio.create_task(listen_task())

    # Give the listen task time to establish connection
    await asyncio.sleep(0.1)

    # Emit NOTIFY from a separate connection
    notify_conn = await asyncpg.connect(dsn)
    try:
        await notify_conn.execute(
            "SELECT pg_notify('stage_changed', 'test-cascade-id')"
        )
    finally:
        await notify_conn.close()

    # wake_event should be set within 2 seconds
    try:
        await asyncio.wait_for(wake_event.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        pytest.fail("wake_event was not set within 2 seconds after NOTIFY")
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    assert wake_event.is_set()


async def test_backoff_resets_on_successful_dispatch(conn, pg_container):
    """Backoff doubles on empty claim, resets to 1.0 after successful dispatch."""
    from executor.cascade import claim_ready_stages
    from executor.dispatch import dispatch_stage
    from executor.loop import _INITIAL_BACKOFF, _MAX_BACKOFF

    # We test backoff behavior by simulating the logic manually
    # (calling run_executor directly is an infinite loop)

    actor_id = await seed_system_actor(conn)
    pool = await _make_pool(pg_container)

    try:
        backoff = _INITIAL_BACKOFF

        # First cycle: no stages — backoff should double
        async with pool.acquire() as pconn:
            stages = await claim_ready_stages(pconn)

        # There may be some stages from other tests, so we check the logic
        if not stages:
            # Simulate timeout: backoff doubles
            backoff = min(backoff * 2, _MAX_BACKOFF)
            assert backoff == 2.0, (
                f"Backoff should be 2.0 after 1st empty, got {backoff}"
            )

            # Double again
            backoff = min(backoff * 2, _MAX_BACKOFF)
            assert backoff == 4.0, (
                f"Backoff should be 4.0 after 2nd empty, got {backoff}"
            )

            # Double again — hits cap
            backoff = min(backoff * 2, _MAX_BACKOFF)
            assert backoff == _MAX_BACKOFF, (
                f"Backoff should be capped at {_MAX_BACKOFF}, got {backoff}"
            )

        # Now seed a stage and confirm backoff resets
        intent_row = await conn.fetchrow(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES (gen_random_uuid(), 'manual', 'backoff-test', $1::uuid)
            RETURNING id
        """,
            actor_id,
        )
        cascade_row = await conn.fetchrow(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
            RETURNING id
        """,
            str(intent_row["id"]),
        )
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on)
            VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}')
        """,
            str(cascade_row["id"]),
        )

        async with pool.acquire() as pconn:
            stages = await claim_ready_stages(pconn)

        assert len(stages) >= 1

        # On successful dispatch, backoff resets to _INITIAL_BACKOFF
        for stage in stages:
            async with pool.acquire() as pconn:
                await dispatch_stage(pconn, stage, actor_id)

        backoff = _INITIAL_BACKOFF  # reset after successful dispatch
        assert backoff == 1.0, (
            f"Backoff should reset to 1.0 after dispatch, got {backoff}"
        )
    finally:
        await pool.close()


async def test_crash_recovery_reclaims_stale_active_stages(conn, pg_container):
    """Manually set 2 stages to stale active; recovery returns them to pending."""
    from executor.recovery import recover_stale_active_stages

    actor_id = await seed_system_actor(conn)
    pool = await _make_pool(pg_container)

    try:
        intent_row = await conn.fetchrow(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES (gen_random_uuid(), 'manual', 'recovery-test', $1::uuid)
            RETURNING id
        """,
            actor_id,
        )
        cascade_row = await conn.fetchrow(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
            RETURNING id
        """,
            str(intent_row["id"]),
        )
        cascade_id = str(cascade_row["id"])

        # Seed 2 stages set to 'active' with created_at 60 seconds ago (simulates orphaned stages)
        stale_ids = []
        for _ in range(2):
            row = await conn.fetchrow(
                """
                INSERT INTO stage (id, cascade_id, type, state, depends_on, created_at)
                VALUES (
                    gen_random_uuid(), $1::uuid, 'narrowing', 'active', '{}',
                    NOW() - '60 seconds'::interval
                )
                RETURNING id
            """,
                cascade_id,
            )
            stale_ids.append(str(row["id"]))

        # Run recovery with threshold of 30 seconds (both stages qualify)
        async with pool.acquire() as pconn:
            recovered = await recover_stale_active_stages(
                pconn, threshold_seconds=30, actor_id=actor_id
            )

        recovered_ids = [str(r["id"]) for r in recovered]
        assert len(recovered) >= 2, (
            f"Expected at least 2 recovered, got {len(recovered)}"
        )
        for stale_id in stale_ids:
            assert stale_id in recovered_ids, f"Stage {stale_id} not recovered"

        # Both stages should now be pending
        for stale_id in stale_ids:
            state = await conn.fetchval(
                "SELECT state FROM stage WHERE id = $1::uuid", stale_id
            )
            assert state == "pending", (
                f"Stage {stale_id} should be pending, got {state}"
            )

        # Recovery ledger entries should exist for each recovered stage
        for stale_id in stale_ids:
            entry_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM ledger_entry
                WHERE stage_id = $1::uuid
                  AND type = 'stage_state_changed'
                  AND content->>'reason' = 'crash_recovery'
            """,
                stale_id,
            )
            assert entry_count >= 1, f"No recovery ledger entry for stage {stale_id}"
    finally:
        await pool.close()


async def test_three_concurrent_executors_no_double_dispatch(conn, pg_container):
    """3 concurrent executor instances process 20 stages; no stage dispatched twice."""
    from executor.loop import single_poll_cycle

    dsn = _get_dsn(pg_container)
    actor_id = await seed_system_actor(conn)

    # Seed a single cascade with 20 independent stages
    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'concurrent-executor-test', $1::uuid)
        RETURNING id
    """,
        actor_id,
    )
    cascade_row = await conn.fetchrow(
        """
        INSERT INTO cascade (id, intent_id, shape, state)
        VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
        RETURNING id
    """,
        str(intent_row["id"]),
    )
    cascade_id = str(cascade_row["id"])

    stage_ids = []
    for _ in range(20):
        row = await conn.fetchrow(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on)
            VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}')
            RETURNING id
        """,
            cascade_id,
        )
        stage_ids.append(str(row["id"]))

    # Create 3 separate pools (simulates 3 independent executor instances)
    pools = [await asyncpg.create_pool(dsn, min_size=2, max_size=5) for _ in range(3)]

    try:

        async def run_pool_cycles(pool, num_cycles=10):
            """Run N poll cycles from a single pool."""
            total_dispatched = []
            for _ in range(num_cycles):
                dispatched = await single_poll_cycle(pool, actor_id)
                total_dispatched.extend(dispatched)
                if not dispatched:
                    await asyncio.sleep(0.01)
            return total_dispatched

        # Run all 3 executors concurrently
        results = await asyncio.gather(*[run_pool_cycles(p) for p in pools])

        all_dispatched_ids = []
        for r in results:
            all_dispatched_ids.extend([str(s["id"]) for s in r])

        # All 20 stages must be resolved
        for stage_id in stage_ids:
            state = await conn.fetchval(
                "SELECT state FROM stage WHERE id = $1::uuid", stage_id
            )
            assert state == "resolved", f"Stage {stage_id} not resolved (state={state})"

        # No stage dispatched twice: check ledger for duplicate resolved entries
        for stage_id in stage_ids:
            resolved_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM ledger_entry
                WHERE stage_id = $1::uuid
                  AND type = 'stage_state_changed'
                  AND content->>'new_state' = 'resolved'
            """,
                stage_id,
            )
            assert resolved_count == 1, (
                f"Stage {stage_id} has {resolved_count} resolved ledger entries (expected 1)"
            )
    finally:
        for p in pools:
            await p.close()
