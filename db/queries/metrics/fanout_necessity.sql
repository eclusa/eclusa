-- CAL-08: Fan-out necessity rate
-- % of fan-outs where verdict = 'diverged' | 'partial' (i.e., models disagreed)
-- A single model would have missed the disagreement in these cases
-- $1 = lookback interval
SELECT
  COUNT(*) FILTER (WHERE verdict IN ('diverged', 'partial'))::float
  / NULLIF(COUNT(*), 0) AS fanout_necessity_rate
FROM fan_out
WHERE completed_at >= NOW() - $1::interval
  AND completed_at IS NOT NULL;
