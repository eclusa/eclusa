"""
fan_out/db.py -- Fan-out DB persistence and verdict routing.

Orchestrates: run fan-out passes -> create DB records -> auto-resolve or surface gate.

FAN-03: auto-resolve converged -> UPDATE stage state='resolved' + gate_auto_resolved ledger entry.
FAN-04: surface diverged/partial -> UPDATE stage state='blocked' + gate_surfaced ledger entry.
"""

import json
import logging
import uuid
from typing import Any

import asyncpg

from fan_out.dispatcher import run_fan_out
from judgment.pass_ import VerdictModel, create_judgment_pass_record

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_VERSION = "0002"


async def run_fan_out_with_db(
    conn: asyncpg.Connection,
    stage_id: str,
    models: list[str],
    prepared_context: str,
    prompt: str,
    context_hash: str,
    actor_id: str,
) -> str:
    """Orchestrate a full fan-out evaluation with DB persistence.

    1. INSERT fan_out record (incomplete)
    2. Fire n judgment passes in parallel via run_fan_out()
    3. CREATE judgment_pass records for each model
    4. UPDATE fan_out with passes, convergence matrix, verdict
    5. Route: auto-resolve if converged, surface gate if diverged/partial

    Returns fan_out.id.
    """
    fan_out_id = str(uuid.uuid4())
    context_ref = f"inline:{context_hash}"

    async with conn.transaction():
        # INSERT fan_out record
        await conn.execute(
            """
            INSERT INTO fan_out (id, stage_id, context_ref, prompt, passes, created_at)
            VALUES ($1::uuid, $2::uuid, $3, $4, '{}', NOW())
        """,
            fan_out_id,
            stage_id,
            context_ref,
            prompt,
        )

        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'fan_out_created',
                   jsonb_build_object('fan_out_id', $2::text),
                   $3
            FROM stage s WHERE s.id = $4::uuid
        """,
            actor_id,
            fan_out_id,
            SYSTEM_SCHEMA_VERSION,
            stage_id,
        )

    # Fire passes outside transaction -- each pass is its own async call
    verdicts, verdict_state, matrix = await run_fan_out(
        models, prepared_context, prompt, context_hash
    )

    # Create judgment_pass records and collect IDs
    pass_ids: list[str] = []
    for model, verdict in zip(models, verdicts):
        pass_id = await create_judgment_pass_record(
            conn=conn,
            stage_id=stage_id,
            model=model,
            context_ref=context_ref,
            context_hash=context_hash,
            prompt=prompt,
            verdict=verdict,
            actor_id=actor_id,
        )
        pass_ids.append(pass_id)

    # UPDATE fan_out with results
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE fan_out
            SET passes = $1::uuid[],
                convergence = $2::jsonb,
                verdict = $3::fan_out_verdict,
                completed_at = NOW()
            WHERE id = $4::uuid
        """,
            pass_ids,
            json.dumps(matrix),
            verdict_state,
            fan_out_id,
        )

        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'fan_out_completed',
                   jsonb_build_object('fan_out_id', $2::text, 'verdict', $3::text, 'model_count', $4::int),
                   $5
            FROM stage s WHERE s.id = $6::uuid
        """,
            actor_id,
            fan_out_id,
            verdict_state,
            len(models),
            SYSTEM_SCHEMA_VERSION,
            stage_id,
        )

    # Route based on verdict
    if verdict_state == "converged":
        await resolve_fan_out_stage(conn, stage_id, actor_id, fan_out_id)
        logger.info(
            "Fan-out %s converged -- stage %s auto-resolved", fan_out_id, stage_id
        )
    else:
        # partial and diverged both surface a gate (D-21, D-22)
        await surface_fan_out_gate(
            conn,
            stage_id,
            actor_id,
            fan_out_id,
            verdict_state,
            verdicts,
            models,
            matrix,
        )
        logger.info(
            "Fan-out %s %s -- gate surfaced for stage %s",
            fan_out_id,
            verdict_state,
            stage_id,
        )

    return fan_out_id


async def resolve_fan_out_stage(
    conn: asyncpg.Connection,
    stage_id: str,
    actor_id: str,
    fan_out_id: str,
) -> None:
    """Auto-resolve stage when fan-out converges. FAN-03."""
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE stage SET state = 'resolved', resolved_at = NOW(), resolved_by = $1::uuid
            WHERE id = $2::uuid
        """,
            actor_id,
            stage_id,
        )
        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'gate_auto_resolved',
                   jsonb_build_object('stage_id', s.id::text, 'fan_out_id', $2::text, 'verdict', 'converged'),
                   $3
            FROM stage s WHERE s.id = $4::uuid
        """,
            actor_id,
            fan_out_id,
            SYSTEM_SCHEMA_VERSION,
            stage_id,
        )


async def surface_fan_out_gate(
    conn: asyncpg.Connection,
    stage_id: str,
    actor_id: str,
    fan_out_id: str,
    verdict_state: str,
    verdicts: list[VerdictModel],
    models: list[str],
    matrix: dict[str, Any],
) -> None:
    """Surface a gate when fan-out diverges or reaches partial convergence. FAN-04."""
    per_model = [
        {
            "model": model,
            "decision": verdict.decision,
            "confidence": verdict.confidence,
            "rationale": verdict.rationale,
            "conditions": verdict.conditions,
        }
        for model, verdict in zip(models, verdicts)
    ]
    divergence_context: dict[str, Any] = {
        "fan_out_id": fan_out_id,
        "verdict_state": verdict_state,
        "per_model": per_model,
        "convergence_matrix": matrix,
    }

    async with conn.transaction():
        await conn.execute(
            """
            UPDATE stage SET state = 'blocked' WHERE id = $1::uuid
        """,
            stage_id,
        )
        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'gate_surfaced',
                   jsonb_build_object(
                       'stage_id', s.id::text,
                       'fan_out_id', $2::text,
                       'verdict', $3::text,
                       'divergence_context', $4::jsonb
                   ),
                   $5
            FROM stage s WHERE s.id = $6::uuid
        """,
            actor_id,
            fan_out_id,
            verdict_state,
            json.dumps(divergence_context),
            SYSTEM_SCHEMA_VERSION,
            stage_id,
        )
