from __future__ import annotations

import json

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from adapters.web.app import create_app

pytestmark = pytest.mark.asyncio


def _dsn(pg_container) -> str:
    url = pg_container.get_connection_url()
    if "postgresql+psycopg2://" in url:
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    elif "postgresql+asyncpg://" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def _seed_actor(conn: asyncpg.Connection, identity: str = "chat-api-test") -> str:
    row = await conn.fetchrow(
        """
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', $1)
        RETURNING id::text
        """,
        identity,
    )
    return row["id"]


async def _get_token(client: AsyncClient, secret: str) -> str:
    resp = await client.post("/api/auth/token", json={"secret": secret})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_chat_endpoint_creates_and_reuses_session(
    conn: asyncpg.Connection, pg_container, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "chat-secret-for-eclusa-backoffice-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)

    app = create_app()
    pool = await asyncpg.create_pool(_dsn(pg_container), min_size=1, max_size=5)
    app.state.pool = pool
    app.state._owns_pool = False

    monkeypatch.setattr(
        "adapters.web.api.chat.build_chat_agent",
        lambda model: Agent(TestModel()),
    )

    try:
        actor_id = await _seed_actor(conn)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _get_token(client, secret)

            first = await client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "messages": [
                        {"role": "user", "content": "Create a quick chat cascade."}
                    ],
                    "model": "anthropic:claude-3-5-haiku-latest",
                },
            )
            assert first.status_code == 200
            assert first.headers["content-type"].startswith("text/event-stream")
            session_id = first.headers["x-eclusa-session-id"]
            assert session_id

            first_lines = [line for line in first.text.splitlines() if line]
            assert first_lines[0].startswith("0:")
            assert first_lines[-1].startswith("d:")
            finish_payload = json.loads(first_lines[-1][2:])
            assert finish_payload["finishReason"] == "stop"
            assert finish_payload["sessionId"] == session_id

            session_row = await conn.fetchrow(
                """
                SELECT
                    ws.id::text AS session_id,
                    ws.harness_type,
                    ws.model,
                    ws.stage_ids[1]::text AS stage_id,
                    s.cascade_id::text AS cascade_id,
                    i.id::text AS intent_id,
                    i.source,
                    i.raw
                FROM work_session ws
                JOIN stage s ON s.id = ws.stage_ids[1]
                JOIN cascade c ON c.id = s.cascade_id
                JOIN intent i ON i.id = c.intent_id
                WHERE ws.id = $1::uuid
                """,
                session_id,
            )
            assert session_row is not None
            assert session_row["harness_type"] == "chat"
            assert session_row["model"] == "anthropic:claude-3-5-haiku-latest"
            assert session_row["source"] == "chat"
            assert "quick chat cascade" in session_row["raw"]

            stage_count = await conn.fetchval(
                "SELECT COUNT(*) FROM stage WHERE cascade_id = $1::uuid",
                session_row["cascade_id"],
            )
            assert stage_count == 1

            second = await client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "session_id": session_id,
                    "messages": [
                        {"role": "user", "content": "Follow up on that chat."}
                    ],
                },
            )
            assert second.status_code == 200
            assert second.headers["x-eclusa-session-id"] == session_id
            second_lines = [line for line in second.text.splitlines() if line]
            assert second_lines[0].startswith("0:")
            assert second_lines[-1].startswith("d:")

            session_count = await conn.fetchval(
                "SELECT COUNT(*) FROM work_session WHERE id = $1::uuid",
                session_id,
            )
            assert session_count == 1

            intent_count = await conn.fetchval(
                "SELECT COUNT(*) FROM intent WHERE created_by = $1::uuid AND source = 'chat'",
                actor_id,
            )
            assert intent_count == 1
    finally:
        await pool.close()
