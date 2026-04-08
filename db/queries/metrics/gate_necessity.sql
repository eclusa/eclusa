-- CAL-01: Gate necessity rate
-- % of resolved gates where human_choice != system_recommendation
-- content JSONB must contain 'human_choice' and 'system_recommendation' keys
-- $1 = lookback interval (e.g., '30 days'::interval)
SELECT
  COUNT(*) FILTER (
    WHERE resolved.content->>'human_choice' IS DISTINCT FROM
          resolved.content->>'system_recommendation'
      AND resolved.content->>'human_choice' IS NOT NULL
  )::float
  / NULLIF(COUNT(*), 0) AS gate_necessity_rate
FROM ledger_entry surfaced
JOIN ledger_entry resolved
  ON  resolved.stage_id = surfaced.stage_id
  AND resolved.type = 'gate_resolved'
WHERE surfaced.type = 'gate_surfaced'
  AND surfaced.timestamp >= NOW() - $1::interval;
