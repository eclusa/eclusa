"""
harness/native.py — Native work session lifecycle for pydantic-ai agents.

Implements start/run/pause/resume/complete for native harness type.
All DB writes use raw asyncpg (same pattern as executor/dispatch.py).
All history serialization uses platform format (ModelMessagesTypeAdapter).
D-01, D-02, D-03, D-04, D-05, D-06, D-11, D-23, D-26, D-27.
"""

import json
import logging
import time
import uuid
from typing import Any

import asyncpg
from pydantic_ai import Agent

from harness.message_format import serialize_history
from harness.snapshot import SnapshotStore

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_VERSION = "0002"


async def start_work_session(
    conn: asyncpg.Connection,
    stage_id: str,
    intent_id: str,
    cascade_id: str,
    model: str,
    actor_id: str,
    addon: Any = None,
) -> str:
    """Create a new work_session DB record with state='running' and a ledger entry.

    D-01, D-02: native harness, start lifecycle.
    D-11: register with proxy addon after DB writes.

    Returns session_id (str).
    """
    session_id = str(uuid.uuid4())

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO work_session (id, stage_ids, harness_type, model, state, cost)
            VALUES ($1::uuid, ARRAY[$2::uuid], 'native', $3, 'running', '{}')
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
                jsonb_build_object('session_id', $3::text, 'model', $5::text, 'stage_id', $1::text),
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
        "Work session started: %s (model=%s, stage=%s)", session_id, model, stage_id
    )
    return session_id


async def run_session_turn(
    conn: asyncpg.Connection,
    session_id: str,
    agent: Agent,
    user_message: str,
    message_history: Any = None,
) -> tuple[Any, list]:
    """Run one pydantic-ai Agent turn, write message_history + cost to DB.

    D-03: message_history stored in platform format (serialize_history).
    D-27: cost accumulated per turn.

    Returns (result.output, result.all_messages()).
    """
    start = time.monotonic()

    result = await agent.run(
        user_message,
        message_history=message_history if message_history is not None else [],
    )

    wall_time_ms = int((time.monotonic() - start) * 1000)
    all_messages = result.all_messages()
    history_json = serialize_history(all_messages)

    usage = result.usage()
    cost_delta = {
        "tokens_in": usage.input_tokens or 0,
        "tokens_out": usage.output_tokens or 0,
        "api_calls": 1,
        "tool_calls": 0,
        "wall_time_ms": wall_time_ms,
        "estimated_usd": 0,
    }

    async with conn.transaction():
        # Fetch current cost under lock, merge Python-side, write back.
        row = await conn.fetchrow(
            "SELECT cost FROM work_session WHERE id = $1::uuid FOR UPDATE",
            session_id,
        )
        current_cost = row["cost"] if row and row["cost"] else {}
        if isinstance(current_cost, str):
            current_cost = json.loads(current_cost)

        merged_cost = {
            "tokens_in": (current_cost.get("tokens_in") or 0)
            + cost_delta["tokens_in"],
            "tokens_out": (current_cost.get("tokens_out") or 0)
            + cost_delta["tokens_out"],
            "api_calls": (current_cost.get("api_calls") or 0)
            + cost_delta["api_calls"],
            "tool_calls": (current_cost.get("tool_calls") or 0)
            + cost_delta["tool_calls"],
            "wall_time_ms": (current_cost.get("wall_time_ms") or 0)
            + cost_delta["wall_time_ms"],
            "estimated_usd": (current_cost.get("estimated_usd") or 0)
            + cost_delta["estimated_usd"],
        }

        await conn.execute(
            """
            UPDATE work_session
            SET message_history = $1::jsonb, cost = $2::jsonb
            WHERE id = $3::uuid
            """,
            json.dumps(history_json),
            json.dumps(merged_cost),
            session_id,
        )

    logger.debug(
        "Session turn complete: %s (tokens_in=%d, tokens_out=%d)",
        session_id,
        cost_delta["tokens_in"],
        cost_delta["tokens_out"],
    )
    return result.output, all_messages


async def pause_work_session(
    conn: asyncpg.Connection,
    session_id: str,
    snapshot_store: SnapshotStore,
    actor_id: str | None = None,
) -> None:
    """Write snapshot to filesystem, set state='paused', insert ledger entry.

    D-03: reads message_history from DB (platform format).
    D-04: saves snapshot via SnapshotStore (filesystem-backed, swappable).
    """
    row = await conn.fetchrow(
        "SELECT message_history FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    message_history_raw = (
        row["message_history"] if row and row["message_history"] else []
    )

    if isinstance(message_history_raw, str):
        message_history_raw = json.loads(message_history_raw)

    snapshot_path = snapshot_store.save_snapshot(session_id, message_history_raw)

    if actor_id is None:
        actor_row = await conn.fetchrow(
            """
            SELECT actor_id
            FROM ledger_entry
            WHERE session_id = $1::uuid AND type = 'work_session_started'
            ORDER BY created_at ASC
            """,
            session_id,
        )
        if actor_row is None:
            raise ValueError(f"No work_session_started ledger entry found for {session_id}")
        actor_id = str(actor_row["actor_id"])

    async with conn.transaction():
        await conn.execute(
            """
            UPDATE work_session
            SET state = 'paused', paused_at = NOW(), workspace_ref = $1
            WHERE id = $2::uuid
            """,
            snapshot_path,
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
                $4::uuid,
                'work_session_paused',
                jsonb_build_object('session_id', ws.id::text, 'snapshot_path', $1::text),
                $2::text
            FROM work_session ws
            LEFT JOIN stage s ON s.id = ws.stage_ids[1]
            WHERE ws.id = $3::uuid
            """,
            snapshot_path,
            SYSTEM_SCHEMA_VERSION,
            session_id,
            actor_id,
        )

    logger.debug("Work session paused: %s (snapshot=%s)", session_id, snapshot_path)


async def resume_work_session(
    conn: asyncpg.Connection,
    session_id: str,
    new_model: str | None = None,
    snapshot_store: SnapshotStore | None = None,
    actor_id: str | None = None,
) -> list:
    """Load snapshot, optionally swap model, set state='running', return restored messages.

    D-04: loads snapshot from SnapshotStore.
    D-05: harness doesn't know it was paused — history passed to next run_session_turn call.
    D-23, D-24, D-25, D-26: model hot-swap records [{from, to, reason, swapped_at}].

    Returns restored_messages list (platform format) for passing to next run_session_turn call.
    """
    if snapshot_store is None:
        snapshot_store = SnapshotStore()

    row = await conn.fetchrow(
        "SELECT workspace_ref, model, model_swaps FROM work_session WHERE id = $1::uuid",
        session_id,
    )
    if row is None:
        raise ValueError(f"No work_session found for id={session_id}")

    workspace_ref = row["workspace_ref"]
    current_model = row["model"]

    # Load snapshot: prefer explicit workspace_ref path, fall back to session_id key
    snapshot_data: list[dict]
    if workspace_ref:
        from pathlib import Path as _Path

        try:
            snapshot_data = json.loads(_Path(workspace_ref).read_text(encoding="utf-8"))
        except FileNotFoundError:
            snapshot_data = snapshot_store.load_snapshot(session_id)
    else:
        snapshot_data = snapshot_store.load_snapshot(session_id)

    if actor_id is None:
        actor_row = await conn.fetchrow(
            """
            SELECT actor_id
            FROM ledger_entry
            WHERE session_id = $1::uuid AND type = 'work_session_started'
            ORDER BY created_at ASC
            """,
            session_id,
        )
        if actor_row is None:
            raise ValueError(f"No work_session_started ledger entry found for {session_id}")
        actor_id = str(actor_row["actor_id"])

    async with conn.transaction():
        if new_model is not None and new_model != current_model:
            # Parse existing model_swaps
            model_swaps_raw = row["model_swaps"]
            if isinstance(model_swaps_raw, str):
                model_swaps: list = json.loads(model_swaps_raw)
            elif model_swaps_raw is None:
                model_swaps = []
            else:
                model_swaps = list(model_swaps_raw)

            swap_record = {
                "from": current_model,
                "to": new_model,
                "reason": "resume with model swap",
                "swapped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            model_swaps.append(swap_record)

            await conn.execute(
                """
                UPDATE work_session
                SET model = $1, model_swaps = $2::jsonb,
                    state = 'running', resumed_at = NOW(), workspace_ref = NULL
                WHERE id = $3::uuid
                """,
                new_model,
                json.dumps(model_swaps),
                session_id,
            )
        else:
            await conn.execute(
                """
                UPDATE work_session
                SET state = 'running', resumed_at = NOW(), workspace_ref = NULL
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
                $4::uuid,
                'work_session_resumed',
                jsonb_build_object('session_id', ws.id::text, 'new_model', $1::text),
                $2::text
            FROM work_session ws
            LEFT JOIN stage s ON s.id = ws.stage_ids[1]
            WHERE ws.id = $3::uuid
            """,
            new_model,
            SYSTEM_SCHEMA_VERSION,
            session_id,
            actor_id,
        )

    logger.debug("Work session resumed: %s (new_model=%s)", session_id, new_model)
    return snapshot_data


async def complete_work_session(
    conn: asyncpg.Connection,
    session_id: str,
    actor_id: str,
    addon: Any = None,
) -> None:
    """Mark work session completed, insert ledger entry, deregister from proxy addon.

    D-11: deregister_session after DB writes.
    """
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
                jsonb_build_object('session_id', ws.id::text),
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

    logger.debug("Work session completed: %s", session_id)
