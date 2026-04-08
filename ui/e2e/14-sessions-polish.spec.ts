/**
 * Sessions UI Polish E2E — Phase 14 Plan 02
 *
 * Verifies three requirements from the sessions UI polish:
 *   UI-E2E-01: Three-column layout (nav | sessions submenu | transcript)
 *   UI-E2E-02: Status as colored dot, no text badges, no cost pill
 *   UI-E2E-03: Session titles are human-readable, not raw UUIDs
 */
import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

async function sendChatMessage(page: Page, text: string) {
  const input = page.getByPlaceholder(/describe the work/i)
  await input.fill(text)
  await page.getByRole('button', { name: /send/i }).click()
  // Wait for assistant response to stream in
  const lastAssistant = page.locator('[data-role="assistant"]').last()
  const contentDiv = lastAssistant.locator('.whitespace-pre-wrap')
  await expect(contentDiv).not.toBeEmpty({ timeout: 45000 })
}

test.describe('Sessions UI Polish -- Phase 14', () => {
  // Test 1: Three-column layout (UI-E2E-01)
  // This test also creates a session so subsequent tests have data
  test('sessions page has three-column submenu layout', async ({ page }) => {
    test.setTimeout(90000)
    await authenticate(page)

    // Create a chat session so there is at least one work_session in DB
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')
    await sendChatMessage(page, 'Sessions UI Polish E2E test — layout verification')
    await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 20000 })

    // Navigate to /sessions
    await page.goto('/sessions')
    await page.waitForLoadState('networkidle')

    // Column 1: Nav sidebar is present (left navigation)
    await expect(page.getByText('Chat')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('Cascades')).toBeVisible()

    // Column 2: Sessions submenu is visible
    const submenu = page.locator('[data-testid="sessions-submenu"]')
    await expect(submenu).toBeVisible({ timeout: 10000 })

    // At least one session item exists in the submenu
    const firstSessionItem = page.locator('[data-testid="session-item"]').first()
    await expect(firstSessionItem).toBeVisible({ timeout: 10000 })

    // Column 3: Main content area renders (empty-state message or transcript)
    // When no session is selected, the empty state is shown
    await expect(
      page.getByText('Select a session from the list'),
    ).toBeVisible({ timeout: 5000 })
  })

  // Test 2: Status as colored dot, no text badges, no cost pill (UI-E2E-02)
  test('session status is colored dot, no badges or cost pill', async ({ page }) => {
    test.setTimeout(60000)
    await authenticate(page)

    await page.goto('/sessions')
    await page.waitForLoadState('networkidle')

    // Wait for session items to load
    const firstSessionItem = page.locator('[data-testid="session-item"]').first()
    await expect(firstSessionItem).toBeVisible({ timeout: 15000 })

    // Status dot is present inside the session item
    const statusDot = firstSessionItem.locator('[data-testid="status-dot"]')
    await expect(statusDot).toBeVisible()

    // Status dot has a valid data-status attribute
    const statusValue = await statusDot.getAttribute('data-status')
    expect(statusValue).toBeTruthy()
    expect(['running', 'completed', 'failed', 'paused', 'error']).toContain(statusValue)

    // No standalone text badge with status text (text-only badges are absent)
    // Assert: no element with only the raw status word as its text content
    await expect(
      firstSessionItem.locator('text=/^(running|completed|failed)$/i'),
    ).toHaveCount(0)

    // No cost pill — USD amount pattern must not appear anywhere in session items
    const allSessionItems = page.locator('[data-testid="session-item"]')
    const count = await allSessionItems.count()
    for (let i = 0; i < count; i++) {
      const item = allSessionItems.nth(i)
      // Check text content for USD pattern
      const text = await item.textContent()
      expect(text ?? '').not.toMatch(/\d+\.\d+\s*USD/i)
    }
  })

  // Test 3: Session titles are human-readable, not raw UUIDs (UI-E2E-03)
  test('sessions display generated titles not UUIDs', async ({ page }) => {
    test.setTimeout(60000)
    await authenticate(page)

    await page.goto('/sessions')
    await page.waitForLoadState('networkidle')

    // Wait for session titles to load
    const firstTitle = page.locator('[data-testid="session-title"]').first()
    await expect(firstTitle).toBeVisible({ timeout: 15000 })

    const titleText = await firstTitle.textContent()
    expect(titleText).toBeTruthy()

    // Title must not be a bare UUID
    const trimmedTitle = (titleText ?? '').trim()
    expect(trimmedTitle.length).toBeGreaterThan(0)
    expect(trimmedTitle).not.toMatch(UUID_PATTERN)

    // Verify all visible titles are non-UUID human-readable text
    const allTitles = page.locator('[data-testid="session-title"]')
    const titleCount = await allTitles.count()
    for (let i = 0; i < titleCount; i++) {
      const title = await allTitles.nth(i).textContent()
      const trimmed = (title ?? '').trim()
      if (trimmed.length > 0) {
        expect(trimmed).not.toMatch(UUID_PATTERN)
      }
    }
  })

  // Test 4: Clicking a session loads its transcript (functional verification)
  test('clicking a session loads its transcript', async ({ page }) => {
    test.setTimeout(60000)
    await authenticate(page)

    await page.goto('/sessions')
    await page.waitForLoadState('networkidle')

    // Wait for session items
    const firstSessionItem = page.locator('[data-testid="session-item"]').first()
    await expect(firstSessionItem).toBeVisible({ timeout: 15000 })

    // Click the first session item
    await firstSessionItem.click()

    // URL should update to /sessions/<uuid>
    await page.waitForURL(
      /\/sessions\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
      { timeout: 10000 },
    )

    // Transcript section is rendered
    const transcriptSection = page.locator('[data-testid="session-transcript"]')
    await expect(transcriptSection).toBeVisible({ timeout: 10000 })

    // At minimum, the Transcript card heading must be visible — proves transcript area loaded
    await expect(page.getByText('Transcript', { exact: true }).first()).toBeVisible({ timeout: 10000 })
  })

  // Test 5: Submenu toggles between ChatSubMenu and SessionsSubMenu on navigation
  test('submenu shows sessions list on /sessions and chat list on /chat', async ({ page }) => {
    test.setTimeout(60000)
    await authenticate(page)

    // Start at /sessions — SessionsSubMenu should be visible
    await page.goto('/sessions')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('[data-testid="sessions-submenu"]')).toBeVisible({ timeout: 10000 })

    // Navigate to /chat — ChatSubMenu should replace it, no sessions-submenu
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // The sessions-submenu should no longer be visible on the chat page
    await expect(page.locator('[data-testid="sessions-submenu"]')).not.toBeVisible({ timeout: 5000 })

    // Navigate back to /sessions — SessionsSubMenu reappears
    await page.goto('/sessions')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('[data-testid="sessions-submenu"]')).toBeVisible({ timeout: 10000 })
  })
})
