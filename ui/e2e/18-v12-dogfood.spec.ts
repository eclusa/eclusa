import { test, expect, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

test.describe('v1.2 Dogfood UAT', () => {
  let token: string

  test.beforeAll(async () => {
    token = await getAuthToken(BASE_URL)
  })

  // --- Build Mode (Phase 17 UI) ---

  test('build mode toggle is visible on chat page', async ({ page }) => {
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    const toggle = page.getByRole('button', { name: /build mode/i })
    await expect(toggle).toBeVisible({ timeout: 10_000 })
    await expect(toggle).toContainText('OFF')
  })

  test('build mode creates SCC cascade', async ({ page }) => {
    test.setTimeout(60_000)
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Toggle build mode ON
    const toggle = page.getByRole('button', { name: /build mode/i })
    await toggle.click()
    await expect(toggle).toContainText('ON')

    // Send a build intent
    const input = page.locator('textarea, input[type="text"]').first()
    await input.fill('Build a simple todo app with React and FastAPI')
    await input.press('Enter')

    // Should get cascade_id confirmation
    const cascadeMsg = page.locator('[data-role="assistant"]').last()
    await expect(cascadeMsg).toContainText('cascade', { timeout: 30_000 })
  })

  test('chat mode still streams response', async ({ page }) => {
    test.setTimeout(90_000)
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Ensure build mode is OFF (default)
    const toggle = page.getByRole('button', { name: /build mode/i })
    await expect(toggle).toContainText('OFF')

    // Send a chat message
    const input = page.locator('textarea, input[type="text"]').first()
    await input.fill('What is 2 plus 2?')
    await input.press('Enter')

    // Should get a streamed assistant response (not "cascade created")
    const assistantMsg = page.locator('[data-role="assistant"]').last()
    await expect(assistantMsg).not.toBeEmpty({ timeout: 60_000 })
    const text = await assistantMsg.textContent()
    expect(text).not.toContain('cascade_id')
  })

  // --- Model Config Panel (Phase 15 UI) ---

  test('advanced model config panel hidden by default', async ({ page }) => {
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Panel should not be visible
    const panel = page.locator('text=Default SCC model')
    await expect(panel).not.toBeVisible()

    // Toggle button should exist
    const toggleBtn = page.getByRole('button', { name: /scc model config/i })
    await expect(toggleBtn).toBeVisible()
  })

  test('advanced model config panel opens on click', async ({ page }) => {
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    const toggleBtn = page.getByRole('button', { name: /scc model config/i })
    await toggleBtn.click()

    // Panel with selectors should now be visible
    await expect(page.locator('text=Default SCC model')).toBeVisible({ timeout: 5_000 })
    await expect(page.locator('text=refine')).toBeVisible()
    await expect(page.locator('text=generate')).toBeVisible()
  })

  // --- Cascade Pipeline (Phase 18 UI) ---

  test('cascades page loads', async ({ page }) => {
    await authenticate(page)
    await page.goto('/cascades')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('body')).not.toContainText('Application error', { timeout: 10_000 })
  })

  test('cascade detail shows pipeline stages', async ({ page }) => {
    test.setTimeout(30_000)

    // Create a cascade via API
    const createResp = await fetch(`${BASE_URL}/api/scc/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ intent_text: 'UAT test cascade for pipeline view' }),
    })

    if (!createResp.ok) {
      test.skip(true, 'Could not create SCC cascade for pipeline test')
      return
    }

    const { cascade_id } = await createResp.json()

    await authenticate(page)
    await page.goto(`/cascades/${cascade_id}`)
    await page.waitForLoadState('networkidle')

    // Pipeline should show stage labels — verify they exist in DOM (may be clipped by overflow)
    await expect(page.getByText('Refine').first()).toBeAttached({ timeout: 15_000 })
    await expect(page.getByText('Cohere').first()).toBeAttached()
  })
})
