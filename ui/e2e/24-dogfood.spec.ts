/**
 * Phase 24 Dogfood E2E — Playwright
 *
 * Proves the full user journey works before a human touches it:
 *   - Registration page loads and redirects on submit (ID-01, ID-02)
 *   - Build mode routes to the refine agent, not instant cascade creation (PIPE-01, TRIGGER-01)
 *   - Chat mode remains unaffected by build mode toggle
 *
 * Uses the new register-based auth (POST /api/auth/register) instead of the
 * old shared-secret token endpoint.
 *
 * Requires: docker compose up (db + api on :8000, UI on :5173)
 */

import { test, expect, type Page } from '@playwright/test'

const API_BASE = 'http://localhost:8000'
const UI_BASE = 'http://localhost:5173'

// ---------------------------------------------------------------------------
// Auth helpers — register-based (Phase 20 pattern)
// ---------------------------------------------------------------------------

let _registeredEmail: string | null = null
let _registeredToken: string | null = null

function _uniqueEmail(): string {
  return `e2e-pw-${Math.random().toString(36).slice(2, 10)}@test.invalid`
}

async function registerUser(
  email: string,
  { name = 'E2E Playwright', password = 'testpass123' } = {}
): Promise<string> {
  const resp = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, name, password }),
  })
  if (!resp.ok) {
    throw new Error(`Register failed ${resp.status}: ${await resp.text()}`)
  }
  const data = await resp.json()
  return data.access_token as string
}

async function authenticatePage(page: Page, token: string): Promise<void> {
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

// ---------------------------------------------------------------------------
// Registration flow tests
// ---------------------------------------------------------------------------

test.describe('Registration flow', () => {
  test('register page loads with required fields', async ({ page }) => {
    await page.goto(`${UI_BASE}/register`)
    await page.waitForLoadState('networkidle')

    // The page must not crash
    await expect(page.locator('body')).not.toContainText('Application error', {
      timeout: 10_000,
    })

    // Email, name, and password fields must be present
    await expect(page.locator('input[type="email"], input[name="email"]').first()).toBeVisible({
      timeout: 10_000,
    })
    await expect(
      page.locator('input[name="name"], input[placeholder*="name" i]').first()
    ).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('input[type="password"]').first()).toBeVisible({
      timeout: 10_000,
    })
  })

  test('register and redirect to /chat with valid session', async ({ page }) => {
    test.setTimeout(30_000)

    const email = _uniqueEmail()
    await page.goto(`${UI_BASE}/register`)
    await page.waitForLoadState('networkidle')

    // Fill registration form
    const emailInput = page.locator('input[type="email"], input[name="email"]').first()
    const nameInput = page.locator('input[name="name"], input[placeholder*="name" i]').first()
    const passwordInput = page.locator('input[type="password"]').first()
    const submitBtn = page.locator('button[type="submit"]').first()

    await emailInput.fill(email)
    await nameInput.fill('Playwright Dogfood')
    await passwordInput.fill('testpass123')
    await submitBtn.click()

    // After successful registration, must redirect to /chat (or /)
    await page.waitForURL(/\/(chat|$)/, { timeout: 15_000 })

    // Token must be stored in localStorage
    const token = await page.evaluate(() =>
      window.localStorage.getItem('eclusa_token')
    )
    expect(token).toBeTruthy()
    expect(token).not.toBe('')

    // Cleanup: delete registered actor via API (best-effort)
    try {
      await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name: 'dup', password: 'dup' }),
      })
      // Second register returns 409 — that's fine, just confirms actor exists
    } catch {
      // ignore
    }
  })
})

// ---------------------------------------------------------------------------
// Build mode flow tests
// ---------------------------------------------------------------------------

test.describe('Build mode — full flow', () => {
  let token: string

  test.beforeAll(async () => {
    const email = _uniqueEmail()
    token = await registerUser(email)
    _registeredEmail = email
    _registeredToken = token
  })

  test('build mode toggle is visible and defaults to OFF', async ({ page }) => {
    await authenticatePage(page, token)
    await page.goto(`${UI_BASE}/chat`)
    await page.waitForLoadState('networkidle')

    await expect(page.locator('body')).not.toContainText('Application error', {
      timeout: 10_000,
    })

    const toggle = page.getByRole('button', { name: /build mode/i })
    await expect(toggle).toBeVisible({ timeout: 10_000 })
    await expect(toggle).toContainText('OFF')
  })

  test('build mode streams refine agent response — not instant cascade creation', async ({
    page,
  }) => {
    test.setTimeout(90_000)

    await authenticatePage(page, token)
    await page.goto(`${UI_BASE}/chat`)
    await page.waitForLoadState('networkidle')

    // Toggle build mode ON
    const toggle = page.getByRole('button', { name: /build mode/i })
    await toggle.click()
    await expect(toggle).toContainText('ON', { timeout: 5_000 })

    // Send a build intent
    const input = page.locator('textarea, input[type="text"]').first()
    await input.fill('build me a todo app')
    await input.press('Enter')

    // The refine agent must respond with a clarifying question or message stream.
    // It must NOT immediately return a cascade_id JSON payload (that would be the
    // old create_scc instant path, which was superseded by the refine agent in PIPE-01).
    const assistantMsg = page.locator('[data-role="assistant"]').last()
    await expect(assistantMsg).not.toBeEmpty({ timeout: 60_000 })

    const responseText = await assistantMsg.textContent()

    // Agent response should contain question-like language, not raw JSON keys
    // It's acceptable to mention cascade in prose, but should NOT be raw JSON
    const isRawJson =
      responseText?.startsWith('{') && responseText.includes('"cascade_id"')
    expect(isRawJson).toBe(false)

    // Response must have some meaningful length (not empty/error)
    expect((responseText ?? '').length).toBeGreaterThan(10)
  })

  test('chat mode unaffected — normal response without cascade creation', async ({
    page,
  }) => {
    test.setTimeout(90_000)

    await authenticatePage(page, token)
    await page.goto(`${UI_BASE}/chat`)
    await page.waitForLoadState('networkidle')

    // Ensure build mode is OFF (default state on fresh navigation)
    const toggle = page.getByRole('button', { name: /build mode/i })
    await expect(toggle).toContainText('OFF', { timeout: 5_000 })

    // Send a plain chat message
    const input = page.locator('textarea, input[type="text"]').first()
    await input.fill('hello')
    await input.press('Enter')

    // Must get an assistant response (streamed)
    const assistantMsg = page.locator('[data-role="assistant"]').last()
    await expect(assistantMsg).not.toBeEmpty({ timeout: 60_000 })

    const text = await assistantMsg.textContent()
    // Chat mode must NOT create a cascade — no cascade_id in response
    expect(text).not.toContain('"cascade_id"')
  })
})

// ---------------------------------------------------------------------------
// Unhappy paths
// ---------------------------------------------------------------------------

test.describe('Auth unhappy paths', () => {
  test('accessing /chat without a token redirects or shows login prompt', async ({
    page,
  }) => {
    test.setTimeout(15_000)

    // Clear all storage to simulate unauthenticated user
    await page.goto(`${UI_BASE}/`)
    await page.evaluate(() => window.localStorage.clear())

    await page.goto(`${UI_BASE}/chat`)
    await page.waitForLoadState('networkidle')

    // Either redirected to /login or /register, or the page shows a login prompt
    const url = page.url()
    const isOnAuth = url.includes('/login') || url.includes('/register')
    const hasLoginText = await page
      .locator('body')
      .containsText(/log\s*in|sign\s*in|register/i)
      .catch(() => false)

    expect(isOnAuth || hasLoginText).toBe(true)
  })

  test('API 401 on gate resolve without bearer token', async () => {
    // Pure API test — no page needed
    const fakeId = '00000000-0000-0000-0000-000000000001'
    const resp = await fetch(`${API_BASE}/api/gates/${fakeId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verdict: 'approved', rationale: 'test', token: '' }),
    })
    expect(resp.status).toBe(401)
  })

  test('API 409 on duplicate email registration', async () => {
    const email = _uniqueEmail()
    // First registration succeeds
    const r1 = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name: 'First', password: 'pass1' }),
    })
    expect(r1.status).toBe(200)

    // Second registration with same email must return 409
    const r2 = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name: 'Second', password: 'pass2' }),
    })
    expect(r2.status).toBe(409)
  })

  test('SCC create with empty intent returns 422', async () => {
    const token = await registerUser(_uniqueEmail())
    const resp = await fetch(`${API_BASE}/api/scc/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ intent_text: '   ' }),
    })
    expect(resp.status).toBe(422)
  })

  test('/healthz returns 200 with pool stats', async () => {
    const resp = await fetch(`${API_BASE}/healthz`)
    expect(resp.status).toBe(200)
    const body = await resp.json()
    expect(body.status).toBe('ok')
    expect(body).toHaveProperty('pool_size')
    expect(body).toHaveProperty('pool_free')
  })
})
