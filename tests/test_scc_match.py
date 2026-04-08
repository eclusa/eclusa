"""Tests for SCC match routing and handler behavior."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from executor.dispatch import dispatch_narrowing
from executor.scc_handlers import dispatch_scc_match
from knowledge.search import SearchResult
from tests.helpers.topology import seed_linear_cascade

pytestmark = pytest.mark.asyncio


async def test_dispatch_scc_match_calls_search_and_writes_output(conn):
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][0]
    cascade_id = topo["cascade_id"]

    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": {"scc_stage": "match", "query_text": "auth model"},
    }

    search_result = SearchResult(
        entity_id="11111111-1111-1111-1111-111111111111",
        name="Auth Model",
        type="concept",
        summary="Authentication boundary",
        rrf_score=1.0,
        cosine_score=0.9,
        bm25_score=0.8,
        bfs_score=0.2,
    )

    with (
        patch(
            "executor.scc_handlers.embed_texts",
            new=AsyncMock(return_value=[[0.1] * 1024]),
        ) as mock_embed,
        patch(
            "executor.scc_handlers.search_schema_commons",
            new=AsyncMock(return_value=[search_result]),
        ) as mock_search,
    ):
        await dispatch_scc_match(conn, stage_row, actor_id)

    mock_embed.assert_awaited_once()
    mock_search.assert_awaited_once()
    called_query_text = mock_search.await_args.args[0]
    assert called_query_text == "auth model"

    row = await conn.fetchrow(
        "SELECT state, output FROM stage WHERE id = $1::uuid", stage_id
    )
    assert row["state"] == "resolved"
    output = row["output"]
    if isinstance(output, str):
        output = json.loads(output)
    assert isinstance(output, list)
    assert output[0]["name"] == "Auth Model"


async def test_dispatch_narrowing_routes_match_stage(conn):
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
        "input": {"scc_stage": "match", "query_text": "authorization"},
    }

    mock_match = AsyncMock()
    with patch("executor.dispatch.dispatch_scc_match", new=mock_match):
        await dispatch_narrowing(conn, stage_row, actor_id)

    mock_match.assert_awaited_once()
    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", stage_id)
    assert row["state"] == "active"


async def test_dispatch_scc_match_resolves_stage(conn):
    topo = await seed_linear_cascade(conn)
    actor_id = topo["actor_id"]
    stage_id = topo["stage_ids"][1]
    cascade_id = topo["cascade_id"]

    stage_row = {
        "id": stage_id,
        "type": "narrowing",
        "cascade_id": cascade_id,
        "input": {"scc_stage": "match", "query_text": "data store"},
    }

    with (
        patch(
            "executor.scc_handlers.embed_texts",
            new=AsyncMock(return_value=[[0.2] * 1024]),
        ),
        patch(
            "executor.scc_handlers.search_schema_commons",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await dispatch_scc_match(conn, stage_row, actor_id)

    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", stage_id)
    assert row["state"] == "resolved"
