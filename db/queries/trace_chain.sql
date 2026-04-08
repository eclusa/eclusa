-- Trace chain: artifact → session → stage → cascade → intent
-- Returns the full ancestry of an artifact in a single query.
-- $1 = artifact UUID to trace
--
-- CYCLE guard (per PITFALLS.md Pitfall 2): prevents infinite loop on cyclic stage.depends_on.
-- depth < 50 provides a secondary termination guard.
-- Source: eclusa.md §3.6; CONTEXT.md D-17; ARCHITECTURE.md Pattern 3

SELECT
  a.id            AS artifact_id,
  a.session_id,
  a.stage_id,
  a.cascade_id,
  a.intent_id,
  -- Enriched context from joined tables
  s.type          AS stage_type,
  s.state         AS stage_state,
  c.state         AS cascade_state,
  i.raw           AS intent_raw,
  i.source        AS intent_source
FROM artifact a
JOIN work_session ws ON ws.id = a.session_id
LEFT JOIN stage   s ON s.id = ws.stage_ids[1]
LEFT JOIN cascade c ON c.id = s.cascade_id
LEFT JOIN intent  i ON i.id = c.intent_id
WHERE a.id = $1
LIMIT 1;
