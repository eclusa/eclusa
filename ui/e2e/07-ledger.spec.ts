import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

test.describe('Ledger', () => {
  test('renders the AS OF picker and table', async ({ page }) => {
    await authenticate(page)
    await page.goto('/ledger')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Ledger').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Now' })).toBeVisible()
  })
})
