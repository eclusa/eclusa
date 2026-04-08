"""Tests for SCC derive stage behavior."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from executor.scc import create_scc_cascade
from executor.scc_handlers import dispatch_scc_derive
from tests.helpers.topology import seed_system_actor

pytestmark = pytest.mark.asyncio


async def _seed_derive_stage(conn):
    actor_id = await seed_system_actor(conn)
    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'derive stage test intent', $1::uuid)
        RETURNING id
        """,
        actor_id,
    )
    intent_id = str(intent_row["id"])
    cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

    stage_row = await conn.fetchrow(
        """
        SELECT id
        FROM stage
        WHERE cascade_id = $1::uuid AND input->>'scc_stage' = 'derive'
        LIMIT 1
        """,
        cascade_id,
    )
    stage_id = str(stage_row["id"])
    await conn.execute(
        """
        UPDATE stage
        SET input = $1::jsonb
        WHERE id = $2::uuid
        """,
        json.dumps(
            {
                "scc_stage": "derive",
                "formalize_output": {"haskell_source": "module Demo where\n"},
                "cohere_output": {"decision": "approve"},
                "matched_sources": [{"name": "API Source", "entity_id": "src-1"}],
            }
        ),
        stage_id,
    )

    return actor_id, cascade_id, stage_id


async def test_dispatch_scc_derive_starts_work_session_and_writes_test_suite(conn):
    actor_id, cascade_id, stage_id = await _seed_derive_stage(conn)
    stage_row = await conn.fetchrow(
        "SELECT id, cascade_id, input FROM stage WHERE id = $1::uuid",
        stage_id,
    )

    with (
        patch("executor.scc_handlers.Agent") as mock_agent,
        patch(
            "executor.scc_handlers.start_work_session",
            new=AsyncMock(return_value="session-derive-1"),
        ) as mock_start,
        patch(
            "executor.scc_handlers.run_session_turn",
            new=AsyncMock(
                return_value=("def test_generated():\n    assert True\n", [])
            ),
        ) as mock_turn,
        patch(
            "executor.scc_handlers.complete_work_session", new=AsyncMock()
        ) as mock_complete,
    ):
        await dispatch_scc_derive(conn, dict(stage_row), actor_id)

    mock_start.assert_awaited_once()
    assert mock_start.await_args.kwargs["model"] == "anthropic:claude-3-5-haiku-latest"
    mock_complete.assert_awaited_once()
    mock_agent.assert_called_once()
    assert mock_agent.call_args.args[0] == "anthropic:claude-3-5-haiku-latest"
    assert "test specification expert" in mock_agent.call_args.kwargs["system_prompt"]

    user_message = mock_turn.await_args.kwargs["user_message"]
    assert "module Demo where" in user_message
    assert "API Source" in user_message

    output_row = await conn.fetchrow(
        "SELECT state, output FROM stage WHERE id = $1::uuid",
        stage_id,
    )
    assert output_row["state"] == "resolved"
    output = output_row["output"]
    if isinstance(output, str):
        output = json.loads(output)
    assert output["test_suite"] == "def test_generated():\n    assert True\n"
    assert output["session_id"] == "session-derive-1"
