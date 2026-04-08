"""knowledge/resolve.py — Entity resolution (KG-02, D-14).

Entity resolution prevents duplicate entity rows by:
1. Exact name match (case-insensitive)
2. Embedding cosine similarity >= RESOLUTION_THRESHOLD

Returns existing entity_id or None if no match found.
Caller (extract.py) is responsible for creating a new entity when None is returned.
"""

import logging

import asyncpg

logger = logging.getLogger(__name__)

RESOLUTION_THRESHOLD = 0.88  # cosine similarity threshold (D-14)


async def resolve_entity(
    name: str,
    embedding: list[float],
    conn: asyncpg.Connection,
) -> str | None:
    """Return existing entity_id if name matches exactly or embedding cosine >= threshold.

    Returns None if no match — caller should create a new entity.

    Step 1: exact name match (case-insensitive via LOWER())
    Step 2: embedding similarity above threshold (only if embedding is non-empty)
    """
    # Step 1: exact name match (case-insensitive)
    row = await conn.fetchrow(
        "SELECT id FROM entity WHERE LOWER(name) = LOWER($1)", name
    )
    if row:
        logger.debug("Resolved entity '%s' by exact name match: %s", name, row["id"])
        return str(row["id"])

    # Step 2: embedding similarity above threshold (skip if empty embedding)
    if not embedding:
        return None

    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    row = await conn.fetchrow(
        """
        SELECT id, 1 - (embedding <=> $1::vector) AS similarity
        FROM entity
        WHERE embedding IS NOT NULL
          AND 1 - (embedding <=> $1::vector) >= $2
        ORDER BY embedding <=> $1::vector
        LIMIT 1
        """,
        embedding_str,
        RESOLUTION_THRESHOLD,
    )
    if row:
        logger.debug(
            "Resolved entity '%s' by embedding similarity %.3f: %s",
            name,
            row["similarity"],
            row["id"],
        )
        return str(row["id"])

    return None
