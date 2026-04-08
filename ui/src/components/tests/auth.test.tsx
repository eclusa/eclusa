import { renderToStaticMarkup } from 'react-dom/server'
import { AuthProvider, createAuthSession, useAuth } from '@/auth/AuthProvider'
import type { ReactNode } from 'react'

function renderAuthSnapshot(children: ReactNode) {
  return renderToStaticMarkup(<AuthProvider>{children}</AuthProvider>)
}

beforeEach(() => {
  const store = new Map<string, string>()
  const localStorageMock = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value)
    },
    removeItem: (key: string) => {
      store.delete(key)
    },
    clear: () => {
      store.clear()
    },
  }

  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      localStorage: localStorageMock,
      fetch: async () => new Response('{}', { status: 200 }),
    },
  })
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: localStorageMock,
  })
})

test('isAuthenticated false by default', () => {
  function Probe() {
    const auth = useAuth()
    return <span data-auth={String(auth.isAuthenticated)} />
  }

  const html = renderAuthSnapshot(<Probe />)
  expect(html).toContain('data-auth="false"')
})

test('login sets isAuthenticated true and persists to localStorage', () => {
  const storage = globalThis.localStorage
  const auth = createAuthSession(storage)
  auth.login('test-token')
  expect(auth.isAuthenticated()).toBe(true)
  expect(storage.getItem('eclusa_token')).toBe('test-token')
})

test('getAuthHeader returns Bearer token when authenticated', () => {
  const auth = createAuthSession(globalThis.localStorage, 'test-token')
  expect(auth.getAuthHeader()).toEqual({ Authorization: 'Bearer test-token' })
})
