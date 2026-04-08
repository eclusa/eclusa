-- Hybrid search: cosine similarity + BM25 + BFS graph traversal, fused via RRF.
-- Three ranking signals combined via Reciprocal Rank Fusion (D-18, D-19).
-- BFS limited to 2 explicit hops from seed entities (D-20).
-- Per-signal scores exposed for transparency (D-21).
-- No external reranker — RRF is sufficient at single-tenant scale (D-22).
--
-- Parameters:
--   $1 = query_embedding::vector (1024-dim) — cosine signal
--   $2 = query_text (text) — BM25 signal + BFS seed entity lookup
--   $3 = limit (int) — max results to return
--
-- RRF formula: 1 / (k + rank) where k=60 (D-19)
-- cosine_score, bm25_score, bfs_score are NULL for entities absent from that signal's CTE.
-- Python layer coerces NULL to 0.0.
--
-- Source: eclusa.md §4.2; CONTEXT.md D-18 through D-22; RESEARCH.md Pattern 5

WITH
  cosine AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS r,
           1 - (embedding <=> $1::vector) AS cosine_score
    FROM entity
    WHERE embedding IS NOT NULL
    LIMIT 40
  ),
  bm25 AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY pdb.score(id) DESC) AS r,
           pdb.score(id) AS bm25_score
    FROM entity
    WHERE name ||| $2 OR summary ||| $2
    LIMIT 40
  ),
  seed_entities AS (
    SELECT id
    FROM entity
    WHERE name ||| $2
    LIMIT 5
  ),
  bfs AS (
    -- Hop 1: direct neighbors of seed entities
    SELECT DISTINCT e.id, 1 AS hop
    FROM fact f
    JOIN entity e ON e.id = f.target_entity
    WHERE f.source_entity IN (SELECT id FROM seed_entities)
      AND f.t_invalid IS NULL
    UNION
    -- Hop 2: neighbors of hop-1 entities (fixed 2-hop depth per D-20)
    SELECT DISTINCT e.id, 2 AS hop
    FROM fact f
    JOIN entity e ON e.id = f.target_entity
    JOIN (
      SELECT DISTINCT e2.id
      FROM fact f2
      JOIN entity e2 ON e2.id = f2.target_entity
      WHERE f2.source_entity IN (SELECT id FROM seed_entities)
        AND f2.t_invalid IS NULL
    ) b ON b.id = f.source_entity
    WHERE f.t_invalid IS NULL
  ),
  bfs_ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY MIN(hop)) AS r,
           1.0 / (60.0 + MIN(hop)) AS bfs_score
    FROM bfs
    GROUP BY id
    LIMIT 40
  ),
  rrf AS (
    SELECT id, 1.0 / (60.0 + r) AS s FROM cosine
    UNION ALL
    SELECT id, 1.0 / (60.0 + r) AS s FROM bm25
    UNION ALL
    SELECT id, 1.0 / (60.0 + r) AS s FROM bfs_ranked
  )
SELECT
  e.id,
  e.name,
  e.type,
  e.summary,
  SUM(rrf.s)           AS rrf_score,
  MAX(c.cosine_score)  AS cosine_score,
  MAX(b.bm25_score)    AS bm25_score,
  MAX(bf.bfs_score)    AS bfs_score
FROM rrf
JOIN entity e USING (id)
LEFT JOIN cosine c USING (id)
LEFT JOIN bm25 b USING (id)
LEFT JOIN bfs_ranked bf USING (id)
GROUP BY e.id, e.name, e.type, e.summary
ORDER BY rrf_score DESC
LIMIT $3;
