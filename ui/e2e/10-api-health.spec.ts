import { expect, test } from '@playwright/test'
import { getAuthToken } from './helpers/auth'

const BASE_URL = 'http://localhost:8000'
const ZERO_UUID = '00000000-0000-0000-0000-000000000000'

test.describe('API health', () => {
  test('authenticates and keeps all protected endpoints below 500', async ({ request }) => {
    const token = await getAuthToken(BASE_URL)
    const headers = {
      Authorization: `Bearer ${token}`,
    }

    const responses = await Promise.all([
      request.get('/api/cascades', { headers }),
      request.get(`/api/cascades/${ZERO_UUID}`, { headers }),
      request.get('/api/gates', { headers }),
      request.post(`/api/gates/${ZERO_UUID}/resolve`, {
        headers,
        data: {
          token: 'not-a-real-token',
          decision: 'approved',
          actor_id: ZERO_UUID,
        },
      }),
      request.get('/api/sessions', { headers }),
      request.get(`/api/sessions/${ZERO_UUID}/messages`, { headers }),
      request.get('/api/costs', { headers }),
      request.get('/api/ledger', { headers }),
      request.get('/api/knowledge/entities?q=e2e', { headers }),
      request.get(`/api/knowledge/facts?entity_id=${ZERO_UUID}`, { headers }),
      request.get('/api/knowledge/communities', { headers }),
      request.get('/api/metrics', { headers }),
    ])

    for (const response of responses) {
      expect(response.status()).toBeLessThan(500)
    }
  })
})
