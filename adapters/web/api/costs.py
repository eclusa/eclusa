from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token

router = APIRouter(prefix="/costs", dependencies=[Depends(verify_token)])

__all__ = ["router"]


class CostByCascade(BaseModel):
    cascade_id: UUID
    total_tokens_in: int
    total_tokens_out: int
    total_usd: float


class CostBySession(BaseModel):
    session_id: UUID
    total_tokens_in: int
    total_tokens_out: int
    total_usd: float


class CostByModel(BaseModel):
    model: str
    total_tokens_in: int
    total_tokens_out: int
    total_usd: float
    session_count: int


class CostSummary(BaseModel):
    by_cascade: list[CostByCascade]
    by_session: list[CostBySession]
    by_model: list[CostByModel]


def _record_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


def _coerce_cost(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _int_cost(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _float_cost(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@router.get("", response_model=CostSummary)
async def get_costs(request: Request) -> CostSummary:
    pool = request.app.state.pool

    by_session_rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          ws.id AS session_id,
          SUM(COALESCE((ws.cost->>'tokens_in')::bigint, 0)) AS total_tokens_in,
          SUM(COALESCE((ws.cost->>'tokens_out')::bigint, 0)) AS total_tokens_out,
          SUM(COALESCE((ws.cost->>'estimated_usd')::numeric, 0)) AS total_usd
        FROM work_session ws
        GROUP BY ws.id
        ORDER BY ws.created_at DESC, ws.id DESC
        """
        )
    ]

    by_model_rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          model,
          SUM(COALESCE((cost->>'tokens_in')::bigint, 0)) AS total_tokens_in,
          SUM(COALESCE((cost->>'tokens_out')::bigint, 0)) AS total_tokens_out,
          SUM(COALESCE((cost->>'estimated_usd')::numeric, 0)) AS total_usd,
          COUNT(*) AS session_count
        FROM work_session
        GROUP BY model
        ORDER BY session_count DESC, model ASC
        """
        )
    ]

    by_cascade_rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          s.cascade_id AS cascade_id,
          SUM(COALESCE((ws.cost->>'tokens_in')::bigint, 0)) AS total_tokens_in,
          SUM(COALESCE((ws.cost->>'tokens_out')::bigint, 0)) AS total_tokens_out,
          SUM(COALESCE((ws.cost->>'estimated_usd')::numeric, 0)) AS total_usd
        FROM work_session ws
        LEFT JOIN stage s ON s.id = ws.stage_ids[1]
        WHERE s.cascade_id IS NOT NULL
        GROUP BY s.cascade_id
        ORDER BY total_usd DESC, s.cascade_id ASC
        """
        )
    ]

    return CostSummary(
        by_cascade=[
            CostByCascade(
                cascade_id=row["cascade_id"],
                total_tokens_in=_int_cost(row["total_tokens_in"]),
                total_tokens_out=_int_cost(row["total_tokens_out"]),
                total_usd=_float_cost(row["total_usd"]),
            )
            for row in by_cascade_rows
        ],
        by_session=[
            CostBySession(
                session_id=row["session_id"],
                total_tokens_in=_int_cost(row["total_tokens_in"]),
                total_tokens_out=_int_cost(row["total_tokens_out"]),
                total_usd=_float_cost(row["total_usd"]),
            )
            for row in by_session_rows
        ],
        by_model=[
            CostByModel(
                model=row["model"],
                total_tokens_in=_int_cost(row["total_tokens_in"]),
                total_tokens_out=_int_cost(row["total_tokens_out"]),
                total_usd=_float_cost(row["total_usd"]),
                session_count=int(row["session_count"]),
            )
            for row in by_model_rows
        ],
    )
