"""Tests for SCC intent-validation fan-out behavior."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from executor.scc import create_scc_cascade
from executor.scc_handlers import dispatch_scc_fanout
from judgment.pass_ import VerdictModel, hash_context
from tests.helpers.topology import seed_system_actor

pytestmark = pytest.mark.asyncio


APPROVE_VERDICT = VerdictModel(
    decision="approve",
    confidence=0.95,
    rationale="matches",
    conditions=[],
)

REJECT_VERDICT = VerdictModel(
    decision="reject",
    confidence=0.2,
    rationale="diverges",
    conditions=["missing requirement"],
)


async def _seed_fanout_stage(conn, raw_intent: str = "fanout stage test intent"):
    actor_id = await seed_system_actor(conn)
    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', $1, $2::uuid)
        RETURNING id
        """,
        raw_intent,
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
        SET output = $1::jsonb
        WHERE id = $2::uuid
        """,
        json.dumps({"scope_doc": "refined scope document"}),
        by_stage["refine"],
    )

    return actor_id, cascade_id, by_stage


async def test_dispatch_scc_fanout_calls_run_fan_out_with_db_and_uses_raw_intent_fallback(
    conn,
):
    actor_id, cascade_id, by_stage = await _seed_fanout_stage(conn)
    stage_row = await conn.fetchrow(
        "SELECT id, cascade_id, input FROM stage WHERE id = $1::uuid",
        by_stage["intent_validation_fanout"],
    )

    with patch(
        "executor.scc_handlers.run_fan_out_with_db",
        new=AsyncMock(return_value="fanout-1"),
    ) as mock_fanout:
        await dispatch_scc_fanout(conn, dict(stage_row), actor_id)

    mock_fanout.assert_awaited_once()
    kwargs = mock_fanout.await_args.kwargs
    assert kwargs["stage_id"] == by_stage["intent_validation_fanout"]
    assert kwargs["models"] == ["anthropic:claude-3-5-haiku-latest"]
    assert kwargs["prompt"] == (
        "Does the refined scope doc faithfully represent the original intent? "
        "List any missed requirements."
    )
    assert "fanout stage test intent" in kwargs["prepared_context"]
    assert "refined scope document" in kwargs["prepared_context"]
    assert kwargs["context_hash"] == hash_context(kwargs["prepared_context"])


async def test_dispatch_scc_fanout_resolves_stage_when_verdicts_converge(conn):
    actor_id, cascade_id, by_stage = await _seed_fanout_stage(conn)
    await conn.execute(
        """
        UPDATE stage
        SET input = $1::jsonb
        WHERE id = $2::uuid
        """,
        json.dumps(
            {
                "scc_stage": "intent_validation_fanout",
                "refine_stage_id": by_stage["refine"],
                "fanout_models": ["model-a", "model-b"],
            }
        ),
        by_stage["intent_validation_fanout"],
    )
    stage_row = await conn.fetchrow(
        "SELECT id, cascade_id, input FROM stage WHERE id = $1::uuid",
        by_stage["intent_validation_fanout"],
    )

    async def _same_verdict(*_args, **_kwargs):
        return APPROVE_VERDICT

    with patch(
        "fan_out.dispatcher.run_judgment_pass", new=AsyncMock(side_effect=_same_verdict)
    ):
        await dispatch_scc_fanout(conn, dict(stage_row), actor_id)

    row = await conn.fetchrow(
        "SELECT state FROM stage WHERE id = $1::uuid",
        by_stage["intent_validation_fanout"],
    )
    assert row["state"] == "resolved"


async def test_dispatch_scc_fanout_blocks_stage_when_verdicts_diverge(conn):
    actor_id, cascade_id, by_stage = await _seed_fanout_stage(conn)
    await conn.execute(
        """
        UPDATE stage
        SET input = $1::jsonb
        WHERE id = $2::uuid
        """,
        json.dumps(
            {
                "scc_stage": "intent_validation_fanout",
                "refine_stage_id": by_stage["refine"],
                "fanout_models": ["model-a", "model-b"],
            }
        ),
        by_stage["intent_validation_fanout"],
    )
    stage_row = await conn.fetchrow(
        "SELECT id, cascade_id, input FROM stage WHERE id = $1::uuid",
        by_stage["intent_validation_fanout"],
    )

    async def _diverge(model, prepared_context, prompt):
        if model == "model-a":
            return APPROVE_VERDICT
        return REJECT_VERDICT

    with patch(
        "fan_out.dispatcher.run_judgment_pass", new=AsyncMock(side_effect=_diverge)
    ):
        await dispatch_scc_fanout(conn, dict(stage_row), actor_id)

    row = await conn.fetchrow(
        "SELECT state FROM stage WHERE id = $1::uuid",
        by_stage["intent_validation_fanout"],
    )
    assert row["state"] == "blocked"


async def test_fanout_uses_scope_doc_directly(conn):
    """v2 build-mode path: scope_doc present in stage input, no refine_stage_id.

    The handler must use scope_doc directly without any DB lookup for refine stage output.
    """
    actor_id = await seed_system_actor(conn)
    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', $1, $2::uuid)
        RETURNING id
        """,
        "v2 direct scope doc test intent",
        actor_id,
    )
    intent_id = str(intent_row["id"])
    cascade_id = str(
        (
            await conn.fetchrow(
                """
                INSERT INTO cascade (id, intent_id, shape, state)
                VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
                RETURNING id
                """,
                intent_id,
            )
        )["id"]
    )

    # Seed a fanout stage with scope_doc directly in input — no refine_stage_id
    stage_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}', $2::jsonb)
        RETURNING id, cascade_id, input
        """,
        cascade_id,
        json.dumps(
            {
                "scc_stage": "intent_validation_fanout",
                "scope_doc": "direct scope document from refine conversation",
                "raw_intent": "v2 direct scope doc test intent",
            }
        ),
    )

    with patch(
        "executor.scc_handlers.run_fan_out_with_db",
        new=AsyncMock(return_value="fanout-v2"),
    ) as mock_fanout:
        await dispatch_scc_fanout(conn, dict(stage_row), actor_id)

    mock_fanout.assert_awaited_once()
    kwargs = mock_fanout.await_args.kwargs
    assert "direct scope document from refine conversation" in kwargs["prepared_context"]
    assert kwargs["context_hash"] == hash_context(kwargs["prepared_context"])


async def test_fanout_missing_both_inputs_returns_early(conn):
    """Stage with neither scope_doc nor refine_stage_id must return early without calling run_fan_out_with_db."""
    actor_id = await seed_system_actor(conn)
    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', $1, $2::uuid)
        RETURNING id
        """,
        "missing inputs test intent",
        actor_id,
    )
    intent_id = str(intent_row["id"])
    cascade_id = str(
        (
            await conn.fetchrow(
                """
                INSERT INTO cascade (id, intent_id, shape, state)
                VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
                RETURNING id
                """,
                intent_id,
            )
        )["id"]
    )

    # Stage with only scc_stage key — no scope_doc, no refine_stage_id
    stage_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}', $2::jsonb)
        RETURNING id, cascade_id, input
        """,
        cascade_id,
        json.dumps({"scc_stage": "intent_validation_fanout"}),
    )

    with patch(
        "executor.scc_handlers.run_fan_out_with_db",
        new=AsyncMock(return_value="should-not-be-called"),
    ) as mock_fanout:
        await dispatch_scc_fanout(conn, dict(stage_row), actor_id)

    mock_fanout.assert_not_awaited()
