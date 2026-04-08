from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

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


async def _seed_entity(
    conn: asyncpg.Connection, name: str, embedding: list[float] | None = None
) -> str:
    if embedding is None:
        row = await conn.fetchrow(
            """
            INSERT INTO entity (id, name, type, summary)
            VALUES (gen_random_uuid(), $1, 'concept', $2)
            RETURNING id::text
            """,
            name,
            f"Summary for {name}",
        )
    else:
        emb = "[" + ",".join(str(v) for v in embedding) + "]"
        row = await conn.fetchrow(
            """
            INSERT INTO entity (id, name, type, summary, embedding)
            VALUES (gen_random_uuid(), $1, 'concept', $2, $3::vector)
            RETURNING id::text
            """,
            name,
            f"Summary for {name}",
            emb,
        )
    return row["id"]


async def _seed_fact(
    conn: asyncpg.Connection,
    *,
    source_entity: str,
    target_entity: str,
    predicate: str,
    t_created: datetime,
) -> str:
    row = await conn.fetchrow(
        """
        INSERT INTO fact (id, source_entity, target_entity, predicate, t_valid, t_created)
        VALUES (gen_random_uuid(), $1::uuid, $2::uuid, $3, $4::timestamptz, $4::timestamptz)
        RETURNING id::text
        """,
        source_entity,
        target_entity,
        predicate,
        t_created,
    )
    return row["id"]


async def _seed_community(
    conn: asyncpg.Connection, name: str, entity_ids: list[str]
) -> str:
    community_entity_ids = [UUID(entity_id) for entity_id in entity_ids]
    row = await conn.fetchrow(
        """
        INSERT INTO community (id, name, entity_ids)
        VALUES (gen_random_uuid(), $1, $2::uuid[])
        RETURNING id::text
        """,
        name,
        community_entity_ids,
    )
    return row["id"]


async def _get_token(client: AsyncClient, secret: str) -> str:
    resp = await client.post("/api/auth/token", json={"secret": secret})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_knowledge_entities_facts_and_communities(
    conn: asyncpg.Connection,
    pg_container,
    monkeypatch,
) -> None:
    secret = "knowledge-secret-for-eclusa-backoffice-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)
    app = create_app()
    pool = await asyncpg.create_pool(_dsn(pg_container), min_size=1, max_size=5)
    app.state.pool = pool
    app.state._owns_pool = False

    try:
        entity_a = await _seed_entity(conn, "Alpha", embedding=[0.1] * 1024)
        entity_b = await _seed_entity(conn, "Beta", embedding=[0.2] * 1024)
        await _seed_fact(
            conn,
            source_entity=entity_a,
            target_entity=entity_b,
            predicate="relates_to",
            t_created=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        await _seed_community(conn, "Alpha Cluster", [entity_a, entity_b])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = await _get_token(client, secret)

            entities_resp = await client.get(
                "/api/knowledge/entities?q=Alpha&limit=20",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert entities_resp.status_code == 200
            entities = entities_resp.json()
            assert len(entities) > 0
            assert any(e["name"] == "Alpha" for e in entities)

            facts_resp = await client.get(
                f"/api/knowledge/facts?entity_id={entity_a}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert facts_resp.status_code == 200
            facts = facts_resp.json()
            assert len(facts) == 1
            assert facts[0]["predicate"] == "relates_to"
            assert facts[0]["object_value"] == "Beta"

            communities_resp = await client.get(
                "/api/knowledge/communities",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert communities_resp.status_code == 200
            communities = communities_resp.json()
            assert len(communities) == 1
            assert communities[0]["member_count"] == 2
    finally:
        await pool.close()
