"""RBAC enforcement tests for gate resolution (SCHEMA-08).

Plan 06 implements check_resolve_permission() and has_cost_view_permission()
in adapters/web/routes.py — D-12, D-14.
"""

from __future__ import annotations

import json

import asyncpg
import pytest

from adapters.web.routes import check_resolve_permission, has_cost_view_permission

pytestmark = pytest.mark.asyncio


async def _seed_actor(conn: asyncpg.Connection, permissions: dict | None) -> str:
    """Insert an actor with given permissions JSONB and return its id as str."""
    perms_json = json.dumps(permissions) if permissions is not None else None
    row = await conn.fetchrow(
        """
        INSERT INTO actor (id, type, identity, permissions)
        VALUES (gen_random_uuid(), 'human', $1, $2::jsonb)
        RETURNING id::text
        """,
        f"test-rbac-{id(permissions)}@example.com",
        perms_json,
    )
    return row["id"]


async def test_resolve_permission_allowed(conn) -> None:
    """SCHEMA-08: Actor with matching gate type in resolve_gates is allowed."""
    actor_id = await _seed_actor(conn, {"resolve_gates": ["approval"]})
    result = await check_resolve_permission(conn, actor_id, "approval")
    assert result is True


async def test_resolve_permission_denied(conn) -> None:
    """SCHEMA-08: Actor without matching gate type is denied."""
    actor_id = await _seed_actor(conn, {"resolve_gates": ["approval"]})
    result = await check_resolve_permission(conn, actor_id, "review")
    assert result is False


async def test_resolve_permission_wildcard(conn) -> None:
    """SCHEMA-08: Actor with resolve_gates=['*'] can resolve any gate type."""
    actor_id = await _seed_actor(conn, {"resolve_gates": ["*"]})
    result = await check_resolve_permission(conn, actor_id, "anything")
    assert result is True


async def test_cost_view_permission(conn) -> None:
    """SCHEMA-08: Cost visibility restricted to actors with view_costs=true."""
    actor_with_cost = await _seed_actor(conn, {"view_costs": True})
    actor_without_cost = await _seed_actor(conn, {"view_costs": False})
    actor_empty = await _seed_actor(conn, {})

    assert await has_cost_view_permission(conn, actor_with_cost) is True
    assert await has_cost_view_permission(conn, actor_without_cost) is False
    assert await has_cost_view_permission(conn, actor_empty) is False
