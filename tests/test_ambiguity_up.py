"""tests/test_ambiguity_up.py — Unit tests for the ambiguityUp tool.

Requirements: PIPE-03

Tests verify:
- test_ambiguity_up_creates_gate_stage: tool creates a gate-type stage with state='blocked'
- test_ambiguity_up_pauses_session: work_session.state is 'paused' after tool call
- test_ambiguity_up_surfaces_gate: ledger_entry of type 'gate_surfaced' exists
- test_ambiguity_up_returns_gate_id: tool return value contains the gate stage ID
- test_ambiguity_up_no_snapshot_store: snapshot_store=None pauses without crash
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from harness.ambiguity import AmbiguityContext, make_ambiguity_up_tool
from tests.helpers.topology import seed_linear_cascade

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_work_session(conn, stage_id: str, actor_id: str) -> str:
    """Insert a work_session row in state='running' and return session_id."""
    session_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO work_session (id, stage_ids, harness_type, model, state, cost)
        VALUES ($1::uuid, ARRAY[$2::uuid], 'native', 'test-model', 'running', '{}')
        """,
        session_id,
        stage_id,
    )
    # Insert a work_session_started ledger entry so pause_work_session can find actor_id
    await conn.execute(
        """
        INSERT INTO ledger_entry (
            id, stage_id, cascade_id, session_id, actor_id,
            type, content, schema_version
        )
        SELECT
            gen_random_uuid(),
            s.id,
            s.cascade_id,
            $3::uuid,
            $2::uuid,
            'work_session_started',
            jsonb_build_object('session_id', $3::text, 'model', 'test-model'),
            '0002'
        FROM stage s WHERE s.id = $1::uuid
        """,
        stage_id,
        actor_id,
        session_id,
    )
    return session_id


def _make_agent_and_tool() -> tuple[Agent, object]:
    """Create a minimal Agent with the ambiguityUp tool registered. Return (agent, tool)."""
    agent: Agent[AmbiguityContext, str] = Agent(TestModel(), deps_type=AmbiguityContext)
    make_ambiguity_up_tool(agent)
    tool = agent._function_toolset.tools["ambiguityUp"]
    return agent, tool


async def _call_tool(conn, session_id: str, cascade_id: str, actor_id: str, reason: str) -> str:
    """Call the ambiguityUp tool function directly, mocking surface_gate dispatch."""
    agent, tool = _make_agent_and_tool()

    ctx = RunContext(
        deps=AmbiguityContext(
            conn=conn,
            session_id=session_id,
            cascade_id=cascade_id,
            actor_id=actor_id,
            snapshot_store=None,
        ),
        model=TestModel(),
        usage=RunUsage(),
        agent=agent,
    )

    # Patch surface_gate to suppress adapter dispatch (no adapter registered in tests)
    with patch("harness.ambiguity.surface_gate", wraps=_surface_gate_no_adapter):
        result = await tool.function(ctx, reason=reason)

    return result


async def _surface_gate_no_adapter(conn, stage, actor_id):
    """Thin wrapper that calls the real surface_gate but silences missing adapter warnings."""
    from executor.dispatch import surface_gate as _real_surface_gate

    # Temporarily register a no-op adapter so surface_gate doesn't warn
    from adapters.registry import AdapterRegistry
    from adapters.protocol import AdapterProtocol, GateContext
    import adapters.registry as reg_module
    import executor.dispatch as dispatch_module

    class _NoopAdapter(AdapterProtocol):
        async def surface_gate(self, ctx: GateContext) -> None:
            pass

    local_reg = AdapterRegistry()
    local_reg.register("email", _NoopAdapter())

    orig = reg_module.registry
    dispatch_module.registry = local_reg
    try:
        await _real_surface_gate(conn, stage, actor_id)
    finally:
        dispatch_module.registry = orig
        reg_module.registry = orig


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_ambiguity_up_creates_gate_stage(conn) -> None:
    """PIPE-03: calling ambiguityUp creates a gate-type stage with state='blocked' in the DB."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]

    session_id = await _seed_work_session(conn, stage_id, actor_id)

    result = await _call_tool(
        conn, session_id, cascade_id, actor_id, reason="unclear requirement X"
    )

    # Extract gate_id from result string "gate:<uuid>"
    assert result.startswith("gate:"), f"Expected 'gate:<uuid>', got {result!r}"
    gate_id = result.removeprefix("gate:")

    row = await conn.fetchrow(
        "SELECT type, state, input FROM stage WHERE id = $1::uuid",
        gate_id,
    )
    assert row is not None, f"Gate stage {gate_id} not found in DB"
    assert row["type"] == "gate", f"Expected type='gate', got {row['type']!r}"
    assert row["state"] == "blocked", f"Expected state='blocked', got {row['state']!r}"

    input_data = row["input"]
    if isinstance(input_data, str):
        input_data = json.loads(input_data)
    assert input_data.get("gate_description") == "unclear requirement X", (
        f"gate_description mismatch: {input_data}"
    )


async def test_ambiguity_up_pauses_session(conn) -> None:
    """PIPE-03: after ambiguityUp, work_session.state is 'paused' for the calling session."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]

    session_id = await _seed_work_session(conn, stage_id, actor_id)

    await _call_tool(conn, session_id, cascade_id, actor_id, reason="blocked on scope")

    row = await conn.fetchrow(
        "SELECT state, paused_at FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row is not None
    assert row["state"] == "paused", f"Expected state='paused', got {row['state']!r}"
    assert row["paused_at"] is not None, "paused_at should be set"


async def test_ambiguity_up_surfaces_gate(conn) -> None:
    """PIPE-03: ambiguityUp writes a ledger_entry of type 'gate_surfaced' for the gate stage."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]

    session_id = await _seed_work_session(conn, stage_id, actor_id)

    result = await _call_tool(
        conn, session_id, cascade_id, actor_id, reason="need decision on auth approach"
    )
    gate_id = result.removeprefix("gate:")

    ledger_row = await conn.fetchrow(
        """
        SELECT type FROM ledger_entry
        WHERE stage_id = $1::uuid AND type = 'gate_surfaced'
        """,
        gate_id,
    )
    assert ledger_row is not None, (
        f"Expected ledger_entry of type 'gate_surfaced' for gate {gate_id}"
    )


async def test_ambiguity_up_returns_gate_id(conn) -> None:
    """PIPE-03: tool return value is 'gate:<uuid>' so the agent knows the gate ID."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]

    session_id = await _seed_work_session(conn, stage_id, actor_id)

    result = await _call_tool(
        conn, session_id, cascade_id, actor_id, reason="ambiguous constraint"
    )

    assert result.startswith("gate:"), f"Return value should start with 'gate:', got {result!r}"
    gate_id = result.removeprefix("gate:")

    # Verify gate_id is a valid UUID by checking DB
    row = await conn.fetchrow("SELECT id FROM stage WHERE id = $1::uuid AND type = 'gate'", gate_id)
    assert row is not None, f"Gate ID in return value {gate_id!r} not found in stage table"


async def test_ambiguity_up_no_snapshot_store(conn) -> None:
    """PIPE-03: snapshot_store=None pauses the session without crash (just UPDATE, no snapshot)."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]

    session_id = await _seed_work_session(conn, stage_id, actor_id)

    # This should not raise even though snapshot_store=None
    result = await _call_tool(
        conn, session_id, cascade_id, actor_id, reason="no store test"
    )
    assert result.startswith("gate:"), f"Expected 'gate:<uuid>', got {result!r}"

    row = await conn.fetchrow(
        "SELECT state FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    assert row["state"] == "paused", (
        f"Session should be paused even without snapshot store, got {row['state']!r}"
    )
