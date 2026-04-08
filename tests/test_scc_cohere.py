"""Tests for SCC cohere routing and handler behavior."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from executor.dispatch import dispatch_narrowing
from executor.scc_handlers import dispatch_scc_cohere
from judgment.pass_ import VerdictModel, create_judgment_pass_record
from tests.helpers.topology import seed_linear_cascade

pytestmark = pytest.mark.asyncio


async def test_dispatch_scc_cohere_calls_judgment_and_writes_output(conn):
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]

    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": {
            "scc_stage": "cohere",
            "matched_sources": [{"entity_id": "1", "name": "Auth Model"}],
        },
    }

    verdict = VerdictModel(
        decision="needs_clarification",
        confidence=0.7,
        rationale="The sources overlap but do not align on ownership.",
        conditions=["Clarify auth boundaries"],
    )

    with (
        patch(
            "executor.scc_handlers.run_judgment_pass",
            new=AsyncMock(return_value=verdict),
        ) as mock_pass,
        patch(
            "executor.scc_handlers.create_judgment_pass_record",
            wraps=create_judgment_pass_record,
        ) as mock_record,
    ):
        await dispatch_scc_cohere(conn, stage_row, actor_id)

    mock_pass.assert_awaited_once()
    mock_record.assert_awaited_once()

    row = await conn.fetchrow(
        "SELECT state, output FROM stage WHERE id = $1::uuid", stage_id
    )
    assert row["state"] == "resolved"
    output = row["output"]
    if isinstance(output, str):
        output = json.loads(output)
    assert output["decision"] == "needs_clarification"
    assert output["conditions"] == ["Clarify auth boundaries"]


async def test_dispatch_narrowing_routes_cohere_stage(conn):
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
        "input": {"scc_stage": "cohere", "matched_sources": []},
    }

    mock_cohere = AsyncMock()
    with patch("executor.dispatch.dispatch_scc_cohere", new=mock_cohere):
        await dispatch_narrowing(conn, stage_row, actor_id)

    mock_cohere.assert_awaited_once()
    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", stage_id)
    assert row["state"] == "active"


async def test_dispatch_scc_cohere_resolves_stage(conn):
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][1]
    cascade_id = topo["cascade_id"]

    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": {
            "scc_stage": "cohere",
            "matched_sources": [{"entity_id": "2", "name": "Storage Layer"}],
        },
    }

    verdict = VerdictModel(
        decision="approve",
        confidence=0.95,
        rationale="The sources compose cleanly.",
        conditions=[],
    )

    with (
        patch(
            "executor.scc_handlers.run_judgment_pass",
            new=AsyncMock(return_value=verdict),
        ),
        patch(
            "executor.scc_handlers.create_judgment_pass_record",
            wraps=create_judgment_pass_record,
        ),
    ):
        await dispatch_scc_cohere(conn, stage_row, actor_id)

    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", stage_id)
    assert row["state"] == "resolved"
