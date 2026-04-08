"""knowledge/facts.py — Bi-temporal fact creation with edge invalidation (KG-03, KG-04).

Facts are edges between entities with four timestamps:
- t_valid / t_invalid: event timeline (when fact was true in the world)
- t_created / t_expired: transactional timeline (when system learned/superseded it)

Edge invalidation: when a new fact contradicts an existing fact (same entity pair,
similar predicate embedding), the old fact's t_invalid is set rather than deleting
the row — the append-only invariant applies to facts too (KG-04).
"""

import logging
from datetime import datetime, timezone

import asyncpg

logger = logging.getLogger(__name__)

INVALIDATION_THRESHOLD = 0.90  # cosine similarity threshold for contradiction detection


async def create_fact_with_invalidation(
    conn: asyncpg.Connection,
    source_entity: str,
    target_entity: str,
    predicate: str,
    embedding: list[float] | None,
    t_valid: datetime,
    source_episodes: list[str],
) -> str:
    """Create a new fact row. Invalidates any prior fact on same entity pair
    with a semantically contradicting predicate (detected by high embedding similarity).

    Old facts are preserved with t_invalid set — they are NOT deleted (KG-04).

    Args:
        conn: asyncpg database connection
        source_entity: UUID string of the source entity
        target_entity: UUID string of the target entity
        predicate: human-readable relation description
        embedding: 1024-dim vector for similarity comparison, or None
        t_valid: world-time when fact became true
        source_episodes: list of episode UUID strings that support this fact

    Returns:
        UUID string of the newly created fact row
    """
    now = datetime.now(timezone.utc)

    async with conn.transaction():
        # Step 1: find similar existing facts between same entities (only if embedding provided)
        if embedding is not None:
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            similar = await conn.fetch(
                """
                SELECT id FROM fact
                WHERE source_entity = $1::uuid
                  AND target_entity = $2::uuid
                  AND t_invalid IS NULL
                  AND embedding IS NOT NULL
                  AND 1 - (embedding <=> $3::vector) > $4
                """,
                source_entity,
                target_entity,
                embedding_str,
                INVALIDATION_THRESHOLD,
            )
            # Step 2: invalidate contradicting facts (set t_invalid, do not delete)
            for row in similar:
                logger.debug(
                    "Invalidating fact %s (contradicted by new fact on %s -> %s)",
                    row["id"],
                    source_entity,
                    target_entity,
                )
                await conn.execute(
                    "UPDATE fact SET t_invalid = $1 WHERE id = $2::uuid",
                    now,
                    str(row["id"]),
                )

        # Step 3: insert new fact with all four bi-temporal timestamps
        embedding_param = (
            "[" + ",".join(str(v) for v in embedding) + "]"
            if embedding is not None
            else None
        )
        fact_id = await conn.fetchval(
            """
            INSERT INTO fact (
                id, source_entity, target_entity, predicate,
                embedding, t_valid, t_invalid, t_created, t_expired,
                source_episodes, schema_version
            ) VALUES (
                gen_random_uuid(), $1::uuid, $2::uuid, $3,
                $4::vector, $5, NULL, $6, NULL,
                $7::uuid[], '0001'
            ) RETURNING id::text
            """,
            source_entity,
            target_entity,
            predicate,
            embedding_param,
            t_valid,
            now,
            source_episodes,
        )

    logger.debug(
        "Created fact %s: %s -> %s (%s)",
        fact_id,
        source_entity,
        target_entity,
        predicate,
    )
    return fact_id
