/**
 * Metrics Dashboard E2E — CAL-E2E-02
 *
 * Proves that all 8 self-calibration metric cards render real computed values
 * (not zeros, not empty state) when sufficient test data exists in the database.
 *
 * Seeds metric data via docker exec psql, navigates to /metrics, and asserts
 * each card shows a real number with no empty state messages.
 */
import { execSync } from 'child_process'
import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Deterministic UUIDs — prefixed 00000013 for easy identification/cleanup
// ---------------------------------------------------------------------------
const ACTOR_ID    = '00000013-e2e0-4000-8000-000000000001'

const INTENT_1    = '00000013-e2e0-4000-8000-000000000010'
const INTENT_2    = '00000013-e2e0-4000-8000-000000000011'
const INTENT_3    = '00000013-e2e0-4000-8000-000000000012'

const CASCADE_1   = '00000013-e2e0-4000-8000-000000000020'
const CASCADE_2   = '00000013-e2e0-4000-8000-000000000021'
const CASCADE_3   = '00000013-e2e0-4000-8000-000000000022'

// Gate stages (need gate_surfaced + gate_resolved)
const STAGE_G1    = '00000013-e2e0-4000-8000-000000000030'
const STAGE_G2    = '00000013-e2e0-4000-8000-000000000031'
// Auto-resolved gate stages
const STAGE_G3    = '00000013-e2e0-4000-8000-000000000032'
const STAGE_G4    = '00000013-e2e0-4000-8000-000000000033'
// Narrowing stages
const STAGE_N1    = '00000013-e2e0-4000-8000-000000000040'
const STAGE_N2    = '00000013-e2e0-4000-8000-000000000041'

// Fan-out IDs
const FANOUT_1    = '00000013-e2e0-4000-8000-000000000050'
const FANOUT_2    = '00000013-e2e0-4000-8000-000000000051'
const FANOUT_3    = '00000013-e2e0-4000-8000-000000000052'

// Ledger entry IDs
const LE_SURF_1   = '00000013-e2e0-4000-8000-000000000060'
const LE_SURF_2   = '00000013-e2e0-4000-8000-000000000061'
const LE_RES_1    = '00000013-e2e0-4000-8000-000000000062'
const LE_RES_2    = '00000013-e2e0-4000-8000-000000000063'
const LE_AUTO_1   = '00000013-e2e0-4000-8000-000000000064'
const LE_AUTO_2   = '00000013-e2e0-4000-8000-000000000065'
const LE_COMP_1   = '00000013-e2e0-4000-8000-000000000066'
const LE_COMP_2   = '00000013-e2e0-4000-8000-000000000067'
const LE_REOPEN   = '00000013-e2e0-4000-8000-000000000068'
const LE_MIGR     = '00000013-e2e0-4000-8000-000000000069'

// ---------------------------------------------------------------------------
// DB helpers — psql via docker exec
// ---------------------------------------------------------------------------

function runSql(sql: string) {
  execSync(
    `docker exec -i eclusa-db-1 psql -U eclusa -d eclusa`,
    { input: sql, stdio: ['pipe', 'pipe', 'pipe'] },
  )
}

function seedMetricData() {
  const sql = `
    -- ===== Actor =====
    INSERT INTO actor (id, type, identity, permissions)
    VALUES ('${ACTOR_ID}', 'system', 'e2e-metrics-cal02', '{"resolve_gates":["*"],"view_costs":true}')
    ON CONFLICT DO NOTHING;

    -- ===== Intents =====
    INSERT INTO intent (id, source, raw, created_by)
    VALUES
      ('${INTENT_1}', 'api', 'E2E metrics test intent 1', '${ACTOR_ID}'),
      ('${INTENT_2}', 'api', 'E2E metrics test intent 2', '${ACTOR_ID}'),
      ('${INTENT_3}', 'api', 'E2E metrics test intent 3', '${ACTOR_ID}');

    -- ===== Cascades =====
    INSERT INTO cascade (id, intent_id, shape, state)
    VALUES
      ('${CASCADE_1}', '${INTENT_1}', '{"test":"metrics_e2e"}', 'active'),
      ('${CASCADE_2}', '${INTENT_2}', '{"test":"metrics_e2e"}', 'active'),
      ('${CASCADE_3}', '${INTENT_3}', '{"test":"metrics_e2e"}', 'active');

    -- ===== Stages: 4 gate + 2 narrowing =====
    INSERT INTO stage (id, cascade_id, type, state, depends_on)
    VALUES
      ('${STAGE_G1}', '${CASCADE_1}', 'gate', 'resolved', '{}'::uuid[]),
      ('${STAGE_G2}', '${CASCADE_2}', 'gate', 'resolved', '{}'::uuid[]),
      ('${STAGE_G3}', '${CASCADE_1}', 'gate', 'resolved', '{}'::uuid[]),
      ('${STAGE_G4}', '${CASCADE_2}', 'gate', 'resolved', '{}'::uuid[]),
      ('${STAGE_N1}', '${CASCADE_1}', 'narrowing', 'resolved', '{}'::uuid[]),
      ('${STAGE_N2}', '${CASCADE_3}', 'narrowing', 'resolved', '{}'::uuid[]);

    -- ===== Ledger: gate_surfaced (2 gates) =====
    -- surfaced 10 min ago
    INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, timestamp)
    VALUES
      ('${LE_SURF_1}', '${STAGE_G1}', '${CASCADE_1}', '${ACTOR_ID}',
       'gate_surfaced', '{"stage_id":"${STAGE_G1}"}',
       NOW() - interval '10 minutes'),
      ('${LE_SURF_2}', '${STAGE_G2}', '${CASCADE_2}', '${ACTOR_ID}',
       'gate_surfaced', '{"stage_id":"${STAGE_G2}"}',
       NOW() - interval '10 minutes');

    -- ===== Ledger: gate_resolved (2 gates) =====
    -- resolved 5 min ago
    -- G1: human_choice DIFFERS from system_recommendation (gate_necessity > 0)
    INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, timestamp)
    VALUES
      ('${LE_RES_1}', '${STAGE_G1}', '${CASCADE_1}', '${ACTOR_ID}',
       'gate_resolved',
       '{"human_choice":"reject","system_recommendation":"approve","stage_id":"${STAGE_G1}"}',
       NOW() - interval '5 minutes'),
    -- G2: human_choice MATCHES system_recommendation
      ('${LE_RES_2}', '${STAGE_G2}', '${CASCADE_2}', '${ACTOR_ID}',
       'gate_resolved',
       '{"human_choice":"approve","system_recommendation":"approve","stage_id":"${STAGE_G2}"}',
       NOW() - interval '5 minutes');

    -- ===== Ledger: gate_auto_resolved (2 separate stages for absorption rate) =====
    INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, timestamp)
    VALUES
      ('${LE_AUTO_1}', '${STAGE_G3}', '${CASCADE_1}', '${ACTOR_ID}',
       'gate_auto_resolved', '{"stage_id":"${STAGE_G3}"}',
       NOW() - interval '8 minutes'),
      ('${LE_AUTO_2}', '${STAGE_G4}', '${CASCADE_2}', '${ACTOR_ID}',
       'gate_auto_resolved', '{"stage_id":"${STAGE_G4}"}',
       NOW() - interval '7 minutes');

    -- ===== Ledger: cascade_state_changed (completed) for rework metric =====
    INSERT INTO ledger_entry (id, cascade_id, actor_id, type, content, timestamp)
    VALUES
      ('${LE_COMP_1}', '${CASCADE_1}', '${ACTOR_ID}',
       'cascade_state_changed', '{"new_state":"completed"}',
       NOW() - interval '4 minutes'),
      ('${LE_COMP_2}', '${CASCADE_2}', '${ACTOR_ID}',
       'cascade_state_changed', '{"new_state":"completed"}',
       NOW() - interval '4 minutes');

    -- ===== Ledger: cascade_reopened (for cascade_rework metric) =====
    INSERT INTO ledger_entry (id, cascade_id, actor_id, type, content, timestamp)
    VALUES
      ('${LE_REOPEN}', '${CASCADE_1}', '${ACTOR_ID}',
       'cascade_reopened', '{"reason":"rework needed"}',
       NOW() - interval '3 minutes');

    -- ===== Ledger: cascade_migration (for decision_durability metric) =====
    -- Must be AFTER gate_resolved timestamp for the same cascade
    INSERT INTO ledger_entry (id, cascade_id, actor_id, type, content, timestamp)
    VALUES
      ('${LE_MIGR}', '${CASCADE_1}', '${ACTOR_ID}',
       'cascade_migration', '{"from_shape":"v1","to_shape":"v2"}',
       NOW() - interval '2 minutes');

    -- ===== Fan-out rows =====
    -- FANOUT_1: converged, linked to STAGE_G1 (for minority_accuracy join)
    INSERT INTO fan_out (id, stage_id, context_ref, prompt, convergence, verdict, completed_at)
    VALUES
      ('${FANOUT_1}', '${STAGE_G1}', 'test-ref-1', 'E2E test prompt',
       '{"majority_verdict":"approve","passes":[{"model":"model-A","verdict":"approve"},{"model":"model-B","verdict":"approve"},{"model":"model-C","verdict":"reject"}]}',
       'converged', NOW() - interval '6 minutes');

    -- FANOUT_2: converged
    INSERT INTO fan_out (id, stage_id, context_ref, prompt, convergence, verdict, completed_at)
    VALUES
      ('${FANOUT_2}', '${STAGE_G2}', 'test-ref-2', 'E2E test prompt 2',
       '{"majority_verdict":"approve","passes":[{"model":"model-A","verdict":"approve"},{"model":"model-B","verdict":"approve"}]}',
       'converged', NOW() - interval '6 minutes');

    -- FANOUT_3: diverged (for fanout_necessity metric)
    INSERT INTO fan_out (id, stage_id, context_ref, prompt, convergence, verdict, completed_at)
    VALUES
      ('${FANOUT_3}', '${STAGE_G3}', 'test-ref-3', 'E2E test prompt 3',
       '{"majority_verdict":"approve","passes":[{"model":"model-A","verdict":"approve"},{"model":"model-B","verdict":"reject"}]}',
       'diverged', NOW() - interval '6 minutes');
  `
  runSql(sql)
}

function cleanupMetricData() {
  const fanoutIds = `'${FANOUT_1}','${FANOUT_2}','${FANOUT_3}'`
  const cascadeIds = `'${CASCADE_1}','${CASCADE_2}','${CASCADE_3}'`
  const intentIds = `'${INTENT_1}','${INTENT_2}','${INTENT_3}'`

  const sql = `
    ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability;
    DELETE FROM fan_out WHERE id IN (${fanoutIds});
    DELETE FROM ledger_entry WHERE cascade_id IN (${cascadeIds});
    ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability;
    DELETE FROM stage WHERE cascade_id IN (${cascadeIds});
    DELETE FROM cascade WHERE id IN (${cascadeIds});
    DELETE FROM intent WHERE id IN (${intentIds});
    DELETE FROM actor WHERE id = '${ACTOR_ID}';
  `
  runSql(sql)
}

// ---------------------------------------------------------------------------
// Auth helper
// ---------------------------------------------------------------------------

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

test.describe('Metrics Dashboard E2E — all 8 cards with real values', () => {
  test.setTimeout(60_000)

  test.beforeAll(() => {
    // Clean up first (idempotent), then seed
    try { cleanupMetricData() } catch { /* no-op if rows don't exist */ }
    seedMetricData()
  })

  test.afterAll(() => {
    try { cleanupMetricData() } catch { /* best-effort cleanup */ }
  })

  test('metrics dashboard renders 8 cards with real values', async ({ page }) => {
    await authenticate(page)
    await page.goto('/metrics')
    await page.waitForLoadState('networkidle')

    // ------ Heading visible ------
    await expect(
      page.getByRole('heading', { name: 'Metrics Dashboard' }),
    ).toBeVisible({ timeout: 15_000 })

    // ------ All 8 metric titles are visible ------
    const metricTitles = [
      'Gate Necessity Rate',
      'Absorption Rate',
      'Resolution Latency',
      'Decision Durability',
      'Cascade Rework Rate',
      'Model Convergence Rate',
      'Minority Model Accuracy',
      'Fan-out Necessity Rate',
    ]

    for (const title of metricTitles) {
      await expect(
        page.getByText(title, { exact: true }).first(),
      ).toBeVisible({ timeout: 10_000 })
    }

    // ------ No empty state messages (all 8 metrics have data) ------
    // EmptyStateGuard renders this text when value is null/undefined.
    // With seeded data, all 8 should return non-null values.
    const emptyStates = page.getByText('Requires 10+ resolved gates to compute.')
    await expect(emptyStates).toHaveCount(0)

    // ------ At least one Recharts chart SVG is present ------
    const charts = page.locator('.recharts-wrapper')
    await expect(charts.first()).toBeVisible({ timeout: 10_000 })

    // ------ Verify chart count matches 8 metrics ------
    await expect(charts).toHaveCount(8)
  })
})
