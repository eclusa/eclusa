"""harness/claude_code.py — Claude Code work session lifecycle for WORK-07.

Claude Code is an external backend process. The executor does not start or
stop it; this module only creates the work_session row, captures history in the
same platform format as native sessions, and marks completion.
"""

import json
import logging
import uuid
from typing import Any

import asyncpg

from harness.message_format import serialize_history

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_VERSION = "0002"


async def start_claude_code_session(
    conn: asyncpg.Connection,
    stage_id: str,
    intent_id: str,
    cascade_id: str,
    model: str,
    actor_id: str,
    addon: Any = None,
) -> str:
    """Create a Claude Code work_session row and register the proxy session."""
    session_id = str(uuid.uuid4())

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO work_session (id, stage_ids, harness_type, model, state, cost)
            VALUES ($1::uuid, ARRAY[$2::uuid], 'claude_code', $3, 'running', '{}')
            """,
            session_id,
            stage_id,
            model,
        )
        await conn.execute(
            """
            INSERT INTO ledger_entry (
                id, stage_id, cascade_id, session_id, actor_id,
                type, content, schema_version
            )
            VALUES (
                gen_random_uuid(), $1::uuid, $2::uuid, $3::uuid, $4::uuid,
                'work_session_started',
                jsonb_build_object(
                    'session_id', $3::text,
                    'model', $5::text,
                    'stage_id', $1::text,
                    'harness_type', 'claude_code'
                ),
                $6::text
            )
            """,
            stage_id,
            cascade_id,
            session_id,
            actor_id,
            model,
            SYSTEM_SCHEMA_VERSION,
        )

    if addon is not None:
        addon.register_session(
            session_id,
            {
                "intent_id": intent_id,
                "cascade_id": cascade_id,
                "stage_id": stage_id,
            },
        )

    logger.debug(
        "Claude Code session started: %s (model=%s, stage=%s)",
        session_id,
        model,
        stage_id,
    )
    return session_id


async def capture_claude_code_message(
    conn: asyncpg.Connection,
    session_id: str,
    messages: Any,
) -> None:
    """Store Claude Code message history in the same platform format as native."""
    history_json = serialize_history(messages)
    await conn.execute(
        """
        UPDATE work_session
        SET message_history = $1::jsonb
        WHERE id = $2::uuid
        """,
        json.dumps(history_json),
        session_id,
    )


async def complete_claude_code_session(
    conn: asyncpg.Connection,
    session_id: str,
    actor_id: str,
    addon: Any = None,
) -> None:
    """Mark a Claude Code session completed and deregister the proxy session."""
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE work_session
            SET state = 'completed', completed_at = NOW()
            WHERE id = $1::uuid
            """,
            session_id,
        )
        await conn.execute(
            """
            INSERT INTO ledger_entry (
                id, stage_id, cascade_id, session_id, actor_id,
                type, content, schema_version
            )
            SELECT
                gen_random_uuid(),
                ws.stage_ids[1],
                s.cascade_id,
                ws.id,
                $1::uuid,
                'work_session_completed',
                jsonb_build_object(
                    'session_id', ws.id::text,
                    'harness_type', 'claude_code'
                ),
                $2::text
            FROM work_session ws
            LEFT JOIN stage s ON s.id = ws.stage_ids[1]
            WHERE ws.id = $3::uuid
            """,
            actor_id,
            SYSTEM_SCHEMA_VERSION,
            session_id,
        )

    if addon is not None:
        addon.deregister_session(session_id)

    logger.debug("Claude Code session completed: %s", session_id)
