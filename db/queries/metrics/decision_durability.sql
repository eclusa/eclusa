-- CAL-04: Decision durability
-- % of resolved gates where the same cascade later received a cascade_migration entry
-- (proxy for "resolution led to rework in same cascade")
-- $1 = lookback interval
SELECT
  COUNT(*) FILTER (
    WHERE EXISTS (
      SELECT 1 FROM ledger_entry rework
      WHERE rework.cascade_id = resolved.cascade_id
        AND rework.type = 'cascade_migration'
        AND rework.timestamp > resolved.timestamp
    )
  )::float
  / NULLIF(COUNT(*), 0) AS decision_durability_rework_rate
FROM ledger_entry resolved
WHERE resolved.type = 'gate_resolved'
  AND resolved.timestamp >= NOW() - $1::interval;
