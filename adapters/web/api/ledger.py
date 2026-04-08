from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token

router = APIRouter(prefix="/ledger", dependencies=[Depends(verify_token)])

__all__ = ["router"]

AS_OF_SQL = (Path(__file__).resolve().parents[3] / "db/queries/as_of.sql").read_text()


class LedgerItem(BaseModel):
    id: UUID
    type: str
    content: dict[str, Any]
    cascade_id: UUID | None
    stage_id: UUID | None
    session_id: UUID | None
    timestamp: datetime
    schema_version: str


class LedgerPage(BaseModel):
    items: list[LedgerItem]
    total_count: int
    page: int
    size: int
    as_of: datetime


def _record_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


def _coerce_content(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_as_of(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = value.replace(" ", "+", 1).replace("Z", "+00:00")
    dt = datetime.fromisoformat(parsed)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _coerce_numeric(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@router.get("", response_model=LedgerPage)
async def list_ledger(
    request: Request,
    as_of: str | None = None,
    page: int = 0,
    size: int = 50,
) -> LedgerPage:
    pool = request.app.state.pool
    as_of_dt = _parse_as_of(as_of)
    offset = max(page, 0) * max(size, 1)
    limit = max(size, 1)

    total_count = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM ledger_entry
        WHERE timestamp <= $1::timestamptz
        """,
        as_of_dt,
    )

    rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          id,
          type,
          content,
          cascade_id,
          stage_id,
          session_id,
          timestamp,
          schema_version
        FROM ledger_entry
        WHERE timestamp <= $1::timestamptz
        ORDER BY timestamp DESC, id DESC
        OFFSET $2
        LIMIT $3
        """,
            as_of_dt,
            offset,
            limit,
        )
    ]

    return LedgerPage(
        items=[
            LedgerItem(
                id=row["id"],
                type=row["type"],
                content=_coerce_content(row["content"]),
                cascade_id=row["cascade_id"],
                stage_id=row["stage_id"],
                session_id=row["session_id"],
                timestamp=row["timestamp"],
                schema_version=row["schema_version"],
            )
            for row in rows
        ],
        total_count=int(total_count or 0),
        page=page,
        size=size,
        as_of=as_of_dt,
    )
