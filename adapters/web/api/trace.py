from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token

router = APIRouter(prefix="/trace", dependencies=[Depends(verify_token)])

__all__ = ["router", "TraceChain", "TraceHop"]


class TraceHop(BaseModel):
    type: str
    id: str
    label: str
    href: str | None = None


class TraceChain(BaseModel):
    artifact_id: UUID
    hops: list[TraceHop]


def _trace_sql() -> str:
    root = Path(__file__).resolve().parents[3]
    for relative in ("db/queries/trace_chain.sql", "sql/trace_chain.sql"):
        path = root / relative
        if path.exists():
            return path.read_text()
    raise FileNotFoundError("trace_chain.sql not found in db/queries or sql")


def _short_label(value: str, *, prefix: str, max_length: int = 40) -> str:
    text = value.strip()
    if len(text) > max_length:
        text = f"{text[: max_length - 3]}..."
    return f"{prefix}: {text}" if text else f"{prefix}: unknown"


def _session_label(session_id: UUID) -> str:
    session_text = str(session_id)
    return f"session: {session_text[:8]}"


def _stage_label(stage_id: UUID) -> str:
    stage_text = str(stage_id)
    return f"stage: {stage_text[:8]}"


def _cascade_label(cascade_id: UUID) -> str:
    cascade_text = str(cascade_id)
    return f"cascade: {cascade_text[:8]}"


@router.get("/{artifact_id}", response_model=TraceChain)
async def get_trace_chain(artifact_id: UUID, request: Request) -> TraceChain:
    pool = request.app.state.pool
    row = await pool.fetchrow(_trace_sql(), artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    artifact_type = row.get("artifact_type") or row.get("stage_type") or "artifact"
    intent_raw = (row["intent_raw"] or "").strip()

    hops = [
        TraceHop(
            type="artifact",
            id=str(row["artifact_id"]),
            label=_short_label(str(artifact_type), prefix="artifact"),
        ),
    ]

    session_id = row["session_id"]
    if session_id is not None:
        session_uuid = UUID(str(session_id))
        hops.append(
            TraceHop(
                type="session",
                id=str(session_uuid),
                label=_session_label(session_uuid),
                href=f"/sessions/{session_uuid}",
            )
        )

    stage_id = row["stage_id"]
    if stage_id is not None:
        stage_uuid = UUID(str(stage_id))
        hops.append(
            TraceHop(
                type="stage",
                id=str(stage_uuid),
                label=_stage_label(stage_uuid),
            )
        )

    cascade_id = row["cascade_id"]
    if cascade_id is not None:
        cascade_uuid = UUID(str(cascade_id))
        hops.append(
            TraceHop(
                type="cascade",
                id=str(cascade_uuid),
                label=_cascade_label(cascade_uuid),
                href=f"/cascades/{cascade_uuid}",
            )
        )

    intent_id = row["intent_id"]
    if intent_id is not None:
        intent_uuid = UUID(str(intent_id))
        hops.append(
            TraceHop(
                type="intent",
                id=str(intent_uuid),
                label=_short_label(intent_raw or str(intent_uuid), prefix="intent"),
            )
        )

    return TraceChain(artifact_id=artifact_id, hops=hops)
