from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import asyncpg
import httpx
import pytest

REPO_ROOT = Path("/home/lynxnathan/code/eclusa")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from executor.propagation import inject_upstream_context
from executor.scc import create_scc_cascade
from executor.scc_handlers import _resolve_model

pytestmark = pytest.mark.asyncio

API_BASE = "http://localhost:8000"
JWT_SECRET = "eclusa-dev-secret-0123456789012345678901234"


def _json(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


async def _get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post("/api/auth/token", json={"secret": JWT_SECRET})
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _auth_headers() -> dict[str, str]:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        token = await _get_token(client)
    return {"Authorization": f"Bearer {token}"}


async def _seed_intent(conn: asyncpg.Connection, actor_id: str, raw: str) -> str:
    row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'api'::intent_source, $1, $2::uuid)
        RETURNING id::text
        """,
        raw,
        actor_id,
    )
    return str(row["id"])


async def _fetch_stage_by_scc_stage(
    conn: asyncpg.Connection, cascade_id: str, scc_stage: str
) -> dict:
    row = await conn.fetchrow(
        """
        SELECT id, cascade_id, type, state, depends_on, input, output
        FROM stage
        WHERE cascade_id = $1::uuid
          AND input->>'scc_stage' = $2
        """,
        cascade_id,
        scc_stage,
    )
    if row is None:
        raise AssertionError(f"stage not found for scc_stage={scc_stage!r}")
    return dict(row)


async def _set_stage_state_and_output(
    conn: asyncpg.Connection, stage_id: str, output: object
) -> dict:
    await conn.execute(
        """
        UPDATE stage
        SET state = 'resolved'::stage_state,
            output = $1::jsonb,
            resolved_at = NOW()
        WHERE id = $2::uuid
        """,
        json.dumps(output, default=str),
        stage_id,
    )
    row = await conn.fetchrow(
        """
        SELECT id, cascade_id, type, state, depends_on, input, output
        FROM stage
        WHERE id = $1::uuid
        """,
        stage_id,
    )
    return dict(row)


async def _cleanup_scc_cascade(conn: asyncpg.Connection, cascade_id: str) -> None:
    row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid", cascade_id
    )
    if row is None:
        return
    intent_id = str(row["intent_id"])

    stage_rows = await conn.fetch(
        "SELECT id FROM stage WHERE cascade_id = $1::uuid", cascade_id
    )
    stage_ids = [str(row["id"]) for row in stage_rows]

    await conn.execute(
        "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
    )
    try:
        async with conn.transaction():
            if stage_ids:
                await conn.execute(
                    "DELETE FROM work_session WHERE stage_ids && $1::uuid[]",
                    stage_ids,
                )
            await conn.execute(
                "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cascade_id
            )
            await conn.execute(
                "DELETE FROM stage WHERE cascade_id = $1::uuid", cascade_id
            )
            await conn.execute("DELETE FROM cascade WHERE id = $1::uuid", cascade_id)
            await conn.execute("DELETE FROM intent WHERE id = $1::uuid", intent_id)
    finally:
        await conn.execute(
            "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
        )


async def _seed_trace_chain(conn: asyncpg.Connection, actor_id: str) -> dict[str, str]:
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    await conn.execute(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES ($1::uuid, 'api'::intent_source, 'E2E trace endpoint test', $2::uuid)
        """,
        intent_id,
        actor_id,
    )
    await conn.execute(
        """
        INSERT INTO cascade (id, intent_id, shape, state)
        VALUES ($1::uuid, $2::uuid, '{"test":"trace_endpoint"}'::jsonb, 'active'::cascade_state)
        """,
        cascade_id,
        intent_id,
    )
    await conn.execute(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input, output)
        VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'resolved'::stage_state,
                '{}'::uuid[], '{"scc_stage":"refine"}'::jsonb,
                '{"scope_doc":"trace scope"}'::jsonb)
        """,
        stage_id,
        cascade_id,
    )
    await conn.execute(
        """
        INSERT INTO work_session (id, stage_ids, harness_type, model, state, message_history, cost)
        VALUES ($1::uuid, ARRAY[$2::uuid], 'native', 'test-model',
                'completed'::work_session_state, '[]'::jsonb, '{}'::jsonb)
        """,
        session_id,
        stage_id,
    )
    await conn.execute(
        """
        INSERT INTO artifact (id, intent_id, cascade_id, stage_id, session_id, type, payload)
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                'api_response'::artifact_type, '{"test":"trace_endpoint"}'::jsonb)
        """,
        artifact_id,
        intent_id,
        cascade_id,
        stage_id,
        session_id,
    )

    return {
        "artifact_id": artifact_id,
        "session_id": session_id,
        "stage_id": stage_id,
        "cascade_id": cascade_id,
        "intent_id": intent_id,
    }


async def _cleanup_trace_chain(
    conn: asyncpg.Connection,
    *,
    artifact_id: str,
    session_id: str,
    stage_id: str,
    cascade_id: str,
    intent_id: str,
) -> None:
    await conn.execute("DELETE FROM artifact WHERE id = $1::uuid", artifact_id)
    await conn.execute("DELETE FROM work_session WHERE id = $1::uuid", session_id)
    await conn.execute("DELETE FROM stage WHERE id = $1::uuid", stage_id)
    await conn.execute("DELETE FROM cascade WHERE id = $1::uuid", cascade_id)
    await conn.execute("DELETE FROM intent WHERE id = $1::uuid", intent_id)


async def test_resolve_model_uses_env_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCC_MODEL_DEFAULT", "openai:glm-5.2")
    monkeypatch.delenv("SCC_MODEL_REFINE", raising=False)

    assert _resolve_model("match") == "openai:glm-5.2"


async def test_resolve_model_per_stage_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCC_MODEL_DEFAULT", "openai:glm-5.2")
    monkeypatch.setenv("SCC_MODEL_REFINE", "anthropic:claude-3-5-haiku-latest")
    monkeypatch.delenv("SCC_MODEL_MATCH", raising=False)

    assert _resolve_model("refine") == "anthropic:claude-3-5-haiku-latest"
    assert _resolve_model("match") == "openai:glm-5.2"


async def test_resolve_model_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCC_MODEL_DEFAULT", raising=False)
    monkeypatch.delenv("SCC_MODEL_REFINE", raising=False)
    monkeypatch.delenv("SCC_MODEL_MATCH", raising=False)

    assert _resolve_model("refine") == "openai:glm-5.1"


async def test_inject_upstream_context_populates_stage_input(
    db_conn: asyncpg.Connection, seed_actor: str
) -> None:
    intent_id = await _seed_intent(db_conn, seed_actor, "propagation test")
    cascade_id = await create_scc_cascade(intent_id, seed_actor, db_conn)

    try:
        refine = await _fetch_stage_by_scc_stage(db_conn, cascade_id, "refine")
        match = await _fetch_stage_by_scc_stage(db_conn, cascade_id, "match")

        await _set_stage_state_and_output(
            db_conn,
            str(refine["id"]),
            {"scope_doc": "search for durable widgets"},
        )

        updated = await inject_upstream_context(db_conn, dict(match))

        assert updated["input"]["query_text"] == "search for durable widgets"

        row = await db_conn.fetchrow(
            "SELECT input FROM stage WHERE id = $1::uuid", match["id"]
        )
        assert _json(row["input"])["query_text"] == "search for durable widgets"
    finally:
        await _cleanup_scc_cascade(db_conn, cascade_id)


async def test_inject_upstream_no_deps_is_noop(db_conn: asyncpg.Connection) -> None:
    stage = {
        "id": str(uuid.uuid4()),
        "depends_on": [],
        "input": {"scc_stage": "cohere", "seed": True},
    }

    updated = await inject_upstream_context(db_conn, stage)

    assert updated["input"] == {"scc_stage": "cohere", "seed": True}


async def test_inject_upstream_accumulated_context(
    db_conn: asyncpg.Connection, seed_actor: str
) -> None:
    intent_id = await _seed_intent(db_conn, seed_actor, "accumulated context test")
    cascade_id = await create_scc_cascade(intent_id, seed_actor, db_conn)

    try:
        refine = await _fetch_stage_by_scc_stage(db_conn, cascade_id, "refine")
        fanout = await _fetch_stage_by_scc_stage(
            db_conn, cascade_id, "intent_validation_fanout"
        )
        match = await _fetch_stage_by_scc_stage(db_conn, cascade_id, "match")
        cohere = await _fetch_stage_by_scc_stage(db_conn, cascade_id, "cohere")

        await _set_stage_state_and_output(
            db_conn,
            str(refine["id"]),
            {"scope_doc": "evaluate source compatibility"},
        )
        await _set_stage_state_and_output(
            db_conn,
            str(match["id"]),
            [{"name": "API Source", "entity_id": "src-1"}],
        )

        await inject_upstream_context(db_conn, dict(fanout))
        updated = await inject_upstream_context(db_conn, dict(cohere))

        assert updated["input"]["query_text"] == "evaluate source compatibility"
        assert updated["input"]["matched_sources"] == [
            {"name": "API Source", "entity_id": "src-1"}
        ]
    finally:
        await _cleanup_scc_cascade(db_conn, cascade_id)


async def test_scc_create_api_happy(db_conn: asyncpg.Connection) -> None:
    headers = await _auth_headers()
    async with httpx.AsyncClient(base_url=API_BASE, timeout=20) as client:
        resp = await client.post(
            "/api/scc/create",
            headers=headers,
            json={"intent_text": "Create an SCC cascade for the new feature."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["cascade_id"]
        assert body["intent_id"]

        stage_count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM stage WHERE cascade_id = $1::uuid",
            body["cascade_id"],
        )
        assert stage_count == 7

        await _cleanup_scc_cascade(db_conn, body["cascade_id"])


async def test_scc_create_api_empty_intent() -> None:
    headers = await _auth_headers()
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        resp = await client.post(
            "/api/scc/create",
            headers=headers,
            json={"intent_text": "   "},
        )
        assert resp.status_code == 422


async def test_chat_build_mode_creates_scc(db_conn: asyncpg.Connection) -> None:
    headers = await _auth_headers()
    async with httpx.AsyncClient(base_url=API_BASE, timeout=20) as client:
        resp = await client.post(
            "/api/chat",
            headers=headers,
            json={
                "messages": [
                    {"role": "user", "content": "Create a build cascade."}
                ],
                "mode": "build",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        body = resp.json()
        assert body["mode"] == "build"
        assert body["cascade_id"]

        stage_count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM stage WHERE cascade_id = $1::uuid",
            body["cascade_id"],
        )
        assert stage_count == 7

        await _cleanup_scc_cascade(db_conn, body["cascade_id"])


async def test_chat_default_mode_streams() -> None:
    headers = await _auth_headers()
    async with httpx.AsyncClient(base_url=API_BASE, timeout=20) as client:
        async with client.stream(
            "POST",
            "/api/chat",
            headers=headers,
            json={"messages": [{"role": "user", "content": "Stream this."}]},
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")


async def test_cascade_stages_endpoint(
    db_conn: asyncpg.Connection, seed_actor: str
) -> None:
    headers = await _auth_headers()
    intent_id = await _seed_intent(db_conn, seed_actor, "cascade stages endpoint")
    cascade_id = await create_scc_cascade(intent_id, seed_actor, db_conn)

    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=20) as client:
            resp = await client.get(
                f"/api/cascades/{cascade_id}/stages",
                headers=headers,
            )
            assert resp.status_code == 200
            stages = resp.json()
            assert len(stages) == 7
            assert {stage["scc_stage"] for stage in stages} == {
                "refine",
                "intent_validation_fanout",
                "match",
                "cohere",
                "formalize",
                "derive",
                "generate",
            }
            display_names = {s["display_name"] for s in stages}
            assert "Refine" in display_names
    finally:
        await _cleanup_scc_cascade(db_conn, cascade_id)


async def test_cascade_stages_404() -> None:
    headers = await _auth_headers()
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        resp = await client.get(
            "/api/cascades/00000000-0000-0000-0000-000000000000/stages",
            headers=headers,
        )
        assert resp.status_code == 404


async def test_stage_output_endpoint(
    db_conn: asyncpg.Connection, seed_actor: str
) -> None:
    headers = await _auth_headers()
    intent_id = await _seed_intent(db_conn, seed_actor, "stage output endpoint")
    cascade_id = await create_scc_cascade(intent_id, seed_actor, db_conn)

    try:
        stage = await _fetch_stage_by_scc_stage(db_conn, cascade_id, "refine")
        await _set_stage_state_and_output(
            db_conn,
            str(stage["id"]),
            {"scope_doc": "traceable output payload"},
        )

        async with httpx.AsyncClient(base_url=API_BASE, timeout=20) as client:
            resp = await client.get(
                f"/api/cascades/{cascade_id}/stages/{stage['id']}/output",
                headers=headers,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["stage_id"] == str(stage["id"])
            assert body["scc_stage"] == "refine"
            assert body["state"] == "resolved"
            assert body["output"]["scope_doc"] == "traceable output payload"
    finally:
        await _cleanup_scc_cascade(db_conn, cascade_id)


async def test_trace_endpoint(db_conn: asyncpg.Connection, seed_actor: str) -> None:
    headers = await _auth_headers()
    seeded = await _seed_trace_chain(db_conn, seed_actor)

    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=20) as client:
            resp = await client.get(
                f"/api/trace/{seeded['artifact_id']}",
                headers=headers,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["artifact_id"] == seeded["artifact_id"]
            assert [hop["type"] for hop in body["hops"]] == [
                "artifact",
                "session",
                "stage",
                "cascade",
                "intent",
            ]
            assert body["hops"][2]["id"] == seeded["stage_id"]
            assert body["hops"][3]["id"] == seeded["cascade_id"]
            assert body["hops"][4]["id"] == seeded["intent_id"]
    finally:
        await _cleanup_trace_chain(db_conn, **seeded)
