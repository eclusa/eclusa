"""GATE-E2E-01 / GATE-E2E-02: Gate lifecycle — blocking and resolution.

Proves:
  - A gate stage (type='gate') blocks its downstream stages until resolved
  - Resolving a gate via resolve_gate() unblocks downstream and the executor
    dispatches it within the same poll cycle
  - The cascade completes after gate resolution and downstream dispatch

Topology: narrowing_A -> gate_B -> narrowing_C
"""

import asyncio
import json
import uuid

import pytest

from executor.dispatch import resolve_gate
from executor.loop import single_poll_cycle

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _cleanup_gate_cascade(conn, cascade_id: str) -> None:
    """Delete a gate test cascade and all related rows in correct FK order.

    Robust variant that handles concurrent executor writes by performing
    all deletes inside a single transaction (atomically).
    """
    row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid", cascade_id
    )
    if row is None:
        return
    intent_id = str(row["intent_id"])

    stage_rows = await conn.fetch(
        "SELECT id FROM stage WHERE cascade_id = $1::uuid", cascade_id
    )
    stage_ids = [r["id"] for r in stage_rows]

    await conn.execute(
        "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
    )
    try:
        async with conn.transaction():
            # Work sessions
            if stage_ids:
                await conn.execute(
                    "DELETE FROM work_session WHERE stage_ids && $1::uuid[]",
                    stage_ids,
                )
            # Ledger entries first (FK references both stage and cascade)
            await conn.execute(
                "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cascade_id
            )
            # Stages
            await conn.execute(
                "DELETE FROM stage WHERE cascade_id = $1::uuid", cascade_id
            )
            # Cascade
            await conn.execute(
                "DELETE FROM cascade WHERE id = $1::uuid", cascade_id
            )
            # Intent
            await conn.execute(
                "DELETE FROM intent WHERE id = $1::uuid", intent_id
            )
    finally:
        await conn.execute(
            "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
        )


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


async def _wait_for_stage_state(
    conn, stage_id: str, expected: str, timeout: float = 3.0
) -> str:
    """Poll a stage's state until it matches expected or timeout.

    The live executor container may compete with tests for claiming stages.
    This helper accommodates the race by polling instead of asserting once.
    Returns the final state observed.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    state = await _get_stage_state(conn, stage_id)
    while state != expected and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)
        state = await _get_stage_state(conn, stage_id)
    return state


async def _wait_for_cascade_state(
    conn, cascade_id: str, expected: str, timeout: float = 3.0
) -> str:
    """Poll a cascade's state until it matches expected or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    state = await _get_cascade_state(conn, cascade_id)
    while state != expected and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)
        state = await _get_cascade_state(conn, cascade_id)
    return state


async def seed_gate_cascade(conn, actor_id: str) -> dict:
    """Seed a 3-stage cascade: narrowing_A -> gate_B -> narrowing_C.

    Returns:
        {
            "intent_id": str,
            "cascade_id": str,
            "stages": {"A": str, "B": str, "C": str},
        }
    """
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_ids = {name: str(uuid.uuid4()) for name in ("A", "B", "C")}

    async with conn.transaction():
        # Intent
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api'::intent_source, 'E2E gate lifecycle test', $2::uuid)
            """,
            intent_id,
            actor_id,
        )

        # Cascade
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{"test":"gate_lifecycle"}'::jsonb, 'active'::cascade_state)
            """,
            cascade_id,
            intent_id,
        )

        # Stage A: narrowing, no dependencies
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state,
                    '{}'::uuid[], '{}'::jsonb)
            """,
            stage_ids["A"],
            cascade_id,
        )

        # Stage B: gate, depends on A
        gate_input = json.dumps({
            "gate_type": "default",
            "gate_description": "E2E test gate",
            "model_recommendation": "approve",
        })
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'gate'::stage_type, 'pending'::stage_state,
                    ARRAY[$3::uuid], $4::jsonb)
            """,
            stage_ids["B"],
            cascade_id,
            stage_ids["A"],
            gate_input,
        )

        # Stage C: narrowing, depends on B (the gate)
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state,
                    ARRAY[$3::uuid], '{}'::jsonb)
            """,
            stage_ids["C"],
            cascade_id,
            stage_ids["B"],
        )

    return {
        "intent_id": intent_id,
        "cascade_id": cascade_id,
        "stages": stage_ids,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_gate_blocks_downstream(e2e_pool, db_conn, seed_actor):
    """GATE-E2E-01: A gate stage blocks its downstream until resolved.

    1. Dispatch A (narrowing, auto-resolves immediately)
    2. Dispatch B (gate, becomes blocked via surface_gate)
    3. Assert C stays pending -- blocked gate B is NOT a terminal state
    4. Another poll cycle dispatches nothing (C depends on blocked B)
    """
    data = await seed_gate_cascade(db_conn, seed_actor)
    cascade_id = data["cascade_id"]
    stages = data["stages"]

    try:
        # --- Cycle 1: dispatch A (narrowing -> resolved immediately) ---
        await single_poll_cycle(e2e_pool, seed_actor)
        state_a = await _wait_for_stage_state(db_conn, stages["A"], "resolved")
        assert state_a == "resolved", f"Stage A should be resolved, got {state_a}"

        # --- Cycle 2: dispatch B (gate -> blocked via surface_gate) ---
        await single_poll_cycle(e2e_pool, seed_actor)
        state_b = await _wait_for_stage_state(db_conn, stages["B"], "blocked")
        assert state_b == "blocked", f"Stage B (gate) should be blocked, got {state_b}"

        # C must still be pending -- blocked gate is NOT terminal
        state_c = await _get_stage_state(db_conn, stages["C"])
        assert state_c == "pending", (
            f"Stage C should remain pending while gate B is blocked, got {state_c}"
        )

        # --- Cycle 3: nothing should be dispatchable ---
        dispatched_3 = await single_poll_cycle(e2e_pool, seed_actor)
        assert dispatched_3 == [], (
            f"No stages should dispatch while gate B is blocked, got {len(dispatched_3)}"
        )

        # C is still pending after the empty cycle
        state_c_again = await _get_stage_state(db_conn, stages["C"])
        assert state_c_again == "pending", (
            f"Stage C should still be pending after empty cycle, got {state_c_again}"
        )

    finally:
        await _cleanup_gate_cascade(db_conn, cascade_id)


async def test_gate_resolution_unblocks_downstream(e2e_pool, db_conn, seed_actor):
    """GATE-E2E-02: Resolving a gate unblocks downstream, cascade completes.

    1. Dispatch A (resolves), dispatch B (blocked)
    2. Resolve gate B via resolve_gate()
    3. Next poll cycle dispatches C (B is now resolved = terminal)
    4. Cascade completes
    5. Verify ledger entries for gate_resolved and stage_state_changed

    NOTE: The live executor container may compete for claiming stage C after
    gate resolution (resolve_gate fires pg_notify). The test uses poll-based
    state checks and drives a poll cycle to ensure C resolves regardless of
    which executor (test or container) claims it first.
    """
    data = await seed_gate_cascade(db_conn, seed_actor)
    cascade_id = data["cascade_id"]
    stages = data["stages"]

    try:
        # --- Drive to blocked state ---
        await single_poll_cycle(e2e_pool, seed_actor)  # dispatches A
        state_a = await _wait_for_stage_state(db_conn, stages["A"], "resolved")
        assert state_a == "resolved", f"Stage A should be resolved, got {state_a}"

        await single_poll_cycle(e2e_pool, seed_actor)  # dispatches B (blocked)
        state_b = await _wait_for_stage_state(db_conn, stages["B"], "blocked")
        assert state_b == "blocked", f"Stage B should be blocked, got {state_b}"

        state_c = await _get_stage_state(db_conn, stages["C"])
        assert state_c == "pending", f"Stage C should be pending, got {state_c}"

        # --- Resolve the gate ---
        await resolve_gate(db_conn, stages["B"], seed_actor)

        state_b_after = await _get_stage_state(db_conn, stages["B"])
        assert state_b_after == "resolved", (
            f"Stage B should be resolved after resolve_gate, got {state_b_after}"
        )

        # --- Drive dispatch: either our cycle or the live executor claims C ---
        # The resolve_gate pg_notify may wake the live executor, which could
        # claim C via SKIP LOCKED before our poll cycle. Either way, C must
        # reach 'resolved' because it's a plain narrowing stage.
        await single_poll_cycle(e2e_pool, seed_actor)

        # Wait for C to reach resolved (handles live executor race)
        state_c_after = await _wait_for_stage_state(
            db_conn, stages["C"], "resolved", timeout=5.0
        )
        assert state_c_after == "resolved", (
            f"Stage C should be resolved after dispatch, got {state_c_after}"
        )

        # --- Cascade should be completed ---
        cascade_state = await _wait_for_cascade_state(
            db_conn, cascade_id, "completed", timeout=5.0
        )
        assert cascade_state == "completed", (
            f"Cascade should be completed, got {cascade_state}"
        )

        # --- Verify ledger entries ---
        gate_resolved_count = await db_conn.fetchval(
            """
            SELECT COUNT(*) FROM ledger_entry
            WHERE cascade_id = $1::uuid AND type = 'gate_resolved'
            """,
            cascade_id,
        )
        assert gate_resolved_count >= 1, (
            f"Expected at least 1 gate_resolved ledger entry, got {gate_resolved_count}"
        )

        state_changed_count = await db_conn.fetchval(
            """
            SELECT COUNT(*) FROM ledger_entry
            WHERE cascade_id = $1::uuid AND type = 'stage_state_changed'
            """,
            cascade_id,
        )
        assert state_changed_count >= 1, (
            f"Expected stage_state_changed ledger entries, got {state_changed_count}"
        )

    finally:
        await _cleanup_gate_cascade(db_conn, cascade_id)
