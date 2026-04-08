import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/auth/AuthProvider'

export interface SessionItem {
  id: string
  stage_id: string
  model: string
  state: string
  cost_estimated_usd: number
  created_at: string
  title: string
}

export interface SessionCost {
  estimated_usd?: number
  tokens_in?: number
  tokens_out?: number
}

export interface SessionVerdict {
  model?: string
  confidence?: number
  decision?: string
  rationale?: string
}

export interface SessionToolCall {
  name?: string
  function?: string
  args?: unknown
  result?: unknown
}

export interface SessionContent extends Record<string, unknown> {
  type?: string
  text?: string
  tool_calls?: SessionToolCall[]
  tool_call?: SessionToolCall
  args?: unknown
  result?: unknown
  verdict?: SessionVerdict
  cost?: SessionCost
  name?: string
  function?: string
}

export interface SessionMessage {
  id?: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: SessionContent | string
  created_at: string
  model?: string
  cost?: SessionCost
  cost_estimated_usd?: number
  tokens_in?: number
  tokens_out?: number
}

async function requestJson<T>(url: string, headers: Record<string, string>) {
  const response = await fetch(url, { headers })
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function fetchSessions(headers: Record<string, string>) {
  return requestJson<SessionItem[]>('/api/sessions', headers)
}

export function fetchSessionMessages(id: string, headers: Record<string, string>) {
  return requestJson<SessionMessage[]>(`/api/sessions/${id}/messages`, headers)
}

export function useSessions() {
  const { getAuthHeader } = useAuth()

  return useQuery<SessionItem[]>({
    queryKey: ['sessions', 'list'],
    queryFn: () => fetchSessions(getAuthHeader()),
    refetchInterval: 30_000,
  })
}

export function useSessionMessages(id: string | null) {
  const { getAuthHeader } = useAuth()

  return useQuery<SessionMessage[]>({
    queryKey: ['sessions', id, 'messages'],
    queryFn: () => {
      if (!id) {
        throw new Error('Session id is required')
      }

      return fetchSessionMessages(id, getAuthHeader())
    },
    enabled: Boolean(id),
  })
}
