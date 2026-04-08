from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token

router = APIRouter(prefix="/cascades", dependencies=[Depends(verify_token)])

__all__ = ["router"]


class StageStatus(BaseModel):
    id: UUID
    type: str
    state: str
    created_at: datetime


class StageDetail(BaseModel):
    id: UUID
    type: str
    state: str
    scc_stage: str | None = None
    display_name: str
    depends_on: list[UUID]
    resolved_at: datetime | None = None
    output_summary: str | None = None
    created_at: datetime


class CascadeItem(BaseModel):
    id: UUID
    title: str
    state: str
    created_at: datetime
    stage_count: int
    blocked_stage_count: int


class CascadeDetail(BaseModel):
    id: UUID
    title: str
    state: str
    created_at: datetime
    stages: list[StageStatus]


def _title_from_row(row: dict) -> str:
    title = row.get("title")
    if title:
        return title
    narrative = row.get("narrative")
    if narrative:
        return narrative
    shape = row.get("shape")
    if isinstance(shape, str):
        try:
            shape = json.loads(shape)
        except json.JSONDecodeError:
            shape = {}
    if isinstance(shape, dict):
        title = shape.get("title")
        if title:
            return str(title)
    return str(row["id"])


def _record_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


@router.get("", response_model=list[CascadeItem])
async def list_cascades(request: Request) -> list[CascadeItem]:
    pool = request.app.state.pool
    rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          c.id,
          COALESCE(c.narrative, c.shape->>'title', c.id::text) AS title,
          c.narrative,
          c.shape,
          c.state,
          c.created_at,
          COUNT(s.id) AS stage_count,
          COUNT(s.id) FILTER (WHERE s.state = 'blocked') AS blocked_stage_count
        FROM cascade c
        LEFT JOIN stage s ON s.cascade_id = c.id
        WHERE c.state = 'active'
        GROUP BY c.id, c.narrative, c.shape, c.state, c.created_at
        ORDER BY c.created_at DESC, c.id DESC
        """
        )
    ]
    return [
        CascadeItem(
            id=row["id"],
            title=_title_from_row(row),
            state=row["state"],
            created_at=row["created_at"],
            stage_count=int(row["stage_count"]),
            blocked_stage_count=int(row["blocked_stage_count"]),
        )
        for row in rows
    ]


@router.get("/{cascade_id}", response_model=CascadeDetail)
async def get_cascade(cascade_id: UUID, request: Request) -> CascadeDetail:
    pool = request.app.state.pool
    row = await pool.fetchrow(
        """
        SELECT
          c.id,
          COALESCE(c.narrative, c.shape->>'title', c.id::text) AS title,
          c.narrative,
          c.shape,
          c.state,
          c.created_at
        FROM cascade c
        WHERE c.id = $1::uuid
        """,
        cascade_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Cascade not found")
    row = _record_dict(row)

    stages = [
        _record_dict(stage_row)
        for stage_row in await pool.fetch(
            """
        SELECT id, type, state, created_at
        FROM stage
        WHERE cascade_id = $1::uuid
        ORDER BY created_at ASC, id ASC
        """,
            cascade_id,
        )
    ]

    return CascadeDetail(
        id=row["id"],
        title=_title_from_row(row),
        state=row["state"],
        created_at=row["created_at"],
        stages=[
            StageStatus(
                id=stage_row["id"],
                type=stage_row["type"],
                state=stage_row["state"],
                created_at=stage_row["created_at"],
            )
            for stage_row in stages
        ],
    )


_SCC_DISPLAY_NAMES = {
    "refine": "Refine",
    "intent_validation_fanout": "Intent Validation",
    "match": "Match",
    "cohere": "Cohere",
    "formalize": "Formalize",
    "derive": "Derive",
    "generate": "Generate",
    "ship": "Ship",
}


def _extract_scc_stage(stage_input) -> str | None:
    if isinstance(stage_input, str):
        try:
            stage_input = json.loads(stage_input)
        except json.JSONDecodeError:
            return None
    if isinstance(stage_input, dict):
        return stage_input.get("scc_stage")
    return None


def _output_summary(output) -> str | None:
    if output is None:
        return None
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            return output[:200] if len(output) > 200 else output
    if isinstance(output, dict):
        keys = list(output.keys())
        return f"{len(keys)} keys: {', '.join(keys[:5])}"
    if isinstance(output, list):
        return f"{len(output)} items"
    return str(output)[:200]


@router.get("/{cascade_id}/stages", response_model=list[StageDetail])
async def list_cascade_stages(cascade_id: UUID, request: Request) -> list[StageDetail]:
    pool = request.app.state.pool
    cascade = await pool.fetchrow(
        "SELECT id FROM cascade WHERE id = $1::uuid", cascade_id
    )
    if cascade is None:
        raise HTTPException(status_code=404, detail="Cascade not found")

    rows = await pool.fetch(
        """
        SELECT id, type, state, input, output, depends_on, resolved_at, created_at
        FROM stage
        WHERE cascade_id = $1::uuid
        ORDER BY created_at ASC, id ASC
        """,
        cascade_id,
    )

    result = []
    for row in rows:
        scc_stage = _extract_scc_stage(row["input"])
        display_name = _SCC_DISPLAY_NAMES.get(scc_stage, scc_stage or row["type"]) if scc_stage else row["type"]
        depends_on_raw = row["depends_on"] or []
        result.append(
            StageDetail(
                id=row["id"],
                type=row["type"],
                state=row["state"],
                scc_stage=scc_stage,
                display_name=display_name,
                depends_on=[UUID(str(d)) for d in depends_on_raw],
                resolved_at=row["resolved_at"],
                output_summary=_output_summary(row["output"]),
                created_at=row["created_at"],
            )
        )
    return result


class StageOutput(BaseModel):
    stage_id: UUID
    scc_stage: str | None = None
    display_name: str
    state: str
    output: dict | list | str | None = None
    output_summary: str | None = None
    resolved_at: datetime | None = None


@router.get("/{cascade_id}/stages/{stage_id}/output", response_model=StageOutput)
async def get_stage_output(cascade_id: UUID, stage_id: UUID, request: Request) -> StageOutput:
    pool = request.app.state.pool
    row = await pool.fetchrow(
        """
        SELECT id, type, state, input, output, resolved_at
        FROM stage
        WHERE id = $1::uuid AND cascade_id = $2::uuid
        """,
        stage_id,
        cascade_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    row = _record_dict(row)
    scc_stage = _extract_scc_stage(row["input"])
    display_name = _SCC_DISPLAY_NAMES.get(scc_stage, scc_stage or row["type"]) if scc_stage else row["type"]

    output = row["output"]
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            pass

    return StageOutput(
        stage_id=row["id"],
        scc_stage=scc_stage,
        display_name=display_name,
        state=row["state"],
        output=output,
        output_summary=_output_summary(row["output"]),
        resolved_at=row["resolved_at"],
    )
