from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from adapters.web.api.auth import verify_token
from adapters.web.chat_bridge import DEFAULT_CHAT_MODEL, create_build_chat_cascade, create_chat_cascade
from harness.refine_agent import RefineContext, build_refine_agent
from harness.message_format import deserialize_history, serialize_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat")

__all__ = ["router", "build_chat_agent"]


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: Any


class ChatRequest(BaseModel):
    model_config = {"populate_by_name": True}

    messages: list[ChatMessage]
    session_id: UUID | None = None
    model: str | None = None
    scc_model_config: dict | None = Field(default=None, alias="model_config")
    mode: Literal["chat", "build"] = "chat"


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False, default=str)


def _to_model_message(message: ChatMessage) -> ModelRequest | ModelResponse:
    text = _message_text(message.content)
    if message.role == "system":
        return ModelRequest(parts=[SystemPromptPart(content=text)])
    if message.role == "user":
        return ModelRequest(parts=[UserPromptPart(content=text)])
    return ModelResponse(parts=[TextPart(content=text)])


def _split_prompt(messages: list[ChatMessage]) -> tuple[list[ModelRequest | ModelResponse], str]:
    if not messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")

    final_message = messages[-1]
    if final_message.role != "user":
        raise HTTPException(status_code=422, detail="last message must be from the user")

    history = [_to_model_message(message) for message in messages[:-1]]
    return history, _message_text(final_message.content)


def _build_system_prompt() -> str:
    return (
        "You are the Eclusa chat orchestration assistant. "
        "Help operators turn natural language into a clear work session."
    )


def build_chat_agent(model: str | None) -> Agent:
    return Agent(model or DEFAULT_CHAT_MODEL, system_prompt=_build_system_prompt())


async def _load_session(pool, session_id: UUID) -> dict[str, Any]:
    row = await pool.fetchrow(
        """
        SELECT id, model, message_history
        FROM work_session
        WHERE id = $1::uuid
        """,
        session_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {key: row[key] for key in row.keys()}


def _stream_chunk(prefix: str, payload: Any) -> str:
    return f"{prefix}:{json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.get("/sessions")
async def list_chat_sessions(
    request: Request,
    payload: dict = Depends(verify_token),
) -> list[dict]:
    """List chat sessions for the current user (most recent first)."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT ws.id, ws.model, ws.state, ws.created_at,
               i.raw AS first_message
        FROM work_session ws
        JOIN stage s ON s.id = ws.stage_ids[1]
        JOIN cascade c ON c.id = s.cascade_id
        JOIN intent i ON i.id = c.intent_id
        WHERE i.source = 'chat'
        ORDER BY ws.created_at DESC
        LIMIT 50
        """,
    )
    return [
        {
            "id": str(row["id"]),
            "model": row["model"],
            "state": row["state"],
            "created_at": row["created_at"].isoformat(),
            "preview": (row["first_message"] or "")[:100],
        }
        for row in rows
    ]


@router.post("", response_model=None)
async def chat(
    request: Request,
    body: ChatRequest,
    payload: dict = Depends(verify_token),
) -> StreamingResponse | JSONResponse:
    pool = request.app.state.pool
    actor_id = str(payload["sub"])
    history, user_prompt = _split_prompt(body.messages)

    session_id = body.session_id

    # Build mode: stream Refine agent conversation (agent has tools to search + create cascade)
    if body.mode == "build":
        async with pool.acquire() as conn:
            # actor_id from JWT sub — actor exists from registration
            if session_id is None:
                created = await create_build_chat_cascade(conn, actor_id, user_prompt, model_config=body.scc_model_config)
                session_id = UUID(created["session_id"])
                intent_id = created["intent_id"]
            else:
                # Continuing an existing build session
                intent_row = await conn.fetchrow(
                    """
                    SELECT i.id FROM intent i
                    JOIN cascade c ON c.intent_id = i.id
                    JOIN stage s ON s.cascade_id = c.id
                    JOIN work_session ws ON ws.stage_ids[1] = s.id
                    WHERE ws.id = $1::uuid
                    """,
                    session_id,
                )
                intent_id = str(intent_row["id"]) if intent_row else str(uuid.uuid4())

        refine_agent = build_refine_agent()

        async def build_stream():
            # AUTH-03: don't hold DB connection during LLM stream; tools acquire their own
            deps = RefineContext(conn=None, actor_id=actor_id, intent_id=intent_id, pool=pool)
            all_messages = []
            async with refine_agent.run_stream(
                user_prompt,
                message_history=history if history else [],
                deps=deps,
            ) as result:
                async for chunk in result.stream_text(delta=True):
                    yield _stream_chunk("0", chunk)
                all_messages = result.all_messages()

            # Short-lived DB write after stream completes
            history_json = serialize_history(all_messages)
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE work_session SET message_history = $1::jsonb WHERE id = $2::uuid",
                    history_json, str(session_id),
                )

            yield _stream_chunk("d", {"finishReason": "stop", "session_id": str(session_id)})

        return StreamingResponse(build_stream(), media_type="text/event-stream")

    session_model = body.model

    if session_id is None:
        async with pool.acquire() as conn:
            # actor_id from JWT sub — actor exists from registration
            created = await create_chat_cascade(conn, actor_id, user_prompt, model_config=body.scc_model_config)
        session_id = UUID(created["session_id"])
        session_model = session_model or DEFAULT_CHAT_MODEL
    else:
        session_row = await _load_session(pool, session_id)
        if not history and session_row["message_history"]:
            raw_history = session_row["message_history"]
            if isinstance(raw_history, str):
                raw_history = json.loads(raw_history)
            history = deserialize_history(raw_history)
        if session_model is None:
            session_model = session_row["model"]

    effective_model = session_model or DEFAULT_CHAT_MODEL
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE work_session SET model = $1 WHERE id = $2::uuid",
            effective_model,
            session_id,
        )

    agent = build_chat_agent(effective_model)

    async def event_stream():
        try:
            async with agent.run_stream(user_prompt, message_history=history) as result:
                async for token in result.stream_text(delta=True, debounce_by=None):
                    if token:
                        yield _stream_chunk("0", token)

                all_messages = result.all_messages()
                history_json = serialize_history(all_messages)
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE work_session
                        SET message_history = $1::jsonb
                        WHERE id = $2::uuid
                        """,
                        json.dumps(history_json),
                        session_id,
                    )

                finish_reason = result.response.finish_reason or "stop"
                yield _stream_chunk(
                    "d",
                    {
                        "finishReason": finish_reason,
                        "sessionId": str(session_id),
                    },
                )
        except Exception as exc:  # pragma: no cover - streaming failure path
            logger.exception("chat stream failed for session %s", session_id)
            yield _stream_chunk(
                "d",
                {
                    "finishReason": "error",
                    "error": str(exc),
                    "sessionId": str(session_id),
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Vercel-AI-UI-Message-Stream": "v1",
            "X-Eclusa-Session-Id": str(session_id),
        },
    )
