import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/auth/AuthProvider'
import { fetchActiveCascades, fetchCascadeDetail } from '@/api/cascades'
import { fetchPendingGates, resolveGateRequest, useResolveGate } from '@/api/gates'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()

      if (url === '/api/cascades') {
        return new Response(JSON.stringify([{ id: 'c-1' }]), { status: 200 })
      }

      if (url === '/api/cascades/c-1') {
        return new Response(JSON.stringify({ id: 'c-1' }), { status: 200 })
      }

      if (url === '/api/gates?state=blocked') {
        return new Response(JSON.stringify([{ id: 'g-1' }]), { status: 200 })
      }

      if (url === '/api/gates/g-1/resolve') {
        return new Response(JSON.stringify({ ok: true }), { status: 200 })
      }

      return new Response('{}', { status: 404 })
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('cascade fetchers call the expected URLs with auth headers', async () => {
  await fetchActiveCascades({ Authorization: 'Bearer token' })
  await fetchCascadeDetail('c-1', { Authorization: 'Bearer token' })

  expect(fetch).toHaveBeenCalledWith('/api/cascades', { headers: { Authorization: 'Bearer token' } })
  expect(fetch).toHaveBeenCalledWith('/api/cascades/c-1', { headers: { Authorization: 'Bearer token' } })
})

test('gate fetchers and resolver call the expected URLs with auth headers', async () => {
  await fetchPendingGates({ Authorization: 'Bearer token' })
  await resolveGateRequest(
    { gateId: 'g-1', decision: 'approve', actorId: 'operator', token: '' },
    { Authorization: 'Bearer token' },
  )

  expect(fetch).toHaveBeenCalledWith('/api/gates?state=blocked', { headers: { Authorization: 'Bearer token' } })
  expect(fetch).toHaveBeenCalledWith(
    '/api/gates/g-1/resolve',
    expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({
        Authorization: 'Bearer token',
        'Content-Type': 'application/json',
      }),
    }),
  )
})

test('useResolveGate invalidates the pending gates query on success', async () => {
  const queryClient = new QueryClient()
  const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
  let mutation: ReturnType<typeof useResolveGate> | null = null

  function Probe() {
    mutation = useResolveGate()
    return null
  }

  renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  )

  expect(mutation).not.toBeNull()
  await mutation!.mutateAsync({ gateId: 'g-1', decision: 'approve', actorId: 'operator', token: '' })

  expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['gates', 'pending'] })
})
