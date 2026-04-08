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


async def _seed_ledger_entry(
    conn: asyncpg.Connection,
    *,
    actor_id: str,
    timestamp: datetime,
    event_type: str,
    content: dict | None = None,
) -> str:
    row = await conn.fetchrow(
        """
        INSERT INTO ledger_entry (id, actor_id, type, content, timestamp)
        VALUES (gen_random_uuid(), $1::uuid, $2, COALESCE($3::jsonb, '{}'::jsonb), $4::timestamptz)
        RETURNING id::text
        """,
        actor_id,
        event_type,
        json.dumps(content) if content is not None else None,
        timestamp,
    )
    return row["id"]


async def _get_token(client: AsyncClient, secret: str) -> str:
    resp = await client.post("/api/auth/token", json={"secret": secret})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_ledger_as_of_paginates(
    conn: asyncpg.Connection, pg_container, monkeypatch
) -> None:
    secret = "ledger-secret-for-eclusa-backoffice-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)
    app = create_app()
    pool = await asyncpg.create_pool(_dsn(pg_container), min_size=1, max_size=5)
    app.state.pool = pool
    app.state._owns_pool = False

    try:
        actor_id = await _seed_actor(conn, "ledger-api-test")
        ts1 = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
        ts2 = ts1 + timedelta(minutes=1)
        ts3 = ts2 + timedelta(minutes=1)
        await _seed_ledger_entry(
            conn, actor_id=actor_id, timestamp=ts1, event_type="cascade_created"
        )
        await _seed_ledger_entry(
            conn, actor_id=actor_id, timestamp=ts2, event_type="gate_surfaced"
        )
        await _seed_ledger_entry(
            conn, actor_id=actor_id, timestamp=ts3, event_type="gate_resolved"
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _get_token(client, secret)
            resp = await client.get(
                "/api/ledger",
                params={"as_of": ts3.isoformat(), "page": 0, "size": 2},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_count"] == 3
            assert data["page"] == 0
            assert data["size"] == 2
            assert len(data["items"]) == 2
            assert data["items"][0]["type"] == "gate_resolved"
            assert data["items"][1]["type"] == "gate_surfaced"
    finally:
        await pool.close()
