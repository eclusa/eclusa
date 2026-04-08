import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from '@/pages/DashboardPage'
import { vi } from 'vitest'

vi.mock('@/api/cascades', () => ({
  useActiveCascades: () => ({
    data: [
      {
        id: 'cascade-1',
        title: 'Release Gate Review',
        state: 'active',
        created_at: '2026-04-05T10:00:00.000Z',
        stage_count: 4,
        blocked_stage_count: 1,
      },
    ],
    isLoading: false,
    error: null,
  }),
}))

test('dashboard renders active cascades with status badges', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )

  expect(html).toContain('Active Cascades')
  expect(html).toContain('Release Gate Review')
  expect(html).toContain('4 stages')
  expect(html).toContain('1 blocked')
  expect(html).toContain('bg-blue-900/40')
})
