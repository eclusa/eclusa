-- CAL-02: Orchestrator absorption rate
-- % of gate-eligible events resolved automatically (gate_auto_resolved) vs surfaced to human
-- $1 = lookback interval
SELECT
  COUNT(*) FILTER (WHERE type = 'gate_auto_resolved')::float
  / NULLIF(
      COUNT(*) FILTER (WHERE type IN ('gate_surfaced', 'gate_auto_resolved')),
      0
  ) AS orchestrator_absorption_rate
FROM ledger_entry
WHERE type IN ('gate_surfaced', 'gate_auto_resolved')
  AND timestamp >= NOW() - $1::interval;
