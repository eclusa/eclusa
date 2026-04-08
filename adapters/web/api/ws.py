from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from adapters.web.api.auth import JWT_ALGORITHM, get_jwt_secret

router = APIRouter()

__all__ = ["router"]


def _coerce_json(value):
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    return value


def _message_payload(row) -> dict:
    return {
        "role": row["role"],
        "content": _coerce_json(row["content"]),
        "created_at": row["created_at"].isoformat(),
    }


async def _fetch_messages(
    conn, session_id: UUID, after_created_at: datetime, after_id: UUID
) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT
          id,
          COALESCE(payload->>'role', type::text) AS role,
          COALESCE(payload->'content', payload, '{}'::jsonb) AS content,
          created_at
        FROM artifact
        WHERE session_id = $1::uuid
          AND (
            created_at > $2::timestamptz
            OR (created_at = $2::timestamptz AND id > $3::uuid)
          )
        ORDER BY created_at ASC, id ASC
        """,
        session_id,
        after_created_at,
        after_id,
    )
    return [{key: row[key] for key in row.keys()} for row in rows]


@router.websocket("/ws/sessions/{session_id}")
async def stream_session_messages(websocket: WebSocket, session_id: UUID) -> None:
    await websocket.accept()

    token = websocket.query_params.get("token")
    if not token:
        await websocket.send_json({"error": "unauthorized"})
        await websocket.close(code=1008)
        return

    try:
        jwt_payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        await websocket.send_json({"error": "unauthorized"})
        await websocket.close(code=1008)
        return

    actor_id: str = jwt_payload.get("sub") or jwt_payload.get("actor_id", "")
    if not actor_id:
        await websocket.send_json({"error": "unauthorized"})
        await websocket.close(code=1008)
        return

    pool = websocket.app.state.pool
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT i.created_by
                FROM work_session ws
                JOIN stage s ON s.id = ws.stage_ids[1]
                JOIN cascade c ON c.id = s.cascade_id
                JOIN intent i ON i.id = c.intent_id
                WHERE ws.id = $1::uuid
                """,
                session_id,
            )
        if row is None:
            await websocket.send_json({"error": "session_not_found"})
            await websocket.close(code=1008)
            return
        if str(row["created_by"]) != actor_id:
            await websocket.send_json({"error": "forbidden"})
            await websocket.close(code=4008)
            return

        last_created_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
        last_id = UUID(int=0)

        async with pool.acquire() as conn:
            initial_rows = await _fetch_messages(
                conn, session_id, last_created_at, last_id
            )
        for row in initial_rows:
            await websocket.send_json(_message_payload(row))
            last_created_at = row["created_at"]
            last_id = row["id"]

        while True:
            await asyncio.sleep(2)
            async with pool.acquire() as conn:
                new_rows = await _fetch_messages(
                    conn, session_id, last_created_at, last_id
                )
            for row in new_rows:
                await websocket.send_json(_message_payload(row))
                last_created_at = row["created_at"]
                last_id = row["id"]
    except WebSocketDisconnect:
        return
