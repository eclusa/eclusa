"""Tests for schema_commons/embed.py — embedding pipeline.

TDD approach: all tests mock httpx so no real API key is needed.
Tests for embed_schema_ir use the conftest conn fixture for DB access.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from schema_commons.embed import (
    embed_texts,
    embed_schema_ir,
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
)
from schema_commons.ir import IREntity, SchemaIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_fake_response(n: int) -> dict:
    """Build a fake embedding API response with n embeddings of 1024 dims."""
    return {"data": [{"index": i, "embedding": [0.1] * 1024} for i in range(n)]}


def make_mock_client(responses: list[dict]) -> httpx.AsyncClient:
    """Create a mock httpx.AsyncClient that returns fake responses in order."""
    mock_client = MagicMock(spec=httpx.AsyncClient)
    fake_resps = []
    for resp_data in responses:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.json.return_value = resp_data
        mock_resp.raise_for_status = MagicMock()
        fake_resps.append(mock_resp)
    mock_client.post = AsyncMock(side_effect=fake_resps)
    return mock_client


# ---------------------------------------------------------------------------
# Tests: module-level constants
# ---------------------------------------------------------------------------


def test_embedding_model_default():
    """EMBEDDING_MODEL defaults to text-embedding-3-small."""
    assert EMBEDDING_MODEL == "text-embedding-3-small"


def test_embedding_batch_size_default():
    """EMBEDDING_BATCH_SIZE defaults to 20."""
    assert EMBEDDING_BATCH_SIZE == 20


# ---------------------------------------------------------------------------
# Tests: embed_texts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_texts_single_batch():
    """embed_texts with 2 texts makes exactly 1 API call (2 < 20 batch size)."""
    texts = ["hello", "world"]
    client = make_mock_client([make_fake_response(2)])

    result = await embed_texts(texts, client)

    assert client.post.call_count == 1
    assert len(result) == 2
    assert len(result[0]) == 1024
    assert len(result[1]) == 1024


@pytest.mark.asyncio
async def test_embed_texts_two_batches():
    """embed_texts with 25 texts makes exactly 2 API calls (20 + 5)."""
    texts = [f"text {i}" for i in range(25)]
    client = make_mock_client(
        [
            make_fake_response(20),  # First batch: 20 texts
            make_fake_response(5),  # Second batch: 5 texts
        ]
    )

    result = await embed_texts(texts, client)

    assert client.post.call_count == 2
    assert len(result) == 25


@pytest.mark.asyncio
async def test_embed_texts_dimensions_1024():
    """Each returned vector has exactly 1024 dimensions."""
    texts = ["hello"]
    client = make_mock_client([make_fake_response(1)])

    result = await embed_texts(texts, client)

    assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_embed_texts_passes_dimensions_param():
    """embed_texts always passes dimensions=1024 in the request body."""
    texts = ["hello"]
    client = make_mock_client([make_fake_response(1)])

    await embed_texts(texts, client)

    call_kwargs = client.post.call_args
    request_json = (
        call_kwargs[1]["json"]
        if "json" in call_kwargs[1]
        else call_kwargs.kwargs.get(
            "json", call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
        )
    )
    assert request_json.get("dimensions") == 1024


@pytest.mark.asyncio
async def test_embed_texts_raises_on_api_error():
    """embed_texts propagates httpx.HTTPStatusError on API failure."""
    texts = ["hello"]
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=MagicMock(),
        response=MagicMock(),
    )
    mock_client.post = AsyncMock(return_value=mock_resp)

    with pytest.raises(httpx.HTTPStatusError):
        await embed_texts(texts, mock_client)


@pytest.mark.asyncio
async def test_embed_texts_empty_list():
    """embed_texts with empty list returns empty list without any API calls."""
    client = make_mock_client([])

    result = await embed_texts([], client)

    assert result == []
    assert client.post.call_count == 0


@pytest.mark.asyncio
async def test_embed_texts_preserves_order():
    """embed_texts respects index ordering from API response."""
    texts = ["first", "second"]
    # Return items in reversed index order — result must still match input order
    reversed_resp = {
        "data": [
            {"index": 1, "embedding": [0.9] * 1024},
            {"index": 0, "embedding": [0.1] * 1024},
        ]
    }
    client = make_mock_client([reversed_resp])

    result = await embed_texts(texts, client)

    # Index 0 → [0.1]*1024, index 1 → [0.9]*1024
    assert result[0][0] == pytest.approx(0.1)
    assert result[1][0] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Tests: embed_schema_ir (requires DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_schema_ir_inserts_entity_rows(conn):
    """embed_schema_ir inserts entity rows into the entity table."""
    ir = SchemaIR(
        source_format="openapi",
        entities=[
            IREntity(
                source_ref="User",
                name="EmbedTestUser",
                description="A user entity",
                type="model",
            ),
            IREntity(
                source_ref="Post",
                name="EmbedTestPost",
                description="A post entity",
                type="model",
            ),
        ],
    )
    client = make_mock_client([make_fake_response(2)])

    await embed_schema_ir(ir, conn, client)

    rows = await conn.fetch(
        "SELECT name, type FROM entity WHERE name IN ('EmbedTestUser', 'EmbedTestPost') ORDER BY name"
    )
    assert len(rows) == 2
    names = {r["name"] for r in rows}
    assert "EmbedTestUser" in names
    assert "EmbedTestPost" in names

    # Cleanup
    await conn.execute(
        "DELETE FROM entity WHERE name IN ('EmbedTestUser', 'EmbedTestPost')"
    )


@pytest.mark.asyncio
async def test_embed_schema_ir_stores_1024_dim_vector(conn):
    """embed_schema_ir stores a 1024-dim vector in the embedding column."""
    ir = SchemaIR(
        source_format="openapi",
        entities=[
            IREntity(
                source_ref="Widget",
                name="EmbedTestWidget",
                description="A widget",
                type="model",
            ),
        ],
    )
    client = make_mock_client([make_fake_response(1)])

    await embed_schema_ir(ir, conn, client)

    row = await conn.fetchrow(
        "SELECT embedding FROM entity WHERE name = 'EmbedTestWidget'"
    )
    assert row is not None
    # asyncpg returns pgvector as a string "[0.1,0.1,...]" without a registered codec.
    # Parse the string to verify 1024 dimensions.
    embedding_str = row["embedding"]
    assert embedding_str is not None
    # Strip brackets and split by comma to count dimensions
    values = embedding_str.strip("[]").split(",")
    assert len(values) == 1024

    await conn.execute("DELETE FROM entity WHERE name = 'EmbedTestWidget'")


@pytest.mark.asyncio
async def test_embed_schema_ir_skips_existing_entity(conn):
    """embed_schema_ir upserts by name — skips if entity already exists (updates embedding)."""
    entity_name = "EmbedTestExisting"

    # Pre-insert entity
    await conn.execute(
        "INSERT INTO entity (id, name, type, created_at, updated_at) "
        "VALUES (gen_random_uuid(), $1, 'model', NOW(), NOW())",
        entity_name,
    )

    ir = SchemaIR(
        source_format="openapi",
        entities=[
            IREntity(
                source_ref="Existing",
                name=entity_name,
                description="Already exists",
                type="model",
            ),
        ],
    )
    client = make_mock_client([make_fake_response(1)])

    await embed_schema_ir(ir, conn, client)

    # Should still have exactly 1 entity (no duplicate)
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM entity WHERE name = $1", entity_name
    )
    assert count == 1

    await conn.execute("DELETE FROM entity WHERE name = $1", entity_name)


@pytest.mark.asyncio
async def test_embed_schema_ir_noop_on_empty_ir(conn):
    """embed_schema_ir does nothing when IR has no entities."""
    ir = SchemaIR(source_format="openapi", entities=[])
    client = make_mock_client([])

    # Should not raise, not call API
    await embed_schema_ir(ir, conn, client)

    assert client.post.call_count == 0


@pytest.mark.asyncio
async def test_embed_schema_ir_batches_25_entities(conn):
    """embed_schema_ir with 25 entities calls embed_texts, resulting in 2 API calls."""
    entities = [
        IREntity(
            source_ref=f"E{i}",
            name=f"EmbedBatchTest{i}",
            description=f"Entity {i}",
            type="model",
        )
        for i in range(25)
    ]
    ir = SchemaIR(source_format="openapi", entities=entities)
    client = make_mock_client(
        [
            make_fake_response(20),
            make_fake_response(5),
        ]
    )

    await embed_schema_ir(ir, conn, client)

    assert client.post.call_count == 2

    # Cleanup
    names = [f"EmbedBatchTest{i}" for i in range(25)]
    await conn.execute("DELETE FROM entity WHERE name = ANY($1::text[])", names)
