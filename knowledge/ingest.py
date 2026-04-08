"""knowledge/ingest.py — Episode tier ingestion.

Episodes preserve raw data exactly as received (KG-01, D-12).
Every piece of knowledge flows through episode first.
"""

import json
import logging
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_VERSION = "0001"


async def ingest_episode(
    raw_data: dict,
    source: str,
    reference_ts: datetime,
    conn: asyncpg.Connection,
) -> str:
    """Write raw data to episode table. Returns episode UUID.

    raw_data is stored as-is in JSONB — no transformation (KG-01).
    reference_ts is the event-world time, not the ingestion time.
    """
    episode_id = await conn.fetchval(
        """
        INSERT INTO episode (id, source, raw_data, reference_ts, schema_version)
        VALUES (gen_random_uuid(), $1, $2::jsonb, $3, $4)
        RETURNING id::text
        """,
        source,
        json.dumps(raw_data),
        reference_ts,
        SYSTEM_SCHEMA_VERSION,
    )
    logger.debug("Ingested episode %s from source=%s", episode_id, source)
    return episode_id
