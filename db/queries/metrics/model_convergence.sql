-- CAL-06: Model convergence rate
-- % of completed fan-outs where verdict = 'converged'
-- $1 = lookback interval
SELECT
  COUNT(*) FILTER (WHERE verdict = 'converged')::float
  / NULLIF(COUNT(*), 0) AS model_convergence_rate
FROM fan_out
WHERE completed_at >= NOW() - $1::interval
  AND completed_at IS NOT NULL;
