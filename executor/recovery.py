"""Stale active stage recovery — EXEC-04 crash recovery."""

import asyncpg
import logging

logger = logging.getLogger(__name__)

STALE_THRESHOLD_SECONDS = (
    30  # Phase 2: stubs resolve in ms; tune in Phase 3 for long-running sessions
)


async def recover_stale_active_stages(
    conn: asyncpg.Connection,
    threshold_seconds: int = STALE_THRESHOLD_SECONDS,
    actor_id: str | None = None,
) -> list[dict]:
    """Return orphaned active stages to pending state.

    Stages stuck in 'active' longer than threshold_seconds with no resolved_at
    are assumed orphaned by a crashed executor (D-04).
    Each recovery writes a stage_state_changed ledger entry.

    actor_id: optional executor actor UUID. If not provided, falls back to
              the 'system-executor' actor identity lookup. Pass actor_id from
              the executor loop for correct attribution.
    """
    async with conn.transaction():
        rows = await conn.fetch(
            """
            UPDATE stage
            SET state = 'pending'
            WHERE state = 'active'
              AND resolved_at IS NULL
              AND created_at < NOW() - ($1 || ' seconds')::interval
            RETURNING id, cascade_id
        """,
            str(threshold_seconds),
        )
        # Write recovery ledger entries
        for row in rows:
            if actor_id is not None:
                await conn.execute(
                    """
                    INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
                    VALUES (
                        gen_random_uuid(), $1::uuid, $2::uuid, $3::uuid,
                        'stage_state_changed',
                        '{"old_state": "active", "new_state": "pending", "reason": "crash_recovery"}'::jsonb,
                        '0002'
                    )
                """,
                    row["id"],
                    row["cascade_id"],
                    actor_id,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
                    VALUES (
                        gen_random_uuid(), $1::uuid, $2::uuid,
                        (SELECT id FROM actor WHERE identity = 'system-executor' LIMIT 1),
                        'stage_state_changed',
                        '{"old_state": "active", "new_state": "pending", "reason": "crash_recovery"}'::jsonb,
                        '0002'
                    )
                """,
                    row["id"],
                    row["cascade_id"],
                )
        return [dict(r) for r in rows]
