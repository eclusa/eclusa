"""Stage dispatch — Phase 5 update.

dispatch_narrowing: marks stage resolved immediately (Phase 3 replaces with real work session).
surface_gate: marks stage blocked, writes gate_surfaced ledger entry, dispatches to adapter.
resolve_gate: marks gate resolved, writes gate_resolved ledger entry, fires scoped pg_notify.
dispatch_stage: router — calls dispatch_narrowing or surface_gate based on stage type.
"""

import json
import os

import asyncpg
import logging

from adapters.protocol import GateContext
from adapters.registry import registry
from executor.scc_handlers import (
    dispatch_scc_cohere,
    dispatch_scc_derive,
    dispatch_scc_fanout,
    dispatch_scc_formalize,
    dispatch_scc_generate,
    dispatch_scc_match,
    dispatch_scc_refine,
)
from executor.ship import dispatch_scc_ship

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_VERSION = "0002"


class GateAlreadyResolvedError(Exception):
    """Raised when a gate has already been resolved."""


async def dispatch_narrowing(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    """Route SCC narrowing stages; resolve legacy narrowing stages immediately."""
    stage_input = stage.get("input") or {}
    if isinstance(stage_input, str):
        stage_input = json.loads(stage_input)
    scc_stage = stage_input.get("scc_stage")

    if scc_stage == "refine":
        await dispatch_scc_refine(conn, stage, actor_id)
    elif scc_stage == "intent_validation_fanout":
        await dispatch_scc_fanout(conn, stage, actor_id)
    elif scc_stage == "match":
        await dispatch_scc_match(conn, stage, actor_id)
    elif scc_stage == "cohere":
        await dispatch_scc_cohere(conn, stage, actor_id)
    elif scc_stage == "formalize":
        await dispatch_scc_formalize(conn, stage, actor_id)
    elif scc_stage == "derive":
        await dispatch_scc_derive(conn, stage, actor_id)
    elif scc_stage == "generate":
        await dispatch_scc_generate(conn, stage, actor_id)
    elif scc_stage == "ship":
        await dispatch_scc_ship(conn, stage, actor_id)
    else:
        await _resolve_stage_immediately(conn, stage, actor_id)


async def _resolve_stage_immediately(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    """Backward-compatible immediate resolve for non-SCC narrowing stages."""
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE stage SET state = 'resolved', resolved_at = NOW(), resolved_by = $1::uuid
            WHERE id = $2::uuid
            """,
            actor_id,
            stage["id"],
        )
        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'stage_state_changed',
                   jsonb_build_object('old_state', 'active', 'new_state', 'resolved', 'note', 'legacy stub'),
                   $2
            FROM stage s WHERE s.id = $3::uuid
            """,
            actor_id,
            SYSTEM_SCHEMA_VERSION,
            stage["id"],
        )
    logger.debug(f"[legacy] Resolved narrowing stage {stage['id']}")


async def surface_gate(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    """Surface a gate stage: mark blocked, write ledger entry, dispatch to adapter (EXEC-06)."""
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE stage SET state = 'blocked' WHERE id = $1::uuid
        """,
            stage["id"],
        )
        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'gate_surfaced',
                   jsonb_build_object('stage_id', s.id::text),
                   $2
            FROM stage s WHERE s.id = $3::uuid
        """,
            actor_id,
            SYSTEM_SCHEMA_VERSION,
            stage["id"],
        )

    # Build GateContext and dispatch to registered adapter
    stage_input = stage.get("input") or {}
    if isinstance(stage_input, str):
        stage_input = json.loads(stage_input)
    base_url = os.environ.get("ECLUSA_BASE_URL", "http://localhost:8000")
    context = GateContext(
        cascade_id=str(stage["cascade_id"]),
        stage_id=str(stage["id"]),
        gate_description=stage_input.get("gate_description", str(stage["id"])),
        model_recommendation=stage_input.get("model_recommendation"),
        eligible_actor_ids=stage_input.get("eligible_actor_ids", []),
        resolve_url=f"{base_url}/gates/{stage['id']}/resolve",
    )
    channel_type = stage_input.get("channel_type", "email")
    adapter = registry.get(channel_type)
    if adapter is None:
        logger.warning(
            f"No adapter registered for channel_type={channel_type!r}, "
            f"gate {stage['id']} surfaced to DB only"
        )
    else:
        await adapter.surface_gate(context)

    logger.info(f"Gate surfaced: stage {stage['id']} via {channel_type}")


async def resolve_gate(conn: asyncpg.Connection, stage_id: str, actor_id: str) -> None:
    """Mark gate resolved, write ledger entry, fire both pg_notify channels (EXEC-07, D-05)."""
    async with conn.transaction():
        # Fetch cascade_id for scoped NOTIFY (D-05)
        row = await conn.fetchrow(
            "SELECT cascade_id FROM stage WHERE id = $1::uuid", stage_id
        )
        if row is None:
            raise ValueError(f"Stage not found: {stage_id}")
        cascade_id = str(row["cascade_id"])

        updated = await conn.fetchrow(
            """
            UPDATE stage
            SET state = 'resolved', resolved_at = NOW(), resolved_by = $1::uuid
            WHERE id = $2::uuid AND type = 'gate' AND state = 'blocked'
            RETURNING id
            """,
            actor_id,
            stage_id,
        )
        if updated is None:
            raise GateAlreadyResolvedError(
                f"Gate {stage_id} is not in 'blocked' state"
            )
        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'gate_resolved',
                   jsonb_build_object('stage_id', s.id::text),
                   $2
            FROM stage s WHERE s.id = $3::uuid
        """,
            actor_id,
            SYSTEM_SCHEMA_VERSION,
            stage_id,
        )

        # Fire catch-all wake signal + cascade-scoped signal (D-05)
        payload = json.dumps({"stage_id": stage_id, "cascade_id": cascade_id})
        await conn.execute("SELECT pg_notify($1, $2)", "stage_changed", payload)
        await conn.execute(
            "SELECT pg_notify($1, $2)", f"stage_changed:{cascade_id}", payload
        )


async def dispatch_stage(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    """Route stage to correct handler based on type (D-05, D-06)."""
    if stage["type"] == "narrowing":
        await dispatch_narrowing(conn, stage, actor_id)
    elif stage["type"] == "gate":
        stage_input = stage.get("input") or {}
        if isinstance(stage_input, str):
            stage_input = json.loads(stage_input)
        auto_resolve = stage_input.get("auto_resolve") == "true"
        if auto_resolve:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE stage SET state = 'resolved', resolved_at = NOW(), resolved_by = $1::uuid
                    WHERE id = $2::uuid
                """,
                    actor_id,
                    stage["id"],
                )
                await conn.execute(
                    """
                    INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
                    SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                           'gate_auto_resolved',
                           jsonb_build_object('stage_id', s.id::text),
                           $2
                    FROM stage s WHERE s.id = $3::uuid
                """,
                    actor_id,
                    SYSTEM_SCHEMA_VERSION,
                    stage["id"],
                )
        else:
            await surface_gate(conn, stage, actor_id)
