"""Executor main loop — Phase 2.

run_executor(asyncpg_dsn, psycopg_dsn, actor_identity): entry point.
Starts two asyncio tasks:
  1. _listen_for_changes: dedicated psycopg3 LISTEN connection, sets wake_event on NOTIFY
  2. _poll_loop: SKIP LOCKED claim, dispatch, backoff, startup recovery

Design principles:
  - Zero in-memory state: all stage ownership is in the DB (D-22)
  - SKIP LOCKED is the only coordination (D-21)
  - LISTEN/NOTIFY is a wake-hint, never the sole trigger (D-02)
  - Crash-restart recovers from DB (EXEC-04)
"""

import asyncio
import json
import uuid

import asyncpg
import psycopg
import logging

from executor.cascade import (
    claim_ready_stages,
    apply_pending_migration,
    check_cascade_completion,
    retry_stage,
    MaxRetriesExceeded,
)
from executor.concurrency import controller as concurrency_controller
from executor.dispatch import dispatch_stage
from executor.propagation import inject_upstream_context
from executor.recovery import recover_stale_active_stages

logger = logging.getLogger(__name__)

_INITIAL_BACKOFF = 1.0  # D-03
_MAX_BACKOFF = 5.0  # D-03


async def _resolve_actor_id(dsn: str, identity: str) -> str:
    """Resolve an actor identity string to its UUID, creating the actor if needed.

    Uses a single connection (not the pool) because the pool hasn't been created yet.
    Pattern mirrors adapters.web.chat_bridge.ensure_actor but with type='system'.
    """
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT id FROM actor WHERE identity = $1",
            identity,
        )
        if row is not None:
            actor_uuid = str(row["id"])
            logger.info(f"Executor actor resolved: {identity} -> {actor_uuid}")
            return actor_uuid

        actor_uuid = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO actor (id, type, identity, permissions)
            VALUES ($1::uuid, $2::actor_type, $3, $4::jsonb)
            """,
            actor_uuid,
            "system",
            identity,
            json.dumps({"resolve_gates": ["*"], "view_costs": True}),
        )
        logger.info(f"Executor actor resolved: {identity} -> {actor_uuid} (created)")
        return actor_uuid
    finally:
        await conn.close()


async def run_executor(asyncpg_dsn: str, psycopg_dsn: str, actor_identity: str) -> None:
    """Start the executor poll loop and LISTEN/NOTIFY listener as concurrent asyncio tasks."""
    # Resolve identity string to UUID before any pool or DB operation
    actor_id = await _resolve_actor_id(asyncpg_dsn, actor_identity)

    pool = await asyncpg.create_pool(asyncpg_dsn, min_size=2, max_size=10)

    # Log startup with connection target (mask credentials)
    host_info = asyncpg_dsn.split("@")[1].split("/")[0] if "@" in asyncpg_dsn else "unknown"
    logger.info(f"Executor started: pool connected to {host_info}, actor={actor_id}")

    wake_event = asyncio.Event()

    listen_task = asyncio.create_task(_listen_for_changes(psycopg_dsn, wake_event))
    poll_task = asyncio.create_task(_poll_loop(pool, wake_event, actor_id))

    try:
        await asyncio.gather(listen_task, poll_task)
    finally:
        await pool.close()


async def _listen_for_changes(psycopg_dsn: str, wake_event: asyncio.Event) -> None:
    """Dedicated LISTEN connection. Sets wake_event on any NOTIFY (D-02).

    Uses a separate connection to avoid lock contention with the poll loop
    (RESEARCH.md Pitfall 2 — NOTIFY outside transaction on dedicated connection).
    """
    async with await psycopg.AsyncConnection.connect(
        psycopg_dsn, autocommit=True
    ) as conn:
        await conn.execute("LISTEN stage_changed")
        async for _ in conn.notifies():
            wake_event.set()


async def _poll_loop(
    pool: asyncpg.Pool, wake_event: asyncio.Event, actor_id: str
) -> None:
    """Main poll loop: SKIP LOCKED claim, dispatch, backoff (D-03), startup recovery (EXEC-04)."""
    backoff = _INITIAL_BACKOFF
    poll_counter = 0

    # Startup: reclaim orphaned stages (EXEC-04)
    async with pool.acquire() as conn:
        recovered = await recover_stale_active_stages(conn, actor_id=actor_id)
        if recovered:
            logger.info(
                f"Startup recovery: reclaimed {len(recovered)} stale active stages"
            )

    while True:
        if poll_counter % 10 == 0:
            logger.info(f"Executor heartbeat: poll cycle {poll_counter}, backoff={backoff:.1f}s")
        poll_counter += 1

        async with pool.acquire() as conn:
            await apply_pending_migration(conn, actor_id)
            stages = await claim_ready_stages(conn)

        if stages:
            backoff = _INITIAL_BACKOFF  # reset on successful claim (D-03)
            for stage in stages:
                asyncio.create_task(_dispatch_and_check(pool, stage, actor_id))
        else:
            try:
                await asyncio.wait_for(wake_event.wait(), timeout=backoff)
                backoff = _INITIAL_BACKOFF  # NOTIFY arrived: reset (D-03)
            except asyncio.TimeoutError:
                backoff = min(backoff * 2, _MAX_BACKOFF)  # D-03: cap at 5s
            finally:
                wake_event.clear()


def _resolve_stage_model(stage: dict) -> str | None:
    """Resolve which LLM model a stage will use, for concurrency control.

    Returns None for non-SCC stages (gates, legacy narrowing) that don't call an LLM.
    """
    stage_input = stage.get("input") or {}
    if isinstance(stage_input, str):
        stage_input = json.loads(stage_input)
    scc_stage = stage_input.get("scc_stage")
    if not scc_stage:
        return None
    from executor.scc_handlers import _resolve_model
    return _resolve_model(scc_stage)


async def _mark_stage_failed(
    conn: asyncpg.Connection, stage: dict, actor_id: str, reason: str
) -> None:
    """Mark a stage as failed after retries exhausted."""
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE stage SET state = 'failed', resolved_at = NOW(), resolved_by = $1::uuid
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
                   jsonb_build_object('old_state', 'active', 'new_state', 'failed', 'reason', $2::text),
                   '0002'
            FROM stage s WHERE s.id = $3::uuid
            """,
            actor_id,
            reason,
            stage["id"],
        )


async def _dispatch_and_check(pool: asyncpg.Pool, stage: dict, actor_id: str) -> None:
    """Dispatch one stage and check cascade completion. Runs as a task per stage.

    Acquires a per-model semaphore before dispatch to prevent rate-limit stalls.
    On failure, reverts stage to pending for retry (up to MAX_RETRIES).
    """
    model = _resolve_stage_model(stage)
    if model:
        await concurrency_controller.acquire(model)
    try:
        async with pool.acquire() as conn:
            await inject_upstream_context(conn, stage)
            await dispatch_stage(conn, stage, actor_id)
        async with pool.acquire() as conn:
            await check_cascade_completion(conn, str(stage["cascade_id"]), actor_id)
    except Exception:
        logger.exception(f"Dispatch failed for stage {stage['id']}")
        try:
            async with pool.acquire() as conn:
                await retry_stage(conn, str(stage["id"]), actor_id)
            logger.info(f"Stage {stage['id']} reverted to pending for retry")
        except MaxRetriesExceeded:
            logger.error(f"Stage {stage['id']} exhausted retries")
            async with pool.acquire() as conn:
                await _mark_stage_failed(
                    conn, stage, actor_id, "max retries exhausted after dispatch failure"
                )
            async with pool.acquire() as conn:
                await check_cascade_completion(conn, str(stage["cascade_id"]), actor_id)
        except Exception:
            logger.exception(f"Failed to revert stage {stage['id']}")
    finally:
        if model:
            concurrency_controller.release(model)


async def single_poll_cycle(pool: asyncpg.Pool, actor_id: str) -> list[dict]:
    """Run one claim+dispatch cycle. Used in tests and for controlled iteration.

    Returns the list of stages that were claimed and dispatched in this cycle.
    """
    async with pool.acquire() as conn:
        await apply_pending_migration(conn, actor_id)
        stages = await claim_ready_stages(conn)

    for stage in stages:
        async with pool.acquire() as conn:
            await inject_upstream_context(conn, stage)
            await dispatch_stage(conn, stage, actor_id)
        async with pool.acquire() as conn:
            await check_cascade_completion(conn, str(stage["cascade_id"]), actor_id)

    return stages


__all__ = ["run_executor", "single_poll_cycle", "_INITIAL_BACKOFF", "_MAX_BACKOFF"]
