from __future__ import annotations

import json
from datetime import datetime, timezone

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from adapters.web.app import create_app

pytestmark = pytest.mark.asyncio


def _dsn(pg_container) -> str:
    url = pg_container.get_connection_url()
    if "postgresql+psycopg2://" in url:
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    elif "postgresql+asyncpg://" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def _seed_actor(conn: asyncpg.Connection, identity: str) -> str:
    row = await conn.fetchrow(
        """
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', $1)
        RETURNING id::text
        """,
        identity,
    )
    return row["id"]


async def _seed_session(
    conn: asyncpg.Connection,
    *,
    model: str,
    state: str,
    created_at: datetime,
    tokens_in: int,
    tokens_out: int,
    estimated_usd: float,
) -> dict[str, str]:
    actor_id = await _seed_actor(conn, f"session-{model}-{created_at.isoformat()}")
    intent_id = await conn.fetchval(
        """
        INSERT INTO intent (id, source, raw, created_by, created_at)
        VALUES (gen_random_uuid(), 'manual', $1, $2::uuid, $3::timestamptz)
        RETURNING id::text
        """,
        f"intent for {model}",
        actor_id,
        created_at,
    )
    cascade_id = await conn.fetchval(
        """
        INSERT INTO cascade (id, intent_id, shape, narrative, state, created_at)
        VALUES (gen_random_uuid(), $1::uuid, $2::jsonb, $3, 'active', $4::timestamptz)
        RETURNING id::text
        """,
        intent_id,
        json.dumps({"title": "Session Cascade"}),
        "Session Cascade",
        created_at,
    )
    stage_id = await conn.fetchval(
        """
        INSERT INTO stage (id, cascade_id, type, state, created_at)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'pending', $2::timestamptz)
        RETURNING id::text
        """,
        cascade_id,
        created_at,
    )
    session_id = await conn.fetchval(
        """
        INSERT INTO work_session (id, stage_ids, harness_type, model, state, cost, created_at)
        VALUES (
            gen_random_uuid(),
            ARRAY[$1::uuid],
            'native',
            $2,
            $3,
            $4::jsonb,
            $5::timestamptz
        )
        RETURNING id::text
        """,
        stage_id,
        model,
        state,
        json.dumps(
            {
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "estimated_usd": estimated_usd,
            }
        ),
        created_at,
    )
    return {
        "session_id": session_id,
        "intent_id": intent_id,
        "cascade_id": cascade_id,
        "stage_id": stage_id,
    }


async def _get_token(client: AsyncClient, secret: str) -> str:
    resp = await client.post("/api/auth/token", json={"secret": secret})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_sessions_list_and_messages(
    conn: asyncpg.Connection, pg_container, monkeypatch
) -> None:
    secret = "sessions-secret-for-eclusa-backoffice-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)
    app = create_app()
    pool = await asyncpg.create_pool(_dsn(pg_container), min_size=1, max_size=5)
    app.state.pool = pool
    app.state._owns_pool = False

    try:
        older_session = await _seed_session(
            conn,
            model="model-a",
            state="running",
            created_at=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
            tokens_in=10,
            tokens_out=20,
            estimated_usd=0.5,
        )
        newer_session = await _seed_session(
            conn,
            model="model-b",
            state="paused",
            created_at=datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
            tokens_in=30,
            tokens_out=40,
            estimated_usd=1.5,
        )

        message_rows = [
            {
                "role": "user",
                "content": {"text": "hello"},
                "created_at": datetime(2099, 1, 2, 10, 1, tzinfo=timezone.utc),
            },
            {
                "role": "assistant",
                "content": {"text": "world"},
                "created_at": datetime(2099, 1, 2, 10, 2, tzinfo=timezone.utc),
            },
        ]
        for row in message_rows:
            await conn.execute(
                """
                INSERT INTO artifact (id, intent_id, cascade_id, stage_id, session_id, type, payload, created_at)
                VALUES (
                    gen_random_uuid(),
                    $1::uuid,
                    $2::uuid,
                    $3::uuid,
                    $4::uuid,
                    'message_sent',
                    $5::jsonb,
                    $6::timestamptz
                )
                """,
                newer_session["intent_id"],
                newer_session["cascade_id"],
                newer_session["stage_id"],
                newer_session["session_id"],
                json.dumps(
                    {
                        "role": row["role"],
                        "content": row["content"],
                    }
                ),
                row["created_at"],
            )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _get_token(client, secret)

            resp = await client.get(
                "/api/sessions",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            session_ids = [s["id"] for s in data]
            assert newer_session["session_id"] in session_ids
            assert older_session["session_id"] in session_ids
            newer = next(s for s in data if s["id"] == newer_session["session_id"])
            assert newer["cost_estimated_usd"] == 1.5

            messages_resp = await client.get(
                f"/api/sessions/{newer_session['session_id']}/messages",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert messages_resp.status_code == 200
            messages = messages_resp.json()
            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert messages[1]["role"] == "assistant"
            assert messages[0]["content"]["text"] == "hello"

            missing = await client.get(
                "/api/sessions/00000000-0000-0000-0000-000000000000/messages",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert missing.status_code == 404
    finally:
        await pool.close()
