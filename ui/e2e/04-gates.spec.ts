import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

test.describe('Gates', () => {
  test('renders the gates list or empty state', async ({ page }) => {
    await authenticate(page)
    await page.goto('/gates')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Pending Gates' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Blocked' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'All' })).toBeVisible()
  })
})
