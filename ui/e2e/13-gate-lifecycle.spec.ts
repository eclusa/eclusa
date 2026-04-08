/**
 * Gate Lifecycle E2E — GATE-E2E-03
 *
 * Proves that the back office Gates view displays a pending (blocked) gate
 * with its context and model recommendation, and that after resolution via
 * the API the gate disappears from the blocked filter view.
 */
import { execSync } from 'child_process'
import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

// Deterministic UUIDs for seeding / cleanup
const ACTOR_UUID   = 'e2e00009-0000-0000-0000-000000000001'
const INTENT_UUID  = 'e2e00009-0000-0000-0000-000000000002'
const CASCADE_UUID = 'e2e00009-0000-0000-0000-000000000003'
const GATE_UUID    = 'e2e00009-0000-0000-0000-000000000004'

// ---------------------------------------------------------------------------
// DB helpers — psql via docker exec (no host psql binary)
// ---------------------------------------------------------------------------

function runSql(sql: string) {
  execSync(
    `docker exec -i eclusa-db-1 psql -U eclusa -d eclusa`,
    { input: sql, stdio: ['pipe', 'pipe', 'pipe'] },
  )
}

function seedGate() {
  const sql = `
    INSERT INTO actor (id, type, identity, permissions)
    VALUES ('${ACTOR_UUID}', 'system', 'e2e-gate-lifecycle', '{"resolve_gates":["*"],"view_costs":true}')
    ON CONFLICT DO NOTHING;

    INSERT INTO intent (id, source, raw, created_by)
    VALUES ('${INTENT_UUID}', 'api', 'E2E gate lifecycle test', '${ACTOR_UUID}');

    INSERT INTO cascade (id, intent_id, shape, state)
    VALUES ('${CASCADE_UUID}', '${INTENT_UUID}', '{"test":"gate_lifecycle"}', 'active');

    INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
    VALUES (
      '${GATE_UUID}', '${CASCADE_UUID}', 'gate', 'blocked', '{}'::uuid[],
      '{"gate_type":"default","gate_description":"E2E UI test gate - please approve","model_recommendation":"approve"}'::jsonb
    );

    INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
    VALUES (
      gen_random_uuid(), '${GATE_UUID}', '${CASCADE_UUID}', '${ACTOR_UUID}',
      'gate_surfaced',
      '{"stage_id":"${GATE_UUID}"}',
      '0002'
    );
  `
  runSql(sql)
}

function cleanupGate() {
  const sql = `
    ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability;
    DELETE FROM ledger_entry WHERE cascade_id = '${CASCADE_UUID}';
    ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability;

    DELETE FROM stage WHERE cascade_id = '${CASCADE_UUID}';
    DELETE FROM cascade WHERE id = '${CASCADE_UUID}';
    DELETE FROM intent WHERE id = '${INTENT_UUID}';
    DELETE FROM actor WHERE id = '${ACTOR_UUID}';
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

test.describe('Gate lifecycle — visibility and resolution', () => {
  test.beforeAll(() => {
    // Clean up first (idempotent) then seed
    try { cleanupGate() } catch { /* no-op if rows don't exist */ }
    seedGate()
  })

  test.afterAll(() => {
    try { cleanupGate() } catch { /* best-effort cleanup */ }
  })

  test('pending gate visible in UI, resolution removes from blocked list', async ({ page }) => {
    // ------- Phase 1: verify gate appears -------
    await authenticate(page)
    await page.goto('/gates')
    await page.waitForLoadState('networkidle')

    // Heading visible
    await expect(page.getByRole('heading', { name: 'Pending Gates' })).toBeVisible()

    // Gate UUID shown in a <code> element
    const gateCode = page.locator('code', { hasText: GATE_UUID })
    await expect(gateCode).toBeVisible({ timeout: 10_000 })

    // Gate description visible in the JSON <pre> context block
    const contextPre = page.locator('pre', { hasText: 'E2E UI test gate' })
    await expect(contextPre).toBeVisible()

    // Model recommendation badge — "approve" in an emerald badge
    const recommendBadge = page.locator('.text-emerald-300', { hasText: 'approve' })
    await expect(recommendBadge).toBeVisible()

    // "Resolve gate" button is visible
    await expect(page.getByRole('button', { name: 'Resolve gate' }).first()).toBeVisible()

    // ------- Phase 2: resolve via API -------
    const token = await getAuthToken(BASE_URL)
    const resolveResp = await fetch(`${BASE_URL}/api/gates/${GATE_UUID}/resolve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        token: '',
        decision: 'approved',
        actor_id: ACTOR_UUID,
      }),
    })
    expect(resolveResp.status).toBe(200)
    const resolveBody = await resolveResp.json()
    expect(resolveBody.status).toBe('resolved')

    // ------- Phase 3: verify gate gone from blocked view -------
    await page.reload()
    await page.waitForLoadState('networkidle')

    // Gate UUID should no longer appear (hook fetches state=blocked only)
    await expect(page.locator('code', { hasText: GATE_UUID })).toBeHidden({ timeout: 10_000 })

    // The page should show empty state OR other gates — but our gate is gone.
    // If no other gates exist, "No pending gates" is shown.
    const remainingGates = page.locator('code').filter({ hasText: /^[0-9a-f-]{36}$/ })
    const count = await remainingGates.count()
    if (count === 0) {
      await expect(page.getByText('No pending gates')).toBeVisible()
    }
  })
})
