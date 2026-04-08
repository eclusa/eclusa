from __future__ import annotations

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


async def _seed_metric_gate(conn: asyncpg.Connection) -> tuple[str, str, str]:
    actor_id = await _seed_actor(conn, "metrics-api-test")
    intent_id = await conn.fetchval(
        """
        INSERT INTO intent (id, source, raw, created_by, created_at)
        VALUES (gen_random_uuid(), 'manual', 'metrics intent', $1::uuid, $2::timestamptz)
        RETURNING id::text
        """,
        actor_id,
        datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    cascade_id = await conn.fetchval(
        """
        INSERT INTO cascade (id, intent_id, shape, narrative, state, created_at)
        VALUES (gen_random_uuid(), $1::uuid, '{}'::jsonb, 'metrics cascade', 'active', $2::timestamptz)
        RETURNING id::text
        """,
        intent_id,
        datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    stage_id = await conn.fetchval(
        """
        INSERT INTO stage (id, cascade_id, type, state, created_at)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'blocked', $2::timestamptz)
        RETURNING id::text
        """,
        cascade_id,
        datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, actor_id, cascade_id, stage_id, type, content, timestamp)
        VALUES (gen_random_uuid(), $1::uuid, $2::uuid, $3::uuid, 'gate_surfaced',
                '{"system_recommendation": "yes"}'::jsonb, $4::timestamptz)
        """,
        actor_id,
        cascade_id,
        stage_id,
        datetime(2099, 1, 1, 10, 1, tzinfo=timezone.utc),
    )
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, actor_id, cascade_id, stage_id, type, content, timestamp)
        VALUES (gen_random_uuid(), $1::uuid, $2::uuid, $3::uuid, 'gate_resolved',
                '{"human_choice": "no", "system_recommendation": "yes"}'::jsonb, $4::timestamptz)
        """,
        actor_id,
        cascade_id,
        stage_id,
        datetime(2099, 1, 1, 10, 2, tzinfo=timezone.utc),
    )
    return actor_id, cascade_id, stage_id


async def _get_token(client: AsyncClient, secret: str) -> str:
    resp = await client.post("/api/auth/token", json={"secret": secret})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_metrics_empty_and_seeded(
    conn: asyncpg.Connection, pg_container, monkeypatch
) -> None:
    secret = "metrics-secret-for-eclusa-backoffice-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)
    app = create_app()
    pool = await asyncpg.create_pool(_dsn(pg_container), min_size=1, max_size=5)
    app.state.pool = pool
    app.state._owns_pool = False

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _get_token(client, secret)

            empty_resp = await client.get(
                "/api/metrics",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert empty_resp.status_code == 200
            empty = empty_resp.json()
            assert set(empty.keys()) == {
                "gate_necessity",
                "orchestrator_absorption",
                "resolution_latency",
                "decision_durability",
                "cascade_rework",
                "model_convergence",
                "minority_accuracy",
                "fanout_necessity",
            }

            await _seed_metric_gate(conn)

            seeded_resp = await client.get(
                "/api/metrics",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert seeded_resp.status_code == 200
            seeded = seeded_resp.json()
            assert seeded["gate_necessity"] == 1.0
            assert seeded["orchestrator_absorption"] is None or isinstance(
                seeded["orchestrator_absorption"], float
            )
    finally:
        await pool.close()
