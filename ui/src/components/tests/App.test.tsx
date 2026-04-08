import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/auth/AuthProvider'
import { AppRoutes } from '@/App'
import { QueryClient } from '@tanstack/react-query'
import { vi } from 'vitest'

vi.mock('@/api/cascades', () => ({
  useActiveCascades: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
}))

test('app renders sidebar and cascades route', () => {
  const html = renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/cascades']}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )

  expect(html).toContain('ECLUSA')
  expect(html).toContain('Active Cascades')
})
