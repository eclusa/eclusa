"""E2E test — session hot-swap preserves message history (COMP-E2E-03).

Proves:
1. pause_work_session saves snapshot, resume_work_session loads it
2. Model swap recorded in model_swaps JSONB column
3. Message history is identical after pause/resume cycle

Uses pydantic-ai TestModel (no live LLM call needed) — the requirement is about
message history preservation across model swaps, not LLM output quality.

Requires: docker compose up -d db (live Postgres).
"""

import json
import uuid

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from harness.message_format import deserialize_history, serialize_history
from harness.native import (
    complete_work_session,
    pause_work_session,
    resume_work_session,
    run_session_turn,
    start_work_session,
)
from harness.snapshot import SnapshotStore
from tests.e2e.conftest import cleanup_cascade

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SNAPSHOT_DIR = "/tmp/eclusa/test_snapshots"


async def seed_single_stage(conn, actor_id: str) -> dict:
    """Seed a minimal cascade with one narrowing stage for session testing."""
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api'::intent_source, 'Session hotswap E2E test', $2::uuid)
            """,
            intent_id,
            actor_id,
        )
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{"test": true}'::jsonb, 'active'::cascade_state)
            """,
            cascade_id,
            intent_id,
        )
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state,
                    '{}'::uuid[], '{}'::jsonb)
            """,
            stage_id,
            cascade_id,
        )

    return {
        "intent_id": intent_id,
        "cascade_id": cascade_id,
        "stage_id": stage_id,
    }


async def cleanup_session_and_cascade(conn, cascade_id: str):
    """Clean up work_session, ledger, and cascade data in correct FK order.

    Uses cleanup_cascade from conftest (which handles trigger disable/enable).
    If the executor wrote additional ledger entries concurrently, catch them
    with a broader cleanup before retrying.
    """
    try:
        await cleanup_cascade(conn, cascade_id)
    except Exception:
        # Retry: the executor may have written ledger entries concurrently.
        # Disable trigger and manually clean everything.
        await conn.execute(
            "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
        )
        try:
            # Get all stage IDs for this cascade
            stage_rows = await conn.fetch(
                "SELECT id FROM stage WHERE cascade_id = $1::uuid", cascade_id
            )
            stage_ids = [r["id"] for r in stage_rows]

            # Get intent_id
            row = await conn.fetchrow(
                "SELECT intent_id FROM cascade WHERE id = $1::uuid", cascade_id
            )
            if row is None:
                return
            intent_id = str(row["intent_id"])

            async with conn.transaction():
                # Delete ALL ledger entries that reference this cascade or its sessions
                await conn.execute(
                    "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cascade_id
                )
                if stage_ids:
                    # Also delete ledger entries referencing sessions for these stages
                    await conn.execute(
                        """
                        DELETE FROM ledger_entry WHERE session_id IN (
                            SELECT id FROM work_session WHERE stage_ids && $1::uuid[]
                        )
                        """,
                        stage_ids,
                    )
                    await conn.execute(
                        "DELETE FROM work_session WHERE stage_ids && $1::uuid[]",
                        stage_ids,
                    )
                # Also delete ledger entries for the judgment passes on these stages
                if stage_ids:
                    await conn.execute(
                        "DELETE FROM judgment_pass WHERE stage_ids && $1::uuid[]",
                        stage_ids,
                    )

                await conn.execute(
                    "DELETE FROM stage WHERE cascade_id = $1::uuid", cascade_id
                )
                await conn.execute(
                    "DELETE FROM cascade WHERE id = $1::uuid", cascade_id
                )
                await conn.execute(
                    "DELETE FROM intent WHERE id = $1::uuid", intent_id
                )
        finally:
            await conn.execute(
                "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
            )


# ---------------------------------------------------------------------------
# Test 1: Session pause/resume preserves history with model swap
# ---------------------------------------------------------------------------


async def test_session_pause_resume_preserves_history(db_conn, seed_actor):
    """COMP-E2E-03: pause on model-A, resume on model-B, history preserved."""
    actor_id = seed_actor
    seed = await seed_single_stage(db_conn, actor_id)
    stage_id = seed["stage_id"]
    cascade_id = seed["cascade_id"]
    intent_id = seed["intent_id"]

    try:
        # Start session with model-A
        session_id = await start_work_session(
            db_conn, stage_id, intent_id, cascade_id, "model-A", actor_id
        )

        # Run a turn with TestModel agent
        agent = Agent(TestModel())
        _output, messages_before = await run_session_turn(
            db_conn, session_id, agent, "Hello from model A"
        )
        assert len(messages_before) > 0, "Should have messages after a turn"

        # Pause the session
        snapshot_store = SnapshotStore(base_dir=SNAPSHOT_DIR)
        await pause_work_session(db_conn, session_id, snapshot_store)

        # Verify DB state after pause
        row = await db_conn.fetchrow(
            "SELECT state, workspace_ref FROM work_session WHERE id = $1::uuid",
            session_id,
        )
        assert row["state"] == "paused", f"Expected 'paused', got '{row['state']}'"
        assert row["workspace_ref"] is not None, "workspace_ref should be set after pause"

        # Resume with model-B
        restored = await resume_work_session(
            db_conn, session_id, new_model="model-B", snapshot_store=snapshot_store
        )

        # Verify DB state after resume
        row = await db_conn.fetchrow(
            "SELECT state, model, model_swaps FROM work_session WHERE id = $1::uuid",
            session_id,
        )
        assert row["state"] == "running", f"Expected 'running', got '{row['state']}'"
        assert row["model"] == "model-B", f"Expected 'model-B', got '{row['model']}'"

        # Verify model_swaps
        model_swaps = row["model_swaps"]
        if isinstance(model_swaps, str):
            model_swaps = json.loads(model_swaps)
        assert isinstance(model_swaps, list), "model_swaps should be a list"
        assert len(model_swaps) == 1, f"Expected 1 swap record, got {len(model_swaps)}"
        assert model_swaps[0]["from"] == "model-A"
        assert model_swaps[0]["to"] == "model-B"

        # Verify restored messages match original length
        assert isinstance(restored, list), "restored should be a list"
        serialized_before = serialize_history(messages_before)
        assert len(restored) == len(serialized_before), (
            f"Restored message count ({len(restored)}) != original ({len(serialized_before)})"
        )

        # Complete the session
        await complete_work_session(db_conn, session_id, actor_id)

    finally:
        await cleanup_session_and_cascade(db_conn, cascade_id)


# ---------------------------------------------------------------------------
# Test 2: Resume without swap keeps model
# ---------------------------------------------------------------------------


async def test_session_resume_without_swap_keeps_model(db_conn, seed_actor):
    """COMP-E2E-03: resume without new_model keeps original model, no swap record."""
    actor_id = seed_actor
    seed = await seed_single_stage(db_conn, actor_id)
    stage_id = seed["stage_id"]
    cascade_id = seed["cascade_id"]
    intent_id = seed["intent_id"]

    try:
        session_id = await start_work_session(
            db_conn, stage_id, intent_id, cascade_id, "model-A", actor_id
        )

        agent = Agent(TestModel())
        _output, messages_before = await run_session_turn(
            db_conn, session_id, agent, "Hello from model A"
        )

        snapshot_store = SnapshotStore(base_dir=SNAPSHOT_DIR)
        await pause_work_session(db_conn, session_id, snapshot_store)

        # Resume WITHOUT specifying a new model
        restored = await resume_work_session(
            db_conn, session_id, new_model=None, snapshot_store=snapshot_store
        )

        # Verify model stays the same
        row = await db_conn.fetchrow(
            "SELECT model, model_swaps FROM work_session WHERE id = $1::uuid",
            session_id,
        )
        assert row["model"] == "model-A", f"Expected 'model-A', got '{row['model']}'"

        # Verify model_swaps is empty (no swap happened)
        model_swaps = row["model_swaps"]
        if isinstance(model_swaps, str):
            model_swaps = json.loads(model_swaps)
        assert isinstance(model_swaps, list), "model_swaps should be a list"
        assert len(model_swaps) == 0, (
            f"Expected 0 swap records, got {len(model_swaps)}"
        )

        # Verify restored messages match
        serialized_before = serialize_history(messages_before)
        assert len(restored) == len(serialized_before)

        await complete_work_session(db_conn, session_id, actor_id)

    finally:
        await cleanup_session_and_cascade(db_conn, cascade_id)


# ---------------------------------------------------------------------------
# Test 3: Message history identical after swap (multi-turn)
# ---------------------------------------------------------------------------


async def test_session_message_history_identical_after_swap(db_conn, seed_actor):
    """COMP-E2E-03: 2 turns, pause, resume with swap, verify pre-pause messages intact."""
    actor_id = seed_actor
    seed = await seed_single_stage(db_conn, actor_id)
    stage_id = seed["stage_id"]
    cascade_id = seed["cascade_id"]
    intent_id = seed["intent_id"]

    try:
        session_id = await start_work_session(
            db_conn, stage_id, intent_id, cascade_id, "model-A", actor_id
        )

        agent = Agent(TestModel())

        # Turn 1
        _out1, msgs_after_t1 = await run_session_turn(
            db_conn, session_id, agent, "Turn 1 message"
        )

        # Turn 2 — pass prior messages as history
        _out2, msgs_after_t2 = await run_session_turn(
            db_conn, session_id, agent, "Turn 2 message", message_history=msgs_after_t1
        )

        # Read message_history from DB before pause
        row_pre = await db_conn.fetchrow(
            "SELECT message_history FROM work_session WHERE id = $1::uuid",
            session_id,
        )
        history_pre_pause = row_pre["message_history"]
        if isinstance(history_pre_pause, str):
            history_pre_pause = json.loads(history_pre_pause)

        # Pause
        snapshot_store = SnapshotStore(base_dir=SNAPSHOT_DIR)
        await pause_work_session(db_conn, session_id, snapshot_store)

        # Resume with model-B
        restored = await resume_work_session(
            db_conn, session_id, new_model="model-B", snapshot_store=snapshot_store
        )

        # Restored should match the pre-pause message history
        assert len(restored) == len(history_pre_pause), (
            f"Restored count ({len(restored)}) != pre-pause ({len(history_pre_pause)})"
        )

        # Compare message content: each message dict should be identical
        for i, (orig, rest) in enumerate(zip(history_pre_pause, restored)):
            assert orig == rest, (
                f"Message {i} differs after resume:\n"
                f"  original: {json.dumps(orig, default=str)[:200]}\n"
                f"  restored: {json.dumps(rest, default=str)[:200]}"
            )

        # Run a 3rd turn on the resumed session with a new agent.
        # Deserialize restored snapshot (raw dicts) back to pydantic-ai message objects
        # so agent.run() can include them in all_messages().
        agent_b = Agent(TestModel())
        restored_messages = deserialize_history(restored)
        _out3, msgs_after_t3 = await run_session_turn(
            db_conn,
            session_id,
            agent_b,
            "Turn 3 after swap",
            message_history=restored_messages,
        )

        # Read final DB history
        row_post = await db_conn.fetchrow(
            "SELECT message_history FROM work_session WHERE id = $1::uuid",
            session_id,
        )
        history_post = row_post["message_history"]
        if isinstance(history_post, str):
            history_post = json.loads(history_post)

        # Final history should be longer than pre-pause (added turn 3)
        assert len(history_post) > len(history_pre_pause), (
            f"Post-resume history ({len(history_post)}) should be longer than "
            f"pre-pause ({len(history_pre_pause)})"
        )

        # The first N messages (from turns 1+2) should be identical
        for i in range(len(history_pre_pause)):
            assert history_post[i] == history_pre_pause[i], (
                f"Pre-pause message {i} mutated after swap+turn3"
            )

        await complete_work_session(db_conn, session_id, actor_id)

    finally:
        await cleanup_session_and_cascade(db_conn, cascade_id)
