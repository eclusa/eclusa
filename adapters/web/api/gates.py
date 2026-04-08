from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token

router = APIRouter(prefix="/gates", dependencies=[Depends(verify_token)])

__all__ = ["router"]


class GateItem(BaseModel):
    id: UUID
    cascade_id: UUID
    state: str
    input: dict[str, Any]
    created_at: datetime
    model_recommendation: str | None = None


def _coerce_input(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(value, dict):
        return value
    return {}


def _record_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


@router.get("", response_model=list[GateItem])
async def list_gates(request: Request, state: str | None = None) -> list[GateItem]:
    pool = request.app.state.pool
    sql = """
        SELECT
          id,
          cascade_id,
          state,
          input,
          created_at,
          input->>'model_recommendation' AS model_recommendation
        FROM stage
        WHERE type = 'gate'
    """
    params: list[Any] = []
    if state is not None:
        sql += " AND state = $1"
        params.append(state)
    sql += " ORDER BY created_at DESC, id DESC"

    rows = [_record_dict(row) for row in await pool.fetch(sql, *params)]
    return [
        GateItem(
            id=row["id"],
            cascade_id=row["cascade_id"],
            state=row["state"],
            input=_coerce_input(row["input"]),
            created_at=row["created_at"],
            model_recommendation=row["model_recommendation"],
        )
        for row in rows
    ]
