"""
tests/test_ingest.py — Tests for episode ingestion (KG-01).

Verifies:
- ingest_episode writes a row to the episode table and returns the UUID
- raw_data is preserved exactly (no transformation)
- source and reference_ts are stored as provided
- schema_version is "0001"
"""

import json
from datetime import datetime, timezone
import asyncpg
import pytest

from knowledge.ingest import ingest_episode


@pytest.mark.asyncio
async def test_ingest_episode_creates_row(conn: asyncpg.Connection):
    """ingest_episode returns a UUID string and a row exists in episode table."""
    raw_data = {"text": "hello from slack", "user": "alice"}
    source = "slack"
    reference_ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    episode_id = await ingest_episode(raw_data, source, reference_ts, conn)

    assert isinstance(episode_id, str)
    assert len(episode_id) == 36  # UUID string length

    row = await conn.fetchrow("SELECT * FROM episode WHERE id = $1::uuid", episode_id)
    assert row is not None


@pytest.mark.asyncio
async def test_ingest_episode_raw_data_preserved(conn: asyncpg.Connection):
    """raw_data is stored exactly as provided — no transformation (KG-01)."""
    raw_data = {"text": "complex payload", "metadata": {"key": "value", "count": 42}}
    source = "email"
    reference_ts = datetime(2026, 3, 1, 9, 30, 0, tzinfo=timezone.utc)

    episode_id = await ingest_episode(raw_data, source, reference_ts, conn)

    row = await conn.fetchrow(
        "SELECT raw_data, source FROM episode WHERE id = $1::uuid", episode_id
    )
    assert row is not None
    # asyncpg returns JSONB columns as strings — decode for comparison
    stored_data = row["raw_data"]
    if isinstance(stored_data, str):
        stored_data = json.loads(stored_data)
    assert stored_data == raw_data
    assert row["source"] == source


@pytest.mark.asyncio
async def test_ingest_episode_schema_version(conn: asyncpg.Connection):
    """schema_version is stored as '0001'."""
    raw_data = {"content": "test"}
    source = "schema_commons"
    reference_ts = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

    episode_id = await ingest_episode(raw_data, source, reference_ts, conn)

    row = await conn.fetchrow(
        "SELECT schema_version FROM episode WHERE id = $1::uuid", episode_id
    )
    assert row is not None
    assert row["schema_version"] == "0001"
