import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { GatesPage } from '@/pages/GatesPage'
import { vi } from 'vitest'

vi.mock('@/auth/AuthProvider', () => ({
  useAuth: () => ({
    token: 'header.eyJhY3Rvcl9pZCI6Im9wZXJhdG9yIn0.signature',
    getAuthHeader: () => ({ Authorization: 'Bearer test-token' }),
  }),
}))

vi.mock('@/api/gates', () => ({
  usePendingGates: () => ({
    data: [
      {
        id: 'gate-1',
        cascade_id: 'cascade-1',
        state: 'blocked',
        created_at: '2026-04-05T10:00:00.000Z',
        model_recommendation: 'approve',
        input: {
          gate_type: 'review',
          context: { note: 'check this' },
        },
      },
    ],
    isLoading: false,
    error: null,
  }),
  useResolveGate: () => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  }),
}))

test('gates page renders pending gates with context and resolve controls', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <GatesPage />
    </MemoryRouter>,
  )

  expect(html).toContain('Pending Gates')
  expect(html).toContain('gate-1')
  expect(html).toContain('cascade-1')
  expect(html).toContain('approve')
  expect(html).toContain('Resolve gate')
  expect(html).toContain('bg-amber-900/40')
})
