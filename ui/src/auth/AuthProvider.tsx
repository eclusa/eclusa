import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

interface AuthContextValue {
  token: string | null
  login: (token: string) => void
  logout: () => void
  isAuthenticated: boolean
  getAuthHeader: () => Record<string, string>
}

export interface AuthStorage {
  getItem: (key: string) => string | null
  setItem: (key: string, value: string) => void
  removeItem: (key: string) => void
}

const AUTH_TOKEN_KEY = 'eclusa_token'
const FETCH_PATCH_FLAG = '__eclusaFetchPatched__'

const AuthContext = createContext<AuthContextValue | null>(null)

interface JwtPayload {
  exp?: unknown
  sub?: unknown
  actor_id?: unknown
}

function base64UrlDecode(value: string) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4)
  return atob(padded)
}

function readJwtPayload(token: string) {
  const parts = token.split('.')
  if (parts.length !== 3 || !parts[1]) return null

  try {
    return JSON.parse(base64UrlDecode(parts[1])) as JwtPayload
  } catch {
    return null
  }
}

export function getTokenSubject(token: string | null) {
  if (!token) return null

  const payload = readJwtPayload(token)
  if (!payload) return null

  if (typeof payload.sub === 'string') return payload.sub
  if (typeof payload.actor_id === 'string') return payload.actor_id

  return null
}

function readStoredToken() {
  if (typeof window === 'undefined') return null

  const token = window.localStorage.getItem(AUTH_TOKEN_KEY)
  if (!token) return null

  const payload = readJwtPayload(token)
  if (payload) {
    if (typeof payload.exp === 'number' && payload.exp * 1000 <= Date.now()) {
      window.localStorage.removeItem(AUTH_TOKEN_KEY)
      return null
    }
  }

  return token
}

export function createAuthSession(storage: AuthStorage, initialToken: string | null = null) {
  let token = initialToken ?? storage.getItem(AUTH_TOKEN_KEY)

  const login = (nextToken: string) => {
    token = nextToken
    storage.setItem(AUTH_TOKEN_KEY, nextToken)
  }

  const logout = () => {
    token = null
    storage.removeItem(AUTH_TOKEN_KEY)
  }

  const isAuthenticated = () => Boolean(token)
  const getAuthHeader = () => (token ? { Authorization: `Bearer ${token}` } : {}) as Record<string, string>

  return {
    get token() {
      return token
    },
    login,
    logout,
    isAuthenticated,
    getAuthHeader,
  }
}

function ensureFetchPatch() {
  if (typeof window === 'undefined') return
  const globalWindow = window as typeof window & { [FETCH_PATCH_FLAG]?: boolean }
  if (globalWindow[FETCH_PATCH_FLAG]) return

  const originalFetch = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const token = readStoredToken()
    if (!token) return originalFetch(input, init)

    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
    if (!headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }

    return originalFetch(input, {
      ...init,
      headers,
    })
  }

  globalWindow[FETCH_PATCH_FLAG] = true
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readStoredToken())

  useEffect(() => {
    ensureFetchPatch()
  }, [])

  const value = useMemo<AuthContextValue>(() => {
    const login = (nextToken: string) => {
      setToken(nextToken)
      window.localStorage.setItem(AUTH_TOKEN_KEY, nextToken)
    }

    const logout = () => {
      setToken(null)
      window.localStorage.removeItem(AUTH_TOKEN_KEY)
    }

    const resolvedToken = token ?? null
    const isAuthenticated = Boolean(resolvedToken)
    const getAuthHeader = () => (resolvedToken ? { Authorization: `Bearer ${resolvedToken}` } : {}) as Record<string, string>

    return {
      token: resolvedToken,
      login,
      logout,
      isAuthenticated,
      getAuthHeader,
    }
  }, [token])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
