from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token
from adapters.web.chat_bridge import ensure_actor  # kept for webhook/system actors
from executor.scc import create_scc_cascade

router = APIRouter(prefix="/scc")

__all__ = ["router"]


class SccCreateRequest(BaseModel):
    intent_text: str
    model_config_override: dict | None = None


class SccCreateResponse(BaseModel):
    cascade_id: str
    intent_id: str


@router.post("/create", response_model=SccCreateResponse)
async def create_scc(
    request: Request,
    body: SccCreateRequest,
    payload: dict = Depends(verify_token),
) -> SccCreateResponse:
    """Create a 7-stage SCC cascade programmatically. TRIGGER-03."""
    if not body.intent_text or not body.intent_text.strip():
        raise HTTPException(status_code=422, detail="intent_text must not be empty")

    pool = request.app.state.pool
    actor_id = str(payload["sub"])

    async with pool.acquire() as conn:
        intent_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api', $2, $3::uuid)
            """,
            intent_id,
            body.intent_text.strip(),
            actor_id,
        )
        cascade_id = await create_scc_cascade(intent_id, actor_id, conn)

        if body.model_config_override is not None:
            await conn.execute(
                "UPDATE cascade SET model_config = $1::jsonb WHERE id = $2::uuid",
                json.dumps(body.model_config_override),
                cascade_id,
            )

    return SccCreateResponse(cascade_id=cascade_id, intent_id=intent_id)
