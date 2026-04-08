from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token

router = APIRouter(prefix="/sessions", dependencies=[Depends(verify_token)])

__all__ = ["router"]


class SessionItem(BaseModel):
    id: UUID
    stage_id: UUID | None
    model: str
    state: str
    cost_estimated_usd: float
    created_at: datetime
    title: str


class SessionMessage(BaseModel):
    id: UUID
    role: str
    content: dict[str, Any]
    created_at: datetime


def _record_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


def _coerce_content(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"value": value}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    return {"value": value}


@router.get("", response_model=list[SessionItem])
async def list_sessions(request: Request) -> list[SessionItem]:
    pool = request.app.state.pool
    rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          ws.id,
          ws.stage_ids[1] AS stage_id,
          ws.model,
          ws.state,
          COALESCE((ws.cost->>'estimated_usd')::numeric, 0) AS cost_estimated_usd,
          ws.created_at,
          COALESCE(
            NULLIF(c.narrative, ''),
            LEFT(i.raw, 120),
            ws.harness_type || ' session'
          ) AS title
        FROM work_session ws
        LEFT JOIN stage s ON s.id = ws.stage_ids[1]
        LEFT JOIN cascade c ON c.id = s.cascade_id
        LEFT JOIN intent i ON i.id = c.intent_id
        ORDER BY ws.created_at DESC, ws.id DESC
        LIMIT 100
        """
        )
    ]
    return [
        SessionItem(
            id=row["id"],
            stage_id=row["stage_id"],
            model=row["model"],
            state=row["state"],
            cost_estimated_usd=float(row["cost_estimated_usd"] or 0.0),
            created_at=row["created_at"],
            title=row.get("title") or "Untitled session",
        )
        for row in rows
    ]


@router.get("/{session_id}/messages", response_model=list[SessionMessage])
async def list_session_messages(
    session_id: UUID, request: Request
) -> list[SessionMessage]:
    pool = request.app.state.pool
    session_row = await pool.fetchrow(
        "SELECT id, message_history, created_at FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Primary path: read from artifact table (executor work sessions)
    rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          id,
          COALESCE(payload->>'role', type::text) AS role,
          COALESCE(payload->'content', payload, '{}'::jsonb) AS content,
          created_at
        FROM artifact
        WHERE session_id = $1::uuid
        ORDER BY created_at ASC, id ASC
        """,
            session_id,
        )
    ]
    if rows:
        return [
            SessionMessage(
                id=row["id"],
                role=row["role"],
                content=_coerce_content(row["content"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # Fallback: read from work_session.message_history (chat sessions)
    raw_history = session_row["message_history"]
    if not raw_history:
        return []
    if isinstance(raw_history, str):
        raw_history = json.loads(raw_history)
    if not isinstance(raw_history, list):
        return []

    messages: list[SessionMessage] = []
    session_created = session_row["created_at"]
    for i, entry in enumerate(raw_history):
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind", "")
        parts = entry.get("parts", [])
        if kind == "request":
            for part in parts:
                part_kind = part.get("part_kind", "")
                if part_kind == "user-prompt":
                    messages.append(SessionMessage(
                        id=UUID(int=i + 1),
                        role="user",
                        content={"text": part.get("content", "")},
                        created_at=session_created,
                    ))
        elif kind == "response":
            for part in parts:
                part_kind = part.get("part_kind", "")
                if part_kind == "text":
                    messages.append(SessionMessage(
                        id=UUID(int=i + 1),
                        role="assistant",
                        content={"text": part.get("content", "")},
                        created_at=session_created,
                    ))
    return messages
