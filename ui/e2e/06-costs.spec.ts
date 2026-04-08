import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

test.describe('Costs', () => {
  test('renders the cost cards', async ({ page }) => {
    await authenticate(page)
    await page.goto('/costs')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Cost dashboard' })).toBeVisible()
    // Empty state shows "No cost data yet" when DB has no sessions
    // With data it shows "Cost by cascade", "Cost by model", etc.
    await expect(page.locator('main')).toContainText(/No cost data yet|Cost by/)
  })
})
