import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

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
  // Wait for assistant response content to stream in
  const lastAssistant = page.locator('[data-role="assistant"]').last()
  const contentDiv = lastAssistant.locator('.whitespace-pre-wrap')
  await expect(contentDiv).not.toBeEmpty({ timeout: 30000 })
}

test.describe('Chat regressions — HAT issue fixes', () => {
  test('session persists across page navigation', async ({ page }) => {
    test.setTimeout(90000)
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Send a message to create a session
    await sendChatMessage(page, 'UAT navigation test — remember the code word "elephant"')

    // Wait for Ready state (streaming done)
    await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 15000 })

    // Navigate away
    await page.goto('/cascades')
    await page.waitForLoadState('networkidle')
    await expect(page.getByText(/cascades/i).first()).toBeVisible()

    // Navigate back to chat
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Thread list in submenu panel should show previous chat with preview
    const threadItem = page.locator('aside').getByText(/elephant/i).first()
    await expect(threadItem).toBeVisible({ timeout: 5000 })

    // Click the session to load it
    await threadItem.click()

    // Messages should load from DB — user message visible
    const userMessage = page.locator('[data-role="user"]')
    await expect(userMessage).toBeVisible({ timeout: 10000 })
    await expect(userMessage).toContainText('elephant')
  })

  test('session transcript shows content in sessions page', async ({ page }) => {
    test.setTimeout(60000)
    await authenticate(page)

    // First create a chat session with content
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')
    await sendChatMessage(page, 'UAT transcript test — this message should appear in the session viewer')
    await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 15000 })

    // Get session ID from the header badge (UUID pattern)
    const sessionBadge = page.locator('header').getByText(/^[0-9a-f]{8}-[0-9a-f]{4}-/)
    await expect(sessionBadge).toBeVisible({ timeout: 15000 })
    const sessionId = await sessionBadge.textContent()
    expect(sessionId).toBeTruthy()

    // Check transcript via API — should return messages, not empty
    const token = await getAuthToken(BASE_URL)
    const resp = await fetch(`http://localhost:8800/api/sessions/${sessionId}/messages`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.ok).toBe(true)
    const messages = await resp.json()
    expect(messages.length).toBeGreaterThanOrEqual(2) // user + assistant
    // User message should be present
    const userMsg = messages.find((m: { role: string }) => m.role === 'user')
    expect(userMsg).toBeTruthy()
    expect(JSON.stringify(userMsg.content)).toContain('transcript test')
  })

  test('API endpoints respond while sessions page has open WebSockets', async ({ page, context }) => {
    test.setTimeout(60000)
    await authenticate(page)

    // Open sessions page — this creates WebSocket connections
    await page.goto('/sessions')
    await page.waitForLoadState('networkidle')
    // Give WebSockets time to connect
    await page.waitForTimeout(3000)

    // Now verify other API endpoints still respond (pool not exhausted)
    const token = await getAuthToken(BASE_URL)

    const gatesResp = await fetch('http://localhost:8800/api/gates', {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(5000),
    })
    expect(gatesResp.ok).toBe(true)

    const cascadesResp = await fetch('http://localhost:8800/api/cascades', {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(5000),
    })
    expect(cascadesResp.ok).toBe(true)

    const costsResp = await fetch('http://localhost:8800/api/costs', {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(5000),
    })
    expect(costsResp.ok).toBe(true)
  })

  test('sessions page does not crash the React tree', async ({ page }) => {
    await authenticate(page)
    await page.goto('/sessions')
    await page.waitForLoadState('networkidle')

    // Page should render without white-screening
    // Check that the app shell sidebar is still visible (not crashed)
    await expect(page.getByText('Chat')).toBeVisible({ timeout: 5000 })
    await expect(page.getByText('Cascades')).toBeVisible()

    // Navigate to another page — should work (no stuck error boundary)
    await page.goto('/gates')
    await page.waitForLoadState('networkidle')
    await expect(page.getByText(/gates/i).first()).toBeVisible({ timeout: 5000 })
  })
})
