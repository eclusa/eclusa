"""Tests for the SCC cascade template."""

from __future__ import annotations

import json

import pytest

from tests.helpers.topology import seed_system_actor

pytestmark = pytest.mark.asyncio


async def _seed_intent(conn, actor_id: str) -> str:
    row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'test intent scc template', $1::uuid)
        RETURNING id
    """,
        actor_id,
    )
    return str(row["id"])


def _normalize_json(value):
    return json.loads(value) if isinstance(value, str) else value


async def test_create_scc_cascade_returns_cascade_id(conn):
    from executor.scc import create_scc_cascade

    actor_id = await seed_system_actor(conn)
    intent_id = await _seed_intent(conn, actor_id)

    cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

    assert isinstance(cascade_id, str)
    assert len(cascade_id) > 0


async def test_create_scc_cascade_inserts_seven_stages(conn):
    from executor.scc import create_scc_cascade

    actor_id = await seed_system_actor(conn)
    intent_id = await _seed_intent(conn, actor_id)

    cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

    stage_count = await conn.fetchval(
        "SELECT COUNT(*) FROM stage WHERE cascade_id = $1::uuid",
        cascade_id,
    )
    assert stage_count == 7


async def test_create_scc_cascade_stage_inputs_are_expected(conn):
    from executor.scc import create_scc_cascade

    actor_id = await seed_system_actor(conn)
    intent_id = await _seed_intent(conn, actor_id)

    cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

    rows = await conn.fetch(
        """
        SELECT id, depends_on, input
        FROM stage
        WHERE cascade_id = $1::uuid
        ORDER BY created_at ASC, id ASC
    """,
        cascade_id,
    )

    scc_stages = [_normalize_json(row["input"])["scc_stage"] for row in rows]
    assert set(scc_stages) == {
        "refine",
        "intent_validation_fanout",
        "match",
        "cohere",
        "formalize",
        "derive",
        "generate",
    }
    assert len(scc_stages) == 7


async def test_create_scc_cascade_dependency_chain(conn):
    from executor.scc import create_scc_cascade

    actor_id = await seed_system_actor(conn)
    intent_id = await _seed_intent(conn, actor_id)

    cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

    rows = await conn.fetch(
        """
        SELECT id, depends_on, input
        FROM stage
        WHERE cascade_id = $1::uuid
        ORDER BY created_at ASC, id ASC
    """,
        cascade_id,
    )

    by_stage = {_normalize_json(row["input"])["scc_stage"]: row for row in rows}

    assert [str(dep) for dep in by_stage["refine"]["depends_on"]] == []
    assert [str(dep) for dep in by_stage["intent_validation_fanout"]["depends_on"]] == [
        str(by_stage["refine"]["id"])
    ]
    assert [str(dep) for dep in by_stage["match"]["depends_on"]] == [
        str(by_stage["intent_validation_fanout"]["id"])
    ]
    assert [str(dep) for dep in by_stage["cohere"]["depends_on"]] == [
        str(by_stage["match"]["id"])
    ]
    assert [str(dep) for dep in by_stage["formalize"]["depends_on"]] == [
        str(by_stage["cohere"]["id"])
    ]
    assert [str(dep) for dep in by_stage["derive"]["depends_on"]] == [
        str(by_stage["formalize"]["id"])
    ]
    assert [str(dep) for dep in by_stage["generate"]["depends_on"]] == [
        str(by_stage["derive"]["id"])
    ]


async def test_create_scc_cascade_fanout_includes_refine_stage_id(conn):
    from executor.scc import create_scc_cascade

    actor_id = await seed_system_actor(conn)
    intent_id = await _seed_intent(conn, actor_id)

    cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

    rows = await conn.fetch(
        """
        SELECT id, input
        FROM stage
        WHERE cascade_id = $1::uuid
        ORDER BY created_at ASC, id ASC
    """,
        cascade_id,
    )

    by_stage = {_normalize_json(row["input"])["scc_stage"]: row for row in rows}
    refine_id = str(by_stage["refine"]["id"])
    fanout_input = _normalize_json(by_stage["intent_validation_fanout"]["input"])
    assert fanout_input["scc_stage"] == "intent_validation_fanout"
    assert fanout_input["refine_stage_id"] == refine_id


async def test_create_scc_cascade_stages_are_pending_narrowing(conn):
    from executor.scc import create_scc_cascade

    actor_id = await seed_system_actor(conn)
    intent_id = await _seed_intent(conn, actor_id)

    cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

    rows = await conn.fetch(
        """
        SELECT state, type
        FROM stage
        WHERE cascade_id = $1::uuid
    """,
        cascade_id,
    )

    assert len(rows) == 7
    assert {row["state"] for row in rows} == {"pending"}
    assert {row["type"] for row in rows} == {"narrowing"}
