from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

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


async def _seed_cascade(
    conn: asyncpg.Connection,
    *,
    title: str,
    state: str,
    created_at: datetime,
    stage_specs: list[dict],
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
        VALUES (gen_random_uuid(), $1::uuid, $2::jsonb, $3, $4::cascade_state, $5::timestamptz)
        RETURNING id::text
        """,
        intent_id,
        json.dumps({"title": title}),
        title,
        state,
        created_at,
    )

    for index, spec in enumerate(stage_specs):
        await conn.fetchrow(
            """
            INSERT INTO stage (id, cascade_id, type, state, input, created_at)
            VALUES (
                gen_random_uuid(),
                $1::uuid,
                $2::stage_type,
                $3::stage_state,
                $4::jsonb,
                $5::timestamptz
            )
            """,
            cascade_id,
            spec["type"],
            spec["state"],
            json.dumps(spec.get("input") or {}),
            created_at + timedelta(seconds=index + 1),
        )

    return cascade_id


async def _get_token(client: AsyncClient, secret: str) -> str:
    resp = await client.post("/api/auth/token", json={"secret": secret})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_cascades_list_and_detail(
    conn: asyncpg.Connection, pg_container, monkeypatch
) -> None:
    secret = "cascade-secret-for-eclusa-backoffice-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)
    app = create_app()
    pool = await asyncpg.create_pool(_dsn(pg_container), min_size=1, max_size=5)
    app.state.pool = pool
    app.state._owns_pool = False

    newest_cascade_id = None
    blocked_id = None
    detail_cascade_id = None

    try:
        detail_cascade_id = await _seed_cascade(
            conn,
            title="Cascade Alpha",
            state="active",
            created_at=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
            stage_specs=[
                {"type": "narrowing", "state": "pending"},
                {
                    "type": "gate",
                    "state": "blocked",
                    "input": {"model_recommendation": "approve"},
                },
                {"type": "gate", "state": "resolved"},
            ],
        )
        newest_cascade_id = await _seed_cascade(
            conn,
            title="Cascade Beta",
            state="active",
            created_at=datetime(2099, 1, 2, 10, 0, tzinfo=timezone.utc),
            stage_specs=[
                {"type": "narrowing", "state": "active"},
                {
                    "type": "gate",
                    "state": "blocked",
                    "input": {"model_recommendation": "hold"},
                },
            ],
        )
        blocked_id = await _seed_cascade(
            conn,
            title="Cascade Paused",
            state="paused",
            created_at=datetime(2099, 1, 3, 10, 0, tzinfo=timezone.utc),
            stage_specs=[{"type": "gate", "state": "blocked"}],
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _get_token(client, secret)

            unauthorized = await client.get("/api/cascades")
            assert unauthorized.status_code == 401

            resp = await client.get(
                "/api/cascades",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            ids = [item["id"] for item in data]
            assert newest_cascade_id in ids
            assert detail_cascade_id in ids
            assert blocked_id not in ids
            assert data[0]["id"] == newest_cascade_id
            newest = next(item for item in data if item["id"] == newest_cascade_id)
            assert newest["stage_count"] == 2
            assert newest["blocked_stage_count"] == 1
            detail = next(item for item in data if item["id"] == detail_cascade_id)
            assert detail["stage_count"] == 3
            assert detail["blocked_stage_count"] == 1

            detail_resp = await client.get(
                f"/api/cascades/{detail_cascade_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert detail_resp.status_code == 200
            detail_data = detail_resp.json()
            assert detail_data["id"] == detail_cascade_id
            assert detail_data["title"] == "Cascade Alpha"
            assert detail_data["state"] == "active"
            assert len(detail_data["stages"]) == 3
            assert detail_data["stages"][0]["type"] == "narrowing"
            assert detail_data["stages"][1]["state"] == "blocked"

            missing = await client.get(
                "/api/cascades/00000000-0000-0000-0000-000000000000",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert missing.status_code == 404
    finally:
        await pool.close()
