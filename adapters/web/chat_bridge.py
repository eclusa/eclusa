from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

DEFAULT_CHAT_MODEL = os.environ.get("DEFAULT_MODEL", "openai:glm-5.1")

__all__ = [
    "DEFAULT_CHAT_MODEL",
    "ensure_actor",
    "create_chat_cascade",
    "create_build_chat_cascade",
]


async def ensure_actor(
    conn: asyncpg.Connection,
    identity: str,
    actor_type: str = "human",
) -> str:
    """Return UUID for an actor with the given identity, creating one if needed."""
    row = await conn.fetchrow(
        "SELECT id FROM actor WHERE identity = $1",
        identity,
    )
    if row is not None:
        return str(row["id"])
    actor_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO actor (id, type, identity, permissions)
        VALUES ($1::uuid, $2::actor_type, $3, $4::jsonb)
        """,
        actor_id,
        actor_type,
        identity,
        json.dumps({"resolve_gates": ["*"], "view_costs": True}),
    )
    return actor_id


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, default=str)


async def create_chat_cascade(
    conn: asyncpg.Connection,
    actor_id: str,
    first_message: Any,
    *,
    model_config: dict | None = None,
) -> dict[str, str]:
    """Create a one-stage chat cascade and its starter work session."""
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    first_message_text = _coerce_text(first_message)
    title = first_message_text.strip()[:120] or "Chat session"

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'chat', $2, $3::uuid)
            """,
            intent_id,
            first_message_text,
            actor_id,
        )
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, narrative, state)
            VALUES ($1::uuid, $2::uuid, $3::jsonb, $4, 'active')
            """,
            cascade_id,
            intent_id,
            json.dumps({"mode": "chat", "title": title}),
            title,
        )
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending', $3::jsonb)
            """,
            stage_id,
            cascade_id,
            json.dumps({"mode": "chat", "first_message": first_message_text}),
        )
        await conn.execute(
            """
            INSERT INTO work_session (id, stage_ids, harness_type, model, state, cost, message_history)
            VALUES (
                $1::uuid,
                ARRAY[$2::uuid],
                'chat',
                $3,
                'running',
                '{}'::jsonb,
                '[]'::jsonb
            )
            """,
            session_id,
            stage_id,
            DEFAULT_CHAT_MODEL,
        )

    if model_config is not None:
        await conn.execute(
            "UPDATE cascade SET model_config = $1::jsonb WHERE id = $2::uuid",
            json.dumps(model_config),
            cascade_id,
        )

    return {
        "intent_id": intent_id,
        "cascade_id": cascade_id,
        "stage_id": stage_id,
        "session_id": session_id,
    }


async def create_build_chat_cascade(
    conn: asyncpg.Connection,
    actor_id: str,
    first_message: Any,
    *,
    model_config: dict | None = None,
) -> dict[str, str]:
    """Create a build-mode chat cascade and its starter work session."""
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    first_message_text = _coerce_text(first_message)
    title = first_message_text.strip()[:120] or "Build session"

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'chat', $2, $3::uuid)
            """,
            intent_id,
            first_message_text,
            actor_id,
        )
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, narrative, state)
            VALUES ($1::uuid, $2::uuid, $3::jsonb, $4, 'active')
            """,
            cascade_id,
            intent_id,
            json.dumps({"mode": "build", "title": title}),
            title,
        )
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending', $3::jsonb)
            """,
            stage_id,
            cascade_id,
            json.dumps({"mode": "build", "first_message": first_message_text}),
        )
        await conn.execute(
            """
            INSERT INTO work_session (id, stage_ids, harness_type, model, state, cost, message_history)
            VALUES (
                $1::uuid,
                ARRAY[$2::uuid],
                'build',
                $3,
                'running',
                '{}'::jsonb,
                '[]'::jsonb
            )
            """,
            session_id,
            stage_id,
            DEFAULT_CHAT_MODEL,
        )

    if model_config is not None:
        await conn.execute(
            "UPDATE cascade SET model_config = $1::jsonb WHERE id = $2::uuid",
            json.dumps(model_config),
            cascade_id,
        )

    return {
        "intent_id": intent_id,
        "cascade_id": cascade_id,
        "stage_id": stage_id,
        "session_id": session_id,
    }
