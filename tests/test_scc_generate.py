"""Tests for SCC generate stage behavior."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from executor.scc import create_scc_cascade
from executor.scc_handlers import dispatch_scc_derive, dispatch_scc_generate
from tests.helpers.topology import seed_system_actor

pytestmark = pytest.mark.asyncio


async def _seed_generate_stages(conn):
    actor_id = await seed_system_actor(conn)
    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'generate stage test intent', $1::uuid)
        RETURNING id
        """,
        actor_id,
    )
    intent_id = str(intent_row["id"])
    cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

    rows = await conn.fetch(
        """
        SELECT id, input
        FROM stage
        WHERE cascade_id = $1::uuid
        """,
        cascade_id,
    )
    by_stage = {json.loads(row["input"])["scc_stage"]: str(row["id"]) for row in rows}

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
        by_stage["derive"],
    )

    return actor_id, cascade_id, by_stage


async def test_dispatch_scc_generate_uses_derived_tests_and_cheapest_model(conn):
    actor_id, cascade_id, by_stage = await _seed_generate_stages(conn)

    derive_stage = {
        "id": by_stage["derive"],
        "cascade_id": cascade_id,
        "input": {
            "scc_stage": "derive",
            "formalize_output": {"haskell_source": "module Demo where\n"},
            "cohere_output": {"decision": "approve"},
            "matched_sources": [{"name": "API Source", "entity_id": "src-1"}],
        },
    }

    with (
        patch("executor.scc_handlers.Agent") as mock_agent,
        patch(
            "executor.scc_handlers.start_work_session",
            new=AsyncMock(return_value="session-derive-2"),
        ) as mock_start,
        patch(
            "executor.scc_handlers.run_session_turn",
            new=AsyncMock(
                return_value=("def test_generated():\n    assert True\n", [])
            ),
        ),
        patch("executor.scc_handlers.complete_work_session", new=AsyncMock()),
    ):
        await dispatch_scc_derive(conn, derive_stage, actor_id)

    derive_output = await conn.fetchval(
        "SELECT output FROM stage WHERE id = $1::uuid",
        by_stage["derive"],
    )
    if isinstance(derive_output, str):
        derive_output = json.loads(derive_output)

    generate_stage_id = by_stage["generate"]
    await conn.execute(
        """
        UPDATE stage
        SET input = $1::jsonb
        WHERE id = $2::uuid
        """,
        json.dumps(
            {
                "scc_stage": "generate",
                "test_suite": derive_output["test_suite"],
                "haskell_source": "module Demo where\n",
                "matched_sources": [{"name": "API Source", "entity_id": "src-1"}],
            }
        ),
        generate_stage_id,
    )

    generate_stage_row = await conn.fetchrow(
        "SELECT id, cascade_id, input FROM stage WHERE id = $1::uuid",
        generate_stage_id,
    )

    with (
        patch("executor.scc_handlers.Agent") as mock_agent,
        patch(
            "executor.scc_handlers.start_work_session",
            new=AsyncMock(return_value="session-generate-1"),
        ) as mock_start,
        patch(
            "executor.scc_handlers.run_session_turn",
            new=AsyncMock(return_value=("generated code block", [])),
        ) as mock_turn,
        patch(
            "executor.scc_handlers.complete_work_session", new=AsyncMock()
        ) as mock_complete,
    ):
        await dispatch_scc_generate(conn, dict(generate_stage_row), actor_id)

    mock_start.assert_awaited_once()
    assert mock_start.await_args.kwargs["model"] == "anthropic:claude-3-5-haiku-latest"
    mock_complete.assert_awaited_once()
    mock_agent.assert_called_once()
    assert "code generator" in mock_agent.call_args.kwargs["system_prompt"]

    user_message = mock_turn.await_args.kwargs["user_message"]
    assert derive_output["test_suite"] in user_message
    assert "module Demo where" in user_message

    output_row = await conn.fetchrow(
        "SELECT state, output FROM stage WHERE id = $1::uuid",
        generate_stage_id,
    )
    assert output_row["state"] == "resolved"
    output = output_row["output"]
    if isinstance(output, str):
        output = json.loads(output)
    assert output["generated_code"] == "generated code block"
    assert output["session_id"] == "session-generate-1"
