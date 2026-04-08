"""knowledge/search.py — Hybrid search: cosine + BM25 + BFS traversal, RRF fusion.

Single SQL query combining three signals (D-18). RRF k=60 (D-19).
BFS limited to 2 hops (D-20). Returns ranked list with per-signal scores (D-21).
No external reranker (D-22).

Satisfies KG-06 (hybrid search) and COMMONS-05 (schema commons matching stage query).
"""

from pathlib import Path

import asyncpg
from pydantic import BaseModel

_SQL_PATH = (
    Path(__file__).parent.parent / "schema_commons" / "queries" / "hybrid_search.sql"
)


class SearchResult(BaseModel):
    """Ranked search result with per-signal score transparency (D-21).

    rrf_score: Reciprocal Rank Fusion score — primary sort key (descending).
    cosine_score: cosine similarity signal; 0.0 if entity not in cosine CTE.
    bm25_score: BM25 full-text signal; 0.0 if entity not in BM25 CTE.
    bfs_score: BFS graph traversal signal; 0.0 if entity not in BFS CTE.
    """

    entity_id: str
    name: str
    type: str | None
    summary: str | None
    rrf_score: float
    cosine_score: float  # 0.0 when entity not in cosine CTE (D-21)
    bm25_score: float  # 0.0 when entity not in BM25 CTE (D-21)
    bfs_score: float  # 0.0 when entity not in BFS CTE (D-21)


async def hybrid_search(
    query_text: str,
    query_embedding: list[float],
    conn: asyncpg.Connection,
    limit: int = 10,
) -> list[SearchResult]:
    """Hybrid search: cosine similarity + BM25 + BFS graph traversal, fused via RRF.

    query_text: used for BM25 signal and BFS seed entity lookup
    query_embedding: 1024-dim vector for cosine signal (pass as list[float])
    limit: max results to return (default 10)

    Returns ranked list ordered by rrf_score descending with per-signal scores (D-21).
    Empty entity table returns [] — no crash.
    Empty query_text gracefully falls back to cosine-only ranking.
    """
    sql = _SQL_PATH.read_text()
    # asyncpg requires vector as '[v1,v2,...]' string — no native vector codec without registration
    # Same pattern as resolve.py and facts.py (Phase 4 decision in STATE.md)
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    rows = await conn.fetch(sql, embedding_str, query_text, limit)
    return [
        SearchResult(
            entity_id=str(row["id"]),
            name=row["name"],
            type=row["type"],
            summary=row["summary"],
            rrf_score=float(row["rrf_score"]),
            cosine_score=float(row["cosine_score"] or 0.0),
            bm25_score=float(row["bm25_score"] or 0.0),
            bfs_score=float(row["bfs_score"] or 0.0),
        )
        for row in rows
    ]


async def search_schema_commons(
    query_text: str,
    query_embedding: list[float],
    conn: asyncpg.Connection,
    limit: int = 10,
) -> list[SearchResult]:
    """Schema commons matching stage query (COMMONS-05).

    Queries schema commons entity index and returns ranked matches
    for a domain concept. Delegates to hybrid_search.

    Caller is responsible for generating query_embedding before calling this function
    (e.g., via schema_commons.embed.embed_texts).
    """
    return await hybrid_search(query_text, query_embedding, conn, limit)
