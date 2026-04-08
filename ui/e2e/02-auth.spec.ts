import { expect, test } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

test.describe('Authentication', () => {
  test('issues a JWT and authorizes the cascades API', async ({ request }) => {
    const token = await getAuthToken('http://localhost:8000')
    expect(token).toBeTruthy()

    const response = await request.get('/api/cascades', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })

    expect(response.status()).toBeLessThan(500)
    expect(response.status()).not.toBe(401)
    const body = await response.json()
    expect(Array.isArray(body)).toBe(true)
  })
})
