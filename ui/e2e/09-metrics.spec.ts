import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

test.describe('Metrics', () => {
  test('renders the metric cards', async ({ page }) => {
    await authenticate(page)
    await page.goto('/metrics')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Metrics Dashboard' })).toBeVisible()
    await expect(page.getByText('Gate Necessity Rate')).toBeVisible()
    await expect(page.getByText('Fan-out Necessity Rate')).toBeVisible()
  })
})
