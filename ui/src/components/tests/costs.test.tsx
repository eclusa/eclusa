import { renderToStaticMarkup } from 'react-dom/server'
import { vi } from 'vitest'
import { CostsPage } from '@/pages/CostsPage'

vi.mock('@/api/costs', () => ({
  useCostSummary: () => ({
    data: {
      by_cascade: [
        { cascade_id: 'cascade-1', total_tokens_in: 100, total_tokens_out: 25, total_usd: 0.0102 },
      ],
      by_session: [
        { session_id: 'session-1', total_tokens_in: 50, total_tokens_out: 20, total_usd: 0.0041 },
        { session_id: 'session-2', total_tokens_in: 80, total_tokens_out: 30, total_usd: 0.0061 },
      ],
      by_model: [
        { model: 'gpt-5.4', total_tokens_in: 180, total_tokens_out: 55, total_usd: 0.0163, session_count: 2 },
      ],
    },
    isLoading: false,
    error: null,
  }),
}))

test('CostsPage renders chart sections', () => {
  const html = renderToStaticMarkup(<CostsPage />)

  expect(html).toContain('Cost dashboard')
  expect(html).toContain('Cost by cascade')
  expect(html).toContain('Cost by model')
  expect(html).toContain('Cumulative spend over time')
  expect(html).toContain('cost-by-cascade-chart')
})
