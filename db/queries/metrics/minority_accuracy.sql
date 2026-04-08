-- CAL-07: Minority model accuracy
-- When gate_resolved.content->>'human_choice' matches a minority verdict in a fan-out,
-- which model provided that verdict. Groups by model name, counts frequency.
-- $1 = lookback interval
SELECT
  pass_data->>'model'                AS model,
  COUNT(*)                           AS minority_selections
FROM ledger_entry gate_res
JOIN fan_out fo
  ON fo.stage_id = gate_res.stage_id
CROSS JOIN LATERAL (
  SELECT jsonb_array_elements(fo.convergence->'passes') AS pass_data
) pass_expansion
WHERE gate_res.type = 'gate_resolved'
  AND gate_res.content->>'human_choice' = pass_data->>'verdict'
  AND gate_res.content->>'human_choice' != fo.convergence->>'majority_verdict'
  AND gate_res.timestamp >= NOW() - $1::interval
GROUP BY pass_data->>'model'
ORDER BY minority_selections DESC;
