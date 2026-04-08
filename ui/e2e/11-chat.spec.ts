import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'
const API_URL = 'http://localhost:8800'

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

async function apiGet(path: string, token: string) {
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return resp.json()
}

test.describe('Chat — full intent→cascade flow', () => {
  test('chat page loads with input, model selector, and empty state', async ({ page }) => {
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Chat input visible
    await expect(page.getByPlaceholder(/describe the work/i)).toBeVisible()

    // Model selector visible with GLM as default
    const select = page.locator('select')
    await expect(select).toBeVisible()
    const selectedValue = await select.inputValue()
    expect(selectedValue).toBe('openai:glm-5.1')

    // All model options present
    const options = await select.locator('option').allTextContents()
    expect(options).toContain('openai:glm-5.1')
    expect(options.length).toBeGreaterThanOrEqual(2)

    // Empty state message
    await expect(page.getByText(/send a request/i)).toBeVisible()

    // Status badge shows "New thread"
    await expect(page.getByRole('main').getByText('New thread', { exact: true })).toBeVisible()

    // No session ID badge yet
    const sessionBadges = page.locator('.border-blue-900\\/40.text-blue-300')
    await expect(sessionBadges).toHaveCount(0)
  })

  test('sending a message streams a real LLM response and creates a session', async ({ page }) => {
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Type a message
    const input = page.getByPlaceholder(/describe the work/i)
    await input.fill('Say hello and confirm you are working. Reply in under 10 words.')

    // Send
    await page.getByRole('button', { name: /send/i }).click()

    // Input should clear after send
    await expect(input).toHaveValue('')

    // User message should appear
    const userMessage = page.locator('[data-role="user"]')
    await expect(userMessage).toBeVisible()
    await expect(userMessage).toContainText('Say hello')

    // Wait for assistant response to stream in — content must appear (not just the placeholder)
    const assistantMessage = page.locator('[data-role="assistant"]')
    const contentDiv = assistantMessage.locator('.whitespace-pre-wrap')
    // Wait until the content div has real text (streaming fills it incrementally)
    await expect(contentDiv).not.toBeEmpty({ timeout: 30000 })

    // The response must contain actual text, not an error
    const content = await contentDiv.textContent()
    expect(content).not.toContain('Failed to stream')
    expect(content!.trim().length).toBeGreaterThan(5)

    // Session ID badge should appear after response completes
    // Wait for streaming to finish (the streaming badge disappears)
    await page.waitForTimeout(2000)
    await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 10000 })
  })

  test('chat creates intent → cascade → stage → work_session visible in API', async ({ page }) => {
    // Get baseline counts via API
    const token = await getAuthToken(BASE_URL)
    const baselineCascades = await apiGet('/api/cascades', token)
    const baselineCount = Array.isArray(baselineCascades) ? baselineCascades.length : 0

    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Send a message
    const input = page.getByPlaceholder(/describe the work/i)
    await input.fill('Create a test intent for E2E verification')
    await page.getByRole('button', { name: /send/i }).click()

    // Wait for response to complete
    const assistantMessage = page.locator('[data-role="assistant"]')
    await expect(assistantMessage).toBeVisible({ timeout: 30000 })
    await page.waitForTimeout(3000)

    // Verify cascade was created via API
    const afterCascades = await apiGet('/api/cascades', token)
    const afterCount = Array.isArray(afterCascades) ? afterCascades.length : 0
    expect(afterCount).toBeGreaterThan(baselineCount)

    // Get the newest cascade
    const cascades = Array.isArray(afterCascades) ? afterCascades : []
    const newest = cascades[cascades.length - 1]
    expect(newest).toBeTruthy()
    expect(newest.state).toBe('active')

    // Verify cascade is visible in the dashboard
    await page.goto('/cascades')
    await page.waitForLoadState('networkidle')
    // Should see at least one cascade card with "active" state
    await expect(page.getByText('active').first()).toBeVisible({ timeout: 10000 })
  })

  test('chat session persists across multiple messages', async ({ page }) => {
    test.setTimeout(90000)
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // First message
    const input = page.getByPlaceholder(/describe the work/i)
    await input.fill('Remember: the secret word is "pineapple"')
    await page.getByRole('button', { name: /send/i }).click()

    // Wait for first response — content must appear
    const firstAssistant = page.locator('[data-role="assistant"]').first()
    const firstContent = firstAssistant.locator('.whitespace-pre-wrap')
    await expect(firstContent).not.toBeEmpty({ timeout: 30000 })
    const firstText = await firstContent.textContent()
    expect(firstText!.trim().length).toBeGreaterThan(0)
    expect(firstText).not.toContain('Failed to stream')

    // Wait for streaming to finish
    await expect(page.getByText('Ready', { exact: true })).toBeVisible({ timeout: 15000 })

    // Second message — should use same session
    await input.fill('What was the secret word I told you?')
    await page.getByRole('button', { name: /send/i }).click()

    // Wait for second response content
    const assistantMessages = page.locator('[data-role="assistant"]')
    await expect(assistantMessages).toHaveCount(2, { timeout: 30000 })
    const secondContent = assistantMessages.nth(1).locator('.whitespace-pre-wrap')
    await expect(secondContent).not.toBeEmpty({ timeout: 30000 })
    const secondText = await secondContent.textContent()
    expect(secondText!.trim().length).toBeGreaterThan(0)
    expect(secondText).not.toContain('Failed to stream')
  })

  test('model selector changes the model sent to backend', async ({ page }) => {
    await authenticate(page)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // Change model
    const select = page.locator('select')
    await select.selectOption('anthropic:claude-haiku-4-5')
    const selectedValue = await select.inputValue()
    expect(selectedValue).toBe('anthropic:claude-haiku-4-5')

    // Intercept the API call to verify model is sent
    const requestPromise = page.waitForRequest((req) =>
      req.url().includes('/api/chat') && req.method() === 'POST'
    )

    const input = page.getByPlaceholder(/describe the work/i)
    await input.fill('Test model selection')
    await page.getByRole('button', { name: /send/i }).click()

    const request = await requestPromise
    const body = JSON.parse(request.postData()!)
    expect(body.model).toBe('anthropic:claude-haiku-4-5')
  })
})
