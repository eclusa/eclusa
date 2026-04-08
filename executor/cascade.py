"""Cascade graph readiness, migration apply, completion check, and retry enforcement.

Four public async functions:
  claim_ready_stages     — SKIP LOCKED readiness query (D-01, D-21, Pitfall 1)
  apply_pending_migration — cascade shape migration from proposal table (D-13..D-16, Pitfall 5)
  check_cascade_completion — cascade state machine after terminal stage transition
  retry_stage            — D-19 retry enforcement: max 3 retries per stage, ledger entry per retry
"""

from __future__ import annotations

import json
import asyncpg
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "0002"
MAX_RETRIES = 3


class MaxRetriesExceeded(Exception):
    """Raised by retry_stage when a stage has exhausted its maximum retry count (D-19)."""


async def claim_ready_stages(
    conn: asyncpg.Connection,
    limit: int = 10,
) -> list[dict]:
    """Claim ready stages atomically using SKIP LOCKED (Pitfall 1 — must be inside transaction).

    A stage is ready when:
      1. state = 'pending'
      2. Its cascade is 'active' or 'evergreen'
      3. All depends_on stages are terminal (resolved or skipped)
      4. The row is not locked by another executor (SKIP LOCKED)

    Claimed stages are immediately updated to state='active' inside the same transaction.
    Returns list of dicts with keys: id, type, cascade_id, depends_on, input, retry_count.
    """
    async with conn.transaction():
        rows = await conn.fetch(
            """
            SELECT s.id, s.type, s.cascade_id, s.depends_on, s.input, s.retry_count
            FROM stage s
            JOIN cascade c ON s.cascade_id = c.id
            WHERE s.state = 'pending'
              AND c.state IN ('active', 'evergreen')
              AND NOT EXISTS (
                  SELECT 1 FROM stage dep
                  WHERE dep.id = ANY(s.depends_on)
                    AND dep.state NOT IN ('resolved', 'skipped')
              )
            FOR UPDATE OF s SKIP LOCKED
            LIMIT $1
        """,
            limit,
        )

        if rows:
            stage_ids = [r["id"] for r in rows]
            await conn.execute(
                """
                UPDATE stage SET state = 'active' WHERE id = ANY($1::uuid[])
            """,
                stage_ids,
            )

    return [dict(r) for r in rows]


async def retry_stage(
    conn: asyncpg.Connection,
    stage_id: str,
    actor_id: str,
) -> None:
    """Retry a stage: increment retry_count, reset to 'pending', write ledger entry.

    Enforces D-19: raises MaxRetriesExceeded if retry_count >= MAX_RETRIES (3).
    No DB writes occur if the limit is already reached.
    """
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT retry_count FROM stage WHERE id = $1::uuid FOR UPDATE
        """,
            stage_id,
        )

        if row is None:
            raise ValueError(f"Stage {stage_id} not found")

        current_count = row["retry_count"]
        if current_count >= MAX_RETRIES:
            raise MaxRetriesExceeded(
                f"Stage {stage_id} has exhausted {MAX_RETRIES} retries"
            )

        new_count = current_count + 1

        await conn.execute(
            """
            UPDATE stage SET retry_count = retry_count + 1, state = 'pending'
            WHERE id = $1::uuid
        """,
            stage_id,
        )

        await conn.execute(
            """
            INSERT INTO ledger_entry
                (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT
                gen_random_uuid(),
                s.id,
                s.cascade_id,
                $1::uuid,
                'stage_state_changed',
                jsonb_build_object(
                    'old_state', 'active',
                    'new_state', 'pending',
                    'reason', 'retry',
                    'retry_count', $2::int
                ),
                $3
            FROM stage s WHERE s.id = $4::uuid
        """,
            actor_id,
            new_count,
            SCHEMA_VERSION,
            stage_id,
        )

    logger.debug(f"Stage {stage_id} retried (count now {new_count})")


async def apply_pending_migration(
    conn: asyncpg.Connection,
    system_actor_id: str,
) -> bool:
    """Apply one pending cascade migration proposal.

    Reads cascade_migration_proposal (not ledger) — Pitfall 5 resolution.
    Guards: returns False if any stage in the cascade is 'active' (D-15).
    Validates: all stage IDs in new_shape depends_on arrays must belong to the same cascade (Pitfall 6).
    Writes a 'cascade_migration' ledger entry with old_shape and new_shape.
    Returns True if a migration was applied, False otherwise.
    """
    async with conn.transaction():
        proposal = await conn.fetchrow("""
            SELECT id, cascade_id, new_shape, reason
            FROM cascade_migration_proposal
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)

        if proposal is None:
            return False

        cascade_id = str(proposal["cascade_id"])
        raw_new = proposal["new_shape"]
        new_shape = json.loads(raw_new) if isinstance(raw_new, str) else dict(raw_new)
        reason = proposal["reason"] or ""

        # D-15: do not apply while any stage is 'active' in this cascade
        active_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM stage
            WHERE cascade_id = $1::uuid AND state = 'active'
        """,
            cascade_id,
        )

        if active_count > 0:
            return False

        # Pitfall 6: validate all stage IDs referenced in new_shape depends_on
        # belong to this cascade. The new_shape may contain a "stages" list or
        # any depends_on arrays at any level. We gather all UUIDs referenced.
        referenced_ids: set[str] = set()
        _collect_depends_on_ids(new_shape, referenced_ids)

        if referenced_ids:
            # Get all stage IDs for this cascade
            cascade_stage_rows = await conn.fetch(
                """
                SELECT id::text FROM stage WHERE cascade_id = $1::uuid
            """,
                cascade_id,
            )
            cascade_stage_ids = {str(r["id"]) for r in cascade_stage_rows}

            foreign_ids = referenced_ids - cascade_stage_ids
            if foreign_ids:
                raise ValueError(
                    f"Migration new_shape references stage IDs not in cascade {cascade_id}: "
                    f"{foreign_ids}"
                )

        # Snapshot old shape
        old_cascade = await conn.fetchrow(
            "SELECT shape FROM cascade WHERE id = $1::uuid", cascade_id
        )
        raw_old = old_cascade["shape"]
        old_shape = json.loads(raw_old) if isinstance(raw_old, str) else dict(raw_old)

        # Apply new shape
        await conn.execute(
            """
            UPDATE cascade SET shape = $1::jsonb WHERE id = $2::uuid
        """,
            json.dumps(new_shape),
            cascade_id,
        )

        # Write cascade_migration ledger entry (immutable record of the applied migration)
        await conn.execute(
            """
            INSERT INTO ledger_entry
                (id, cascade_id, actor_id, type, content, schema_version)
            VALUES (
                gen_random_uuid(),
                $1::uuid,
                $2::uuid,
                'cascade_migration',
                jsonb_build_object(
                    'old_shape', $3::jsonb,
                    'new_shape', $4::jsonb,
                    'reason',    $5::text,
                    'applied_at', NOW()::text
                ),
                $6
            )
        """,
            cascade_id,
            system_actor_id,
            json.dumps(old_shape),
            json.dumps(new_shape),
            reason,
            SCHEMA_VERSION,
        )

        # Mark proposal as applied
        await conn.execute(
            """
            UPDATE cascade_migration_proposal
            SET status = 'applied', applied_at = NOW()
            WHERE id = $1::uuid
        """,
            str(proposal["id"]),
        )

    logger.info(f"Applied migration for cascade {cascade_id}: {reason}")
    return True


async def check_cascade_completion(
    conn: asyncpg.Connection,
    cascade_id: str,
    actor_id: str,
) -> None:
    """Check whether all stages are terminal and update cascade state accordingly.

    Terminal states: resolved, skipped, failed.
    Non-terminal states: pending, active, blocked.

    If any non-terminal stage exists → return (cascade still in progress).
    If all terminal:
      - no failures → cascade 'completed' (+ ledger entry)
      - any failures + failure_policy='fail_cascade' → cascade 'failed', pending stages 'skipped'
      - any failures + failure_policy='skip' → pending/blocked stages 'skipped', cascade 'completed'
    """
    async with conn.transaction():
        cascade_row = await conn.fetchrow(
            """
            SELECT state, failure_policy FROM cascade WHERE id = $1::uuid
        """,
            cascade_id,
        )

        if cascade_row is None:
            return

        current_state = str(cascade_row["state"])
        failure_policy = str(cascade_row["failure_policy"])

        # Already in a terminal state — don't overwrite
        if current_state in ("completed", "failed"):
            return

        # Check for any failed stages
        failed_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM stage
            WHERE cascade_id = $1::uuid AND state = 'failed'
        """,
            cascade_id,
        )

        if failed_count > 0:
            # Handle failure based on policy
            if failure_policy == "skip":
                # Skip remaining pending/blocked stages, then complete
                await conn.execute(
                    """
                    UPDATE stage
                    SET state = 'skipped'
                    WHERE cascade_id = $1::uuid AND state IN ('pending', 'blocked', 'active')
                """,
                    cascade_id,
                )

                await conn.execute(
                    """
                    UPDATE cascade
                    SET state = 'completed', completed_at = NOW()
                    WHERE id = $1::uuid
                """,
                    cascade_id,
                )

                await conn.execute(
                    """
                    INSERT INTO ledger_entry
                        (id, cascade_id, actor_id, type, content, schema_version)
                    VALUES (
                        gen_random_uuid(), $1::uuid, $2::uuid,
                        'cascade_state_changed',
                        jsonb_build_object('old_state', $3::text, 'new_state', 'completed', 'policy', 'skip'),
                        $4
                    )
                """,
                    cascade_id,
                    actor_id,
                    current_state,
                    SCHEMA_VERSION,
                )

            else:
                # fail_cascade (default per D-18) or unknown policy
                # Mark cascade failed + skip all remaining stages
                await conn.execute(
                    """
                    UPDATE stage
                    SET state = 'skipped'
                    WHERE cascade_id = $1::uuid AND state IN ('pending', 'blocked', 'active')
                """,
                    cascade_id,
                )

                await conn.execute(
                    """
                    UPDATE cascade SET state = 'failed' WHERE id = $1::uuid
                """,
                    cascade_id,
                )

                await conn.execute(
                    """
                    INSERT INTO ledger_entry
                        (id, cascade_id, actor_id, type, content, schema_version)
                    VALUES (
                        gen_random_uuid(), $1::uuid, $2::uuid,
                        'cascade_state_changed',
                        jsonb_build_object('old_state', $3::text, 'new_state', 'failed', 'policy', $5::text),
                        $4
                    )
                """,
                    cascade_id,
                    actor_id,
                    current_state,
                    SCHEMA_VERSION,
                    failure_policy,
                )

            return

        # No failures — check if all stages are terminal (resolved or skipped)
        non_terminal = await conn.fetchval(
            """
            SELECT COUNT(*) FROM stage
            WHERE cascade_id = $1::uuid
              AND state NOT IN ('resolved', 'skipped', 'failed')
        """,
            cascade_id,
        )

        if non_terminal > 0:
            return  # still in progress

        # All stages terminal, no failures — complete the cascade
        await conn.execute(
            """
            UPDATE cascade
            SET state = 'completed', completed_at = NOW()
            WHERE id = $1::uuid
        """,
            cascade_id,
        )

        await conn.execute(
            """
            INSERT INTO ledger_entry
                (id, cascade_id, actor_id, type, content, schema_version)
            VALUES (
                gen_random_uuid(), $1::uuid, $2::uuid,
                'cascade_state_changed',
                jsonb_build_object('old_state', $3::text, 'new_state', 'completed'),
                $4
            )
        """,
            cascade_id,
            actor_id,
            current_state,
            SCHEMA_VERSION,
        )


def _collect_depends_on_ids(obj: object, result: set[str]) -> None:
    """Recursively walk a JSONB structure and collect all stage IDs found in 'depends_on' arrays.

    Handles both list and dict shapes. Used by apply_pending_migration to validate
    that cross-cascade stage references don't exist in the proposed new shape (Pitfall 6).
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "depends_on" and isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and len(item) > 0:
                        result.add(item)
            else:
                _collect_depends_on_ids(value, result)
    elif isinstance(obj, list):
        for item in obj:
            _collect_depends_on_ids(item, result)
