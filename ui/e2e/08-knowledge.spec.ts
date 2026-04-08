import { expect, test, type Page } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'

async function authenticate(page: Page) {
  const token = await getAuthToken(BASE_URL)
  await page.addInitScript((value) => {
    window.localStorage.setItem('eclusa_token', value)
  }, token)
}

test.describe('Knowledge', () => {
  test('renders the search bar and entity list area', async ({ page }) => {
    await authenticate(page)
    await page.goto('/knowledge')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Knowledge Browser' })).toBeVisible()
    await expect(page.getByPlaceholder('Search entities...')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Entities' })).toBeVisible()

    await page.getByPlaceholder('Search entities...').fill('cascade')
    await page.waitForTimeout(400)

    const entityRows = page.locator('main button[aria-expanded]')
    if (await entityRows.count()) {
      await expect(entityRows.first()).toBeVisible()
    } else {
      await expect(page.locator('main')).toContainText(/Searching entities\.{3}|No entities matched your search\.|Failed to load entities/)
    }
  })
})
