"""schema_commons/embed.py — Embedding pipeline for SchemaIR entities.

Calls the embedding API in batches (D-08) and writes entity-level embeddings
(D-09) into the entity table's vector(1024) column (D-10).

NOTE: The entity table has no UNIQUE constraint on name (Phase 1 DDL).
Upsert is implemented as SELECT-then-INSERT/UPDATE. See deferred-items.md
for the tracking of a future migration to add UniqueConstraint on entity.name.
"""

import os
import logging
from datetime import datetime, timezone

import asyncpg
import httpx

from schema_commons.ir import SchemaIR

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "https://api.openai.com/v1/embeddings")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "20"))


async def embed_texts(texts: list[str], client: httpx.AsyncClient) -> list[list[float]]:
    """Call embedding API in batches. Returns list of 1024-dim float vectors.

    Always passes dimensions=1024 — matches entity.embedding vector(1024) column
    (D-10). text-embedding-3-small supports Matryoshka truncation to any dim.

    Raises httpx.HTTPStatusError on API failure — caller handles retry (D-08).
    """
    if not texts:
        return []

    results: list[list[float]] = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        resp = await client.post(
            EMBEDDING_URL,
            json={"model": EMBEDDING_MODEL, "input": batch, "dimensions": 1024},
            headers={
                "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', 'test-key')}"
            },
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # Sort by index to guarantee order matches input order
        sorted_data = sorted(data, key=lambda x: x["index"])
        results.extend(item["embedding"] for item in sorted_data)
    return results


async def embed_schema_ir(
    ir: SchemaIR,
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
) -> None:
    """Embed all entities in SchemaIR and upsert into the entity table.

    One embedding per IR entity (D-09). Uses entity name as natural key.

    Upsert strategy: SELECT-then-INSERT/UPDATE because the entity table has no
    UNIQUE constraint on name (Phase 1 DDL omitted it). Under concurrent access
    this can produce duplicates — acceptable for single-tenant deployment.
    A future migration should add UniqueConstraint on entity.name.
    """
    if not ir.entities:
        return

    # Build text inputs — one per entity, entity-level granularity (D-09)
    texts = [f"{e.name}: {e.description or ''} (type: {e.type})" for e in ir.entities]
    embeddings = await embed_texts(texts, client)

    now = datetime.now(timezone.utc)

    for entity, embedding in zip(ir.entities, embeddings):
        # Serialize embedding list to pgvector string format: "[0.1, 0.2, ...]"
        # asyncpg passes this as text; the ::vector cast in SQL handles conversion.
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

        # Check if entity with this name already exists
        existing_id = await conn.fetchval(
            "SELECT id FROM entity WHERE name = $1 LIMIT 1",
            entity.name,
        )

        if existing_id is not None:
            # Update existing entity — refresh embedding and updated_at
            await conn.execute(
                """
                UPDATE entity
                SET embedding = $1::vector,
                    type = $2,
                    summary = $3,
                    updated_at = $4
                WHERE id = $5
                """,
                embedding_str,
                entity.type,
                entity.description,
                now,
                existing_id,
            )
        else:
            # Insert new entity row
            await conn.execute(
                """
                INSERT INTO entity (id, name, type, summary, embedding, created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2, $3, $4::vector, $5, $6)
                """,
                entity.name,
                entity.type,
                entity.description,
                embedding_str,
                now,
                now,
            )

    logger.debug(
        "Embedded %d entities from %s schema",
        len(ir.entities),
        ir.source_format,
    )
