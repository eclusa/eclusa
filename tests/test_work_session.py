"""
tests/test_work_session.py — Work session lifecycle tests.

Requirements: WORK-01, WORK-02, WORK-03, WORK-04, WORK-05, WORK-08
Implemented in: 03-02-PLAN
"""

import json
from unittest.mock import MagicMock

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from harness.message_format import deserialize_history, serialize_history
from harness.native import (
    pause_work_session,
    resume_work_session,
    run_session_turn,
    start_work_session,
)
from harness.snapshot import SnapshotStore
from tests.helpers.topology import seed_linear_cascade


def make_test_agent(response: str = "test response") -> Agent:
    """Create a pydantic-ai Agent backed by TestModel — no real API calls."""
    model = TestModel()
    return Agent(model)


@pytest.fixture
async def topology(conn):
    """Seed a minimal cascade + stage + actor for work session tests."""
    return await seed_linear_cascade(conn)


# WORK-01: start_work_session creates a DB record with state='running' and ledger entry


async def test_session_start_creates_db_record(conn, topology):
    """WORK-01: start_work_session inserts work_session row with state='running'."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    session_id = await start_work_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
    )

    # Verify work_session row
    row = await conn.fetchrow(
        "SELECT state, harness_type, model FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row is not None, "work_session row not found"
    assert row["state"] == "running"
    assert row["harness_type"] == "native"
    assert row["model"] == "anthropic:claude-3-5-haiku-latest"

    # Verify ledger entry
    ledger_row = await conn.fetchrow(
        "SELECT type FROM ledger_entry WHERE session_id = $1::uuid",
        session_id,
    )
    assert ledger_row is not None, "ledger_entry not found for session"
    assert ledger_row["type"] == "work_session_started"


# WORK-02: message_history written to DB per turn (platform format)


async def test_message_history_written_per_turn(conn, topology):
    """WORK-02: run_session_turn writes updated message_history to DB in platform format."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    session_id = await start_work_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
    )

    agent = make_test_agent()
    output, all_messages = await run_session_turn(
        conn=conn,
        session_id=session_id,
        agent=agent,
        user_message="hello",
    )

    # Verify message_history is non-empty in DB
    row = await conn.fetchrow(
        "SELECT message_history FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row is not None
    history = row["message_history"]
    if isinstance(history, str):
        history = json.loads(history)
    assert isinstance(history, list)
    assert len(history) > 0, "message_history should be non-empty after a turn"

    # Verify round-trip: deserialize and re-serialize gives same structure
    restored = deserialize_history(history)
    reserialized = serialize_history(restored)
    assert reserialized == history


# WORK-03: pause_work_session writes snapshot to filesystem


async def test_pause_writes_snapshot(conn, topology, tmp_path):
    """WORK-03: pause_work_session saves snapshot to disk and sets state='paused'."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    session_id = await start_work_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
    )

    agent = make_test_agent()
    await run_session_turn(
        conn=conn,
        session_id=session_id,
        agent=agent,
        user_message="do some work",
    )

    snapshot_store = SnapshotStore(base_dir=str(tmp_path))
    await pause_work_session(
        conn=conn, session_id=session_id, snapshot_store=snapshot_store
    )

    # Verify state in DB
    row = await conn.fetchrow(
        "SELECT state, workspace_ref FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row["state"] == "paused"
    assert row["workspace_ref"] is not None

    # Verify snapshot file exists
    assert snapshot_store.snapshot_exists(session_id), (
        "snapshot file should exist after pause"
    )

    # Verify ledger entry for paused
    ledger_row = await conn.fetchrow(
        "SELECT type FROM ledger_entry WHERE session_id = $1::uuid AND type = 'work_session_paused'",
        session_id,
    )
    assert ledger_row is not None, "work_session_paused ledger entry not found"


# WORK-04: resume_work_session restores history transparently


async def test_resume_restores_history(conn, topology, tmp_path):
    """WORK-04: resume_work_session loads snapshot and returns message history."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    session_id = await start_work_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
    )

    agent = make_test_agent()
    _output, original_messages = await run_session_turn(
        conn=conn,
        session_id=session_id,
        agent=agent,
        user_message="first message",
    )
    original_history = serialize_history(original_messages)

    snapshot_store = SnapshotStore(base_dir=str(tmp_path))
    await pause_work_session(
        conn=conn, session_id=session_id, snapshot_store=snapshot_store
    )

    restored_data = await resume_work_session(
        conn=conn,
        session_id=session_id,
        snapshot_store=snapshot_store,
    )

    # State back to running
    row = await conn.fetchrow(
        "SELECT state, workspace_ref FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row["state"] == "running"
    assert row["workspace_ref"] is None

    # Restored history matches original
    assert restored_data == original_history, (
        "restored history should match pre-pause history"
    )

    # Ledger entry for resumed
    ledger_row = await conn.fetchrow(
        "SELECT type FROM ledger_entry WHERE session_id = $1::uuid AND type = 'work_session_resumed'",
        session_id,
    )
    assert ledger_row is not None, "work_session_resumed ledger entry not found"


# WORK-05: model hot-swap between pause and resume preserves history


async def test_model_hotswap_preserves_history(conn, topology, tmp_path):
    """WORK-05: resume with new_model updates model and model_swaps; history unchanged."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    model_a = "anthropic:claude-3-5-haiku-latest"
    model_b = "anthropic:claude-3-opus-latest"

    session_id = await start_work_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model=model_a,
        actor_id=actor_id,
    )

    agent = make_test_agent()
    _output, original_messages = await run_session_turn(
        conn=conn,
        session_id=session_id,
        agent=agent,
        user_message="work before swap",
    )
    original_history = serialize_history(original_messages)

    snapshot_store = SnapshotStore(base_dir=str(tmp_path))
    await pause_work_session(
        conn=conn, session_id=session_id, snapshot_store=snapshot_store
    )

    restored_data = await resume_work_session(
        conn=conn,
        session_id=session_id,
        new_model=model_b,
        snapshot_store=snapshot_store,
    )

    # Model updated
    row = await conn.fetchrow(
        "SELECT model, model_swaps FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row["model"] == model_b, "model should be updated to model_b after hot-swap"

    # model_swaps has the swap record
    model_swaps = row["model_swaps"]
    if isinstance(model_swaps, str):
        model_swaps = json.loads(model_swaps)
    assert isinstance(model_swaps, list)
    assert len(model_swaps) == 1, "should have exactly one swap record"
    swap = model_swaps[0]
    assert swap["from"] == model_a
    assert swap["to"] == model_b

    # Message history unchanged after swap
    assert restored_data == original_history, (
        "history should be identical after model hot-swap"
    )


# WORK-08: cost tracking accumulates per turn


async def test_cost_tracked_per_api_call(conn, topology):
    """WORK-08: cost JSONB accumulates tokens_in/out, api_calls, wall_time_ms per turn."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    session_id = await start_work_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
    )

    agent = make_test_agent()

    # Run two turns — cost should accumulate
    await run_session_turn(
        conn=conn,
        session_id=session_id,
        agent=agent,
        user_message="turn one",
    )
    await run_session_turn(
        conn=conn,
        session_id=session_id,
        agent=agent,
        user_message="turn two",
    )

    row = await conn.fetchrow(
        "SELECT cost FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    cost = row["cost"]
    if isinstance(cost, str):
        cost = json.loads(cost)

    assert cost.get("api_calls") == 2, (
        f"Expected 2 api_calls, got {cost.get('api_calls')}"
    )
    assert cost.get("tokens_in", 0) > 0, "tokens_in should be positive after turns"
    assert cost.get("tokens_out", 0) > 0, "tokens_out should be positive after turns"
    assert "wall_time_ms" in cost, "wall_time_ms should be tracked"


# WORK-01 (addon variant): register_session called on start


async def test_start_work_session_calls_addon_register(conn, topology):
    """D-11: start_work_session calls addon.register_session with correct session_id and context."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    addon = MagicMock()

    session_id = await start_work_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
        addon=addon,
    )

    addon.register_session.assert_called_once_with(
        session_id,
        {
            "intent_id": intent_id,
            "cascade_id": cascade_id,
            "stage_id": stage_id,
        },
    )
