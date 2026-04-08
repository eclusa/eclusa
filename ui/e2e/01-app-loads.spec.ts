import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'
const SECRET = 'eclusa-dev-secret-0123456789012345678901234'

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
  return token
}

test.describe('App shell', () => {
  test('redirects unauthenticated users to /login', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Should redirect to /login, not show the dashboard
    await expect(page).toHaveURL(/\/login/)
  })

  test('login form authenticates and redirects to dashboard', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    // Fill in the secret and submit
    await page.getByPlaceholder(/secret/i).fill(SECRET)
    await page.getByRole('button', { name: /sign in|log in|enter/i }).click()
    await page.waitForLoadState('networkidle')

    // Should redirect to cascades dashboard
    await expect(page).toHaveURL(/\/cascades/, { timeout: 10000 })
    await expect(page.getByRole('heading', { name: 'Active Cascades' })).toBeVisible()
  })

  test('loads the back office shell at the root route (pre-authed)', async ({ page }) => {
    await authenticate(page)
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('aside')).toBeVisible()
    await expect(page.locator('main')).toBeVisible()
    await expect(page.getByText('ECLUSA')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Cascades' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Active Cascades' })).toBeVisible()
  })
})
