-- CAL-03: Resolution latency (seconds, p50/p95)
-- Time from gate_surfaced to gate_resolved for the same stage
-- $1 = lookback interval
SELECT
  PERCENTILE_CONT(0.50) WITHIN GROUP (
    ORDER BY EXTRACT(EPOCH FROM (resolved.timestamp - surfaced.timestamp))
  ) AS latency_p50_seconds,
  PERCENTILE_CONT(0.95) WITHIN GROUP (
    ORDER BY EXTRACT(EPOCH FROM (resolved.timestamp - surfaced.timestamp))
  ) AS latency_p95_seconds
FROM ledger_entry surfaced
JOIN ledger_entry resolved
  ON  resolved.stage_id = surfaced.stage_id
  AND resolved.type = 'gate_resolved'
WHERE surfaced.type = 'gate_surfaced'
  AND surfaced.timestamp >= NOW() - $1::interval;
