-- CAL-05: Cascade rework rate
-- % of completed cascades that were subsequently reopened (cascade_reopened event)
-- $1 = lookback interval
SELECT
  COUNT(DISTINCT reopened.cascade_id)::float
  / NULLIF(
      COUNT(DISTINCT completed.cascade_id),
      0
  ) AS cascade_rework_rate
FROM ledger_entry completed
LEFT JOIN ledger_entry reopened
  ON  reopened.cascade_id = completed.cascade_id
  AND reopened.type = 'cascade_reopened'
  AND reopened.timestamp > completed.timestamp
WHERE completed.type = 'cascade_state_changed'
  AND completed.content->>'new_state' = 'completed'
  AND completed.timestamp >= NOW() - $1::interval;
