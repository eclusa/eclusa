"""
tests/test_claude_code_harness.py — Claude Code harness lifecycle tests.
"""

import json
from unittest.mock import MagicMock

import pytest

from harness.claude_code import (
    capture_claude_code_message,
    complete_claude_code_session,
    start_claude_code_session,
)
from harness.message_format import serialize_history
from tests.helpers.topology import seed_linear_cascade


@pytest.fixture
async def topology(conn):
    """Seed a minimal cascade + stage + actor for Claude Code harness tests."""
    return await seed_linear_cascade(conn)


async def test_start_claude_code_session_creates_db_record(conn, topology):
    """start_claude_code_session inserts a running work_session with claude_code type."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    session_id = await start_claude_code_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
    )

    assert isinstance(session_id, str)

    row = await conn.fetchrow(
        "SELECT state, harness_type, model FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row is not None
    assert row["state"] == "running"
    assert row["harness_type"] == "claude_code"
    assert row["model"] == "anthropic:claude-3-5-haiku-latest"

    ledger_row = await conn.fetchrow(
        "SELECT type FROM ledger_entry WHERE session_id = $1::uuid",
        session_id,
    )
    assert ledger_row is not None
    assert ledger_row["type"] == "work_session_started"


async def test_start_claude_code_session_registers_addon(conn, topology):
    """start_claude_code_session registers the proxy session with the addon."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    addon = MagicMock()

    session_id = await start_claude_code_session(
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


async def test_capture_claude_code_message_writes_platform_history(conn, topology):
    """capture_claude_code_message stores external messages as platform JSONB."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    session_id = await start_claude_code_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
    )

    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    await capture_claude_code_message(
        conn=conn, session_id=session_id, messages=messages
    )

    row = await conn.fetchrow(
        "SELECT message_history FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row is not None
    history = row["message_history"]
    if isinstance(history, str):
        history = json.loads(history)
    assert history == serialize_history(messages)


async def test_complete_claude_code_session_marks_complete_and_deregisters(
    conn, topology
):
    """complete_claude_code_session marks the session complete and deregisters addon."""
    topo = topology
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]
    intent_id = topo["intent_id"]
    actor_id = topo["actor_id"]

    addon = MagicMock()

    session_id = await start_claude_code_session(
        conn=conn,
        stage_id=stage_id,
        intent_id=intent_id,
        cascade_id=cascade_id,
        model="anthropic:claude-3-5-haiku-latest",
        actor_id=actor_id,
        addon=addon,
    )

    await complete_claude_code_session(
        conn=conn,
        session_id=session_id,
        actor_id=actor_id,
        addon=addon,
    )

    row = await conn.fetchrow(
        "SELECT state, completed_at FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row is not None
    assert row["state"] == "completed"
    assert row["completed_at"] is not None

    ledger_row = await conn.fetchrow(
        "SELECT type FROM ledger_entry WHERE session_id = $1::uuid AND type = 'work_session_completed'",
        session_id,
    )
    assert ledger_row is not None
    assert ledger_row["type"] == "work_session_completed"

    addon.deregister_session.assert_called_once_with(session_id)
