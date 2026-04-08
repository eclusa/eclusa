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
    cascade_title: str,
    created_at: datetime,
    tokens_in: int,
    tokens_out: int,
    estimated_usd: float,
) -> str:
    actor_id = await _seed_actor(conn, f"cost-{model}-{created_at.isoformat()}")
    intent_id = await conn.fetchval(
        """
        INSERT INTO intent (id, source, raw, created_by, created_at)
        VALUES (gen_random_uuid(), 'manual', $1, $2::uuid, $3::timestamptz)
        RETURNING id::text
        """,
        f"intent for {cascade_title}",
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
        json.dumps({"title": cascade_title}),
        cascade_title,
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
            'running',
            $3::jsonb,
            $4::timestamptz
        )
        RETURNING id::text
        """,
        stage_id,
        model,
        json.dumps(
            {
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "estimated_usd": estimated_usd,
            }
        ),
        created_at,
    )
    return session_id


async def _get_token(client: AsyncClient, secret: str) -> str:
    resp = await client.post("/api/auth/token", json={"secret": secret})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_costs_summary(
    conn: asyncpg.Connection, pg_container, monkeypatch
) -> None:
    secret = "costs-secret-for-eclusa-backoffice-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)
    app = create_app()
    pool = await asyncpg.create_pool(_dsn(pg_container), min_size=1, max_size=5)
    app.state.pool = pool
    app.state._owns_pool = False

    try:
        await _seed_session(
            conn,
            model="model-a",
            cascade_title="Cascade A",
            created_at=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
            tokens_in=11,
            tokens_out=22,
            estimated_usd=0.11,
        )
        await _seed_session(
            conn,
            model="model-a",
            cascade_title="Cascade A",
            created_at=datetime(2099, 1, 1, 11, 0, tzinfo=timezone.utc),
            tokens_in=33,
            tokens_out=44,
            estimated_usd=0.22,
        )
        await _seed_session(
            conn,
            model="model-b",
            cascade_title="Cascade B",
            created_at=datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
            tokens_in=55,
            tokens_out=66,
            estimated_usd=0.55,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _get_token(client, secret)

            resp = await client.get(
                "/api/costs",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["by_session"]) == 3
            assert len(data["by_model"]) == 2
            assert len(data["by_cascade"]) == 3  # each _seed_session creates a distinct cascade
            assert data["by_model"][0]["session_count"] == 2
            assert any(row["total_tokens_in"] == 44 for row in data["by_model"])
    finally:
        await pool.close()
