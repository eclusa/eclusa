from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token
from knowledge.search import SearchResult, hybrid_search

router = APIRouter(prefix="/knowledge", dependencies=[Depends(verify_token)])

__all__ = ["router"]


class KnowledgeFact(BaseModel):
    id: UUID
    subject_id: UUID
    predicate: str
    object_id: UUID | None
    object_value: str | None
    t_valid: datetime
    t_invalid: datetime | None
    t_created: datetime
    t_expired: datetime | None


class CommunityItem(BaseModel):
    id: UUID
    name: str
    member_count: int


_ZERO_EMBEDDING = [0.0] * 1024


def _record_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


@router.get("/entities", response_model=list[SearchResult])
async def search_entities(
    request: Request,
    q: str,
    limit: int = 20,
) -> list[SearchResult]:
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        return await hybrid_search(q, _ZERO_EMBEDDING, conn, limit=limit)


@router.get("/facts", response_model=list[KnowledgeFact])
async def list_facts(request: Request, entity_id: UUID) -> list[KnowledgeFact]:
    pool = request.app.state.pool
    rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          f.id,
          f.source_entity AS subject_id,
          f.predicate,
          f.target_entity AS object_id,
          e.name AS object_value,
          f.t_valid,
          f.t_invalid,
          f.t_created,
          f.t_expired
        FROM fact f
        LEFT JOIN entity e ON e.id = f.target_entity
        WHERE f.source_entity = $1::uuid OR f.target_entity = $1::uuid
        ORDER BY f.t_created DESC, f.id DESC
        """,
            entity_id,
        )
    ]
    return [
        KnowledgeFact(
            id=row["id"],
            subject_id=row["subject_id"],
            predicate=row["predicate"],
            object_id=row["object_id"],
            object_value=row["object_value"],
            t_valid=row["t_valid"],
            t_invalid=row["t_invalid"],
            t_created=row["t_created"],
            t_expired=row["t_expired"],
        )
        for row in rows
    ]


@router.get("/communities", response_model=list[CommunityItem])
async def list_communities(request: Request) -> list[CommunityItem]:
    pool = request.app.state.pool
    rows = [
        _record_dict(row)
        for row in await pool.fetch(
            """
        SELECT
          id,
          name,
          cardinality(entity_ids) AS member_count
        FROM community
        ORDER BY member_count DESC, created_at DESC, id DESC
        """
        )
    ]
    return [
        CommunityItem(
            id=row["id"],
            name=row["name"],
            member_count=int(row["member_count"] or 0),
        )
        for row in rows
    ]
