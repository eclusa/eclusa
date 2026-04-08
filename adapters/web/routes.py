"""FastAPI router for gate resolution callbacks — RBAC enforced (D-14).

D-12: Permission check in resolve_gate() path — actor must have resolve permission.
D-14: RBAC is checked at the API/adapter boundary, not in the executor.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token
from executor.dispatch import resolve_gate

logger = logging.getLogger(__name__)
router = APIRouter()

__all__ = [
    "router",
    "check_resolve_permission",
    "has_cost_view_permission",
    "ResolveRequest",
]


async def check_resolve_permission(
    conn: asyncpg.Connection,
    actor_id: str,
    gate_type: str,
) -> bool:
    """Return True if actor has resolve permission for gate_type. D-12, D-14.

    Permission shape in actor.permissions JSONB:
      {"resolve_gates": ["*"]}          → can resolve any gate type
      {"resolve_gates": ["approval"]}   → can resolve only 'approval' gate type
      {"resolve_gates": []}             → cannot resolve any gate
      {} or None                        → cannot resolve any gate
    Actor not found → False.
    """
    row = await conn.fetchrow(
        "SELECT permissions FROM actor WHERE id = $1::uuid", actor_id
    )
    if row is None:
        return False
    permissions = (
        json.loads(row["permissions"])
        if isinstance(row["permissions"], str)
        else (row["permissions"] or {})
    )
    resolvable = permissions.get("resolve_gates", [])
    return gate_type in resolvable or resolvable == ["*"]


async def has_cost_view_permission(conn: asyncpg.Connection, actor_id: str) -> bool:
    """Return True if actor has view_costs permission. D-13.

    Permission shape: {"view_costs": true} → True; anything else → False.
    Actor not found → False.
    """
    row = await conn.fetchrow(
        "SELECT permissions FROM actor WHERE id = $1::uuid", actor_id
    )
    if row is None:
        return False
    permissions = (
        json.loads(row["permissions"])
        if isinstance(row["permissions"], str)
        else (row["permissions"] or {})
    )
    return bool(permissions.get("view_costs", False))


class ResolveRequest(BaseModel):
    """Request body for gate resolution endpoint.

    token: opaque resolve token from the gate surfacing email URL
    decision: the actor's decision (e.g. 'approved', 'rejected', or custom)
    actor_id: UUID of the resolving actor (used for RBAC check)
    """

    token: str
    decision: str
    actor_id: str


@router.post("/gates/{gate_id}/resolve")
async def resolve_gate_endpoint(
    gate_id: str,
    body: ResolveRequest,
    request: Request,
    payload: dict = Depends(verify_token),
) -> dict:
    """Resolve a gate. JWT required. Actor derived from token. RBAC enforced. D-12, D-14."""
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as conn:
        # 1. Fetch gate stage
        row = await conn.fetchrow(
            """
            SELECT id, state, cascade_id, resolve_token, expires_at, input
            FROM stage WHERE id = $1::uuid AND type = 'gate'
            """,
            gate_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Gate not found")
        if row["state"] != "blocked":
            raise HTTPException(
                status_code=409,
                detail=f"Gate is not blocked (state={row['state']!r})",
            )

        # 2. Token validation — resolve_token is nullable; if NULL, skip token check
        if row["resolve_token"] is not None:
            if not secrets.compare_digest(body.token, row["resolve_token"]):
                raise HTTPException(status_code=403, detail="Invalid resolution token")
            if row["expires_at"] and datetime.now(timezone.utc) > row[
                "expires_at"
            ].replace(tzinfo=timezone.utc):
                raise HTTPException(status_code=403, detail="Resolution token expired")

        # 3. RBAC check — actor_id from JWT, not body (AUTH-01)
        actor_id = payload["sub"]
        stage_input = (
            json.loads(row["input"])
            if isinstance(row["input"], str)
            else (row["input"] or {})
        )
        gate_type = stage_input.get("gate_type", "default")
        allowed = await check_resolve_permission(conn, actor_id, gate_type)
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Actor lacks resolve permission for gate type {gate_type!r}",
            )

        # 4. Resolve — writes DB + fires NOTIFY on both channels (EXEC-07)
        await resolve_gate(conn, gate_id, actor_id)

    return {"status": "resolved", "gate_id": gate_id}
