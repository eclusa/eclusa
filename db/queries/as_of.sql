-- AS OF TIMESTAMP: returns the most recent ledger entry for a given entity
-- before or at the specified timestamp.
-- $1 = entity_id (intent_id, cascade_id, or stage_id — any ledger FK)
-- $2 = as_of TIMESTAMPTZ (the historical moment to query)
--
-- Source: CONTEXT.md SCHEMA-05; ARCHITECTURE.md Pattern 5; eclusa.md §3.7

SELECT
  id,
  type,
  content,
  confidence,
  reversible,
  artifact_ids,
  timestamp,
  schema_version
FROM ledger_entry
WHERE (
    intent_id   = $1
    OR cascade_id = $1
    OR stage_id   = $1
    OR session_id = $1
  )
  AND timestamp <= $2::timestamptz
ORDER BY timestamp DESC
LIMIT 1;
