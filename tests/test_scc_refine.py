"""Tests for SCC refine routing and handler behavior."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from executor.dispatch import dispatch_narrowing
from executor.scc_handlers import dispatch_scc_refine
from harness.native import complete_work_session, start_work_session
from tests.helpers.topology import seed_linear_cascade

pytestmark = pytest.mark.asyncio


async def test_dispatch_scc_refine_calls_work_session_lifecycle(conn):
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]

    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": {"scc_stage": "refine", "raw_intent": "Build a retrieval workflow"},
    }

    with (
        patch(
            "executor.scc_handlers.Agent",
            side_effect=lambda *args, **kwargs: Agent(
                TestModel(custom_output_text="scope doc text")
            ),
        ),
        patch(
            "executor.scc_handlers.start_work_session", wraps=start_work_session
        ) as mock_start,
        patch(
            "executor.scc_handlers.complete_work_session", wraps=complete_work_session
        ) as mock_complete,
    ):
        await dispatch_scc_refine(conn, stage_row, actor_id)

    assert mock_start.await_count == 1
    assert mock_complete.await_count == 1

    session_row = await conn.fetchrow(
        "SELECT state, model FROM work_session WHERE stage_ids[1] = $1::uuid",
        stage_id,
    )
    assert session_row["state"] == "completed"
    assert session_row["model"] == "anthropic:claude-3-5-haiku-latest"

    stage_db_row = await conn.fetchrow(
        "SELECT state, output FROM stage WHERE id = $1::uuid",
        stage_id,
    )
    assert stage_db_row["state"] == "resolved"
    output = stage_db_row["output"]
    if isinstance(output, str):
        output = json.loads(output)
    assert "scope_doc" in output
    assert output["scope_doc"] == "scope doc text"


async def test_dispatch_narrowing_routes_refine_stage(conn):
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]

    await conn.execute(
        "UPDATE stage SET state = 'active' WHERE id = $1::uuid", stage_id
    )
    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": {"scc_stage": "refine"},
    }

    mock_refine = AsyncMock()
    with patch("executor.dispatch.dispatch_scc_refine", new=mock_refine):
        await dispatch_narrowing(conn, stage_row, actor_id)

    mock_refine.assert_awaited_once()
    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", stage_id)
    assert row["state"] == "active"


async def test_dispatch_narrowing_legacy_stage_resolves_immediately(conn):
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][1]
    cascade_id = topo["cascade_id"]

    await conn.execute(
        "UPDATE stage SET state = 'active' WHERE id = $1::uuid", stage_id
    )
    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": {},
    }

    await dispatch_narrowing(conn, stage_row, actor_id)

    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", stage_id)
    assert row["state"] == "resolved"

    ledger_row = await conn.fetchrow(
        "SELECT type, schema_version FROM ledger_entry WHERE stage_id = $1::uuid AND type = 'stage_state_changed'",
        stage_id,
    )
    assert ledger_row is not None
    assert ledger_row["schema_version"] == "0002"


async def test_dispatch_scc_refine_writes_scope_doc_payload(conn):
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]

    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": {
            "scc_stage": "refine",
            "raw_intent": "Create a customer support triage flow",
        },
    }

    with patch(
        "executor.scc_handlers.Agent",
        side_effect=lambda *args, **kwargs: Agent(
            TestModel(custom_output_text="structured scope")
        ),
    ):
        await dispatch_scc_refine(conn, stage_row, actor_id)

    output = await conn.fetchval(
        "SELECT output FROM stage WHERE id = $1::uuid", stage_id
    )
    if isinstance(output, str):
        output = json.loads(output)
    assert output["scope_doc"] == "structured scope"
    assert output["session_id"]
