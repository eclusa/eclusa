import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/auth/AuthProvider'

export interface EntityResult {
  id: string
  name: string
  entity_type: string
  score?: number
}

export interface Fact {
  id: string
  subject_id: string
  predicate: string
  object_id: string | null
  object_value: string | null
  t_valid: string
  t_invalid: string | null
  t_created: string
  t_expired: string | null
}

export interface Community {
  id: string
  name: string
  member_count: number
}

async function requestJson<T>(url: string, headers: Record<string, string>) {
  const response = await fetch(url, { headers })
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function fetchEntitySearch(q: string, limit: number, headers: Record<string, string>) {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
  })

  return requestJson<EntityResult[]>(`/api/knowledge/entities?${params}`, headers)
}

export function fetchEntityFacts(entityId: string, headers: Record<string, string>) {
  const params = new URLSearchParams({
    entity_id: entityId,
  })

  return requestJson<Fact[]>(`/api/knowledge/facts?${params}`, headers)
}

export function fetchCommunities(headers: Record<string, string>) {
  return requestJson<Community[]>('/api/knowledge/communities', headers)
}

export function useEntitySearch(q: string, limit = 20) {
  const { getAuthHeader } = useAuth()
  const normalizedQuery = q.trim()

  return useQuery<EntityResult[]>({
    queryKey: ['knowledge', 'entities', normalizedQuery, limit],
    queryFn: () => fetchEntitySearch(normalizedQuery, limit, getAuthHeader()),
    enabled: normalizedQuery.length > 1,
    staleTime: 10_000,
  })
}

export function useEntityFacts(entityId: string | null) {
  const { getAuthHeader } = useAuth()

  return useQuery<Fact[]>({
    queryKey: ['knowledge', 'facts', entityId],
    queryFn: () => {
      if (!entityId) {
        throw new Error('Entity id is required')
      }

      return fetchEntityFacts(entityId, getAuthHeader())
    },
    enabled: Boolean(entityId),
  })
}

export function useCommunities() {
  const { getAuthHeader } = useAuth()

  return useQuery<Community[]>({
    queryKey: ['knowledge', 'communities'],
    queryFn: () => fetchCommunities(getAuthHeader()),
    staleTime: 60_000,
  })
}
