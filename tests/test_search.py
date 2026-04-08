"""Tests for hybrid search: cosine + BM25 + BFS via RRF.

TDD: tests written first (RED), then implementation added in 04-07 GREEN phase.
Covers KG-06, COMMONS-05, D-21 per-signal scores.
"""

import pytest

from knowledge.search import hybrid_search, search_schema_commons, SearchResult


@pytest.fixture(autouse=True)
async def clean_entity_table(conn):
    """Truncate entity and fact tables before each test for isolation."""
    await conn.execute("TRUNCATE TABLE fact, entity RESTART IDENTITY CASCADE")
    yield


async def _insert_entity(
    conn, name: str, entity_type: str = "concept", embedding: list[float] | None = None
) -> str:
    """Helper: insert entity row and return UUID as str."""
    if embedding is not None:
        emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
        row = await conn.fetchrow(
            """
            INSERT INTO entity (id, name, type, summary, embedding)
            VALUES (gen_random_uuid(), $1, $2, $3, $4::vector)
            RETURNING id
            """,
            name,
            entity_type,
            f"Summary for {name}",
            emb_str,
        )
    else:
        row = await conn.fetchrow(
            """
            INSERT INTO entity (id, name, type, summary)
            VALUES (gen_random_uuid(), $1, $2, $3)
            RETURNING id
            """,
            name,
            entity_type,
            f"Summary for {name}",
        )
    return str(row["id"])


@pytest.mark.asyncio
async def test_hybrid_search_empty_db(conn):
    """Empty entity table should return empty list — no crash."""
    results = await hybrid_search("User", [0.1] * 1024, conn, limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_hybrid_search_returns_results(conn):
    """Entity named 'User' with matching embedding appears in results."""
    await _insert_entity(conn, "User", embedding=[0.1] * 1024)
    results = await hybrid_search("User", [0.1] * 1024, conn, limit=10)
    assert len(results) > 0
    assert results[0].name == "User"


@pytest.mark.asyncio
async def test_hybrid_search_scores(conn):
    """All rrf_score > 0; cosine_score, bm25_score, bfs_score are floats >= 0.0 (D-21)."""
    await _insert_entity(conn, "User", embedding=[0.1] * 1024)
    results = await hybrid_search("User", [0.1] * 1024, conn, limit=10)
    assert len(results) > 0
    for r in results:
        assert r.rrf_score > 0.0
        assert isinstance(r.cosine_score, float)
        assert isinstance(r.bm25_score, float)
        assert isinstance(r.bfs_score, float)
        assert r.cosine_score >= 0.0
        assert r.bm25_score >= 0.0
        assert r.bfs_score >= 0.0


@pytest.mark.asyncio
async def test_search_schema_commons_alias(conn):
    """search_schema_commons returns same results as hybrid_search for same inputs."""
    await _insert_entity(conn, "User", embedding=[0.1] * 1024)
    results_search = await hybrid_search("User", [0.1] * 1024, conn, limit=10)
    results_commons = await search_schema_commons("User", [0.1] * 1024, conn, limit=10)
    assert len(results_search) == len(results_commons)
    for s, c in zip(results_search, results_commons):
        assert s.name == c.name
        assert abs(s.rrf_score - c.rrf_score) < 1e-9


@pytest.mark.asyncio
async def test_search_result_has_per_signal_scores(conn):
    """SearchResult model has cosine_score, bm25_score, bfs_score as float fields (D-21)."""
    fields = SearchResult.model_fields
    assert "cosine_score" in fields
    assert "bm25_score" in fields
    assert "bfs_score" in fields
    assert "rrf_score" in fields
    assert "entity_id" in fields
    assert "name" in fields
    assert "type" in fields
    assert "summary" in fields


@pytest.mark.asyncio
async def test_hybrid_search_ordered_by_rrf_score(conn):
    """Results are ordered by rrf_score descending."""
    await _insert_entity(conn, "User", embedding=[0.1] * 1024)
    await _insert_entity(conn, "Post", embedding=[0.5] * 1024)
    results = await hybrid_search("User", [0.1] * 1024, conn, limit=10)
    scores = [r.rrf_score for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_hybrid_search_empty_query_text_graceful(conn):
    """Empty query_text returns results ranked by cosine only — no crash."""
    await _insert_entity(conn, "User", embedding=[0.1] * 1024)
    # Should not raise — BM25 with empty query returns 0 results but cosine still works
    results = await hybrid_search("", [0.1] * 1024, conn, limit=10)
    # May return results (cosine) or empty (both BM25 and cosine return empty) — just no crash
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_bfs_score_zero_without_facts(conn):
    """BFS signal returns 0.0 when no fact edges exist — graceful fallback."""
    await _insert_entity(conn, "User", embedding=[0.1] * 1024)
    results = await hybrid_search("User", [0.1] * 1024, conn, limit=10)
    assert len(results) > 0
    # With no facts, bfs_score must be 0.0 for all results
    for r in results:
        assert r.bfs_score == 0.0
