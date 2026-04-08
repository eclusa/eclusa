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


async def _seed_gate(
    conn: asyncpg.Connection,
    *,
    cascade_id: str,
    state: str,
    created_at: datetime,
    input_data: dict | None = None,
) -> str:
    row = await conn.fetchval(
        """
        INSERT INTO stage (id, cascade_id, type, state, input, created_at)
        VALUES (
            gen_random_uuid(),
            $1::uuid,
            'gate',
            $2::stage_state,
            $3::jsonb,
            $4::timestamptz
        )
        RETURNING id::text
        """,
        cascade_id,
        state,
        json.dumps(input_data or {}),
        created_at,
    )
    return row


async def _seed_cascade(
    conn: asyncpg.Connection,
    *,
    title: str,
    created_at: datetime,
) -> str:
    actor_id = await _seed_actor(conn, f"system-{title}")
    intent_id = await conn.fetchval(
        """
        INSERT INTO intent (id, source, raw, created_by, created_at)
        VALUES (gen_random_uuid(), 'manual', $1, $2::uuid, $3::timestamptz)
        RETURNING id::text
        """,
        f"intent for {title}",
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
        json.dumps({"title": title}),
        title,
        created_at,
    )
    return cascade_id


async def _get_token(client: AsyncClient, secret: str) -> str:
    resp = await client.post("/api/auth/token", json={"secret": secret})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_gates_list_filters_by_state(
    conn: asyncpg.Connection, pg_container, monkeypatch
) -> None:
    secret = "gate-secret-for-eclusa-backoffice-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)
    app = create_app()
    pool = await asyncpg.create_pool(_dsn(pg_container), min_size=1, max_size=5)
    app.state.pool = pool
    app.state._owns_pool = False

    try:
        cascade_id = await _seed_cascade(
            conn,
            title="Gate Cascade",
            created_at=datetime(2099, 2, 1, 10, 0, tzinfo=timezone.utc),
        )
        blocked_gate_id = await _seed_gate(
            conn,
            cascade_id=cascade_id,
            state="blocked",
            created_at=datetime(2099, 2, 1, 10, 1, tzinfo=timezone.utc),
            input_data={"model_recommendation": "approve", "gate_type": "approval"},
        )
        resolved_gate_id = await _seed_gate(
            conn,
            cascade_id=cascade_id,
            state="resolved",
            created_at=datetime(2099, 2, 1, 10, 2, tzinfo=timezone.utc),
            input_data={"gate_type": "approval"},
        )
        other_gate_id = await _seed_gate(
            conn,
            cascade_id=cascade_id,
            state="pending",
            created_at=datetime(2099, 2, 1, 10, 3, tzinfo=timezone.utc),
            input_data={"model_recommendation": "review"},
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _get_token(client, secret)

            unauthorized = await client.get("/api/gates")
            assert unauthorized.status_code == 401

            all_resp = await client.get(
                "/api/gates",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert all_resp.status_code == 200
            all_rows = all_resp.json()
            all_ids = {row["id"] for row in all_rows}
            assert blocked_gate_id in all_ids
            assert resolved_gate_id in all_ids
            assert other_gate_id in all_ids

            blocked_resp = await client.get(
                "/api/gates?state=blocked",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert blocked_resp.status_code == 200
            blocked_rows = blocked_resp.json()
            assert blocked_rows[0]["id"] == blocked_gate_id
            row = blocked_rows[0]
            assert row["id"] == blocked_gate_id
            assert row["cascade_id"] == cascade_id
            assert row["state"] == "blocked"
            assert row["input"]["gate_type"] == "approval"
            assert row["model_recommendation"] == "approve"
    finally:
        await pool.close()
