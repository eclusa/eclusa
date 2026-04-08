import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/auth/AuthProvider'

export interface GateItem {
  id: string
  cascade_id: string
  state: string
  input: Record<string, unknown>
  created_at: string
  model_recommendation: string | null
}

export interface ResolveParams {
  gateId: string
  decision: string
  actorId: string
  token: string
}

async function requestJson<T>(url: string, init: RequestInit) {
  const response = await fetch(url, init)
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function fetchPendingGates(headers: Record<string, string>) {
  return requestJson<GateItem[]>('/api/gates?state=blocked', { headers })
}

export function resolveGateRequest(params: ResolveParams, headers: Record<string, string>) {
  return requestJson<unknown>(`/api/gates/${params.gateId}/resolve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify({
      token: params.token,
      decision: params.decision,
      actor_id: params.actorId,
    }),
  })
}

export function usePendingGates() {
  const { getAuthHeader } = useAuth()

  return useQuery<GateItem[]>({
    queryKey: ['gates', 'pending'],
    queryFn: () => fetchPendingGates(getAuthHeader()),
    refetchInterval: 10_000,
  })
}

export function useResolveGate() {
  const queryClient = useQueryClient()
  const { getAuthHeader } = useAuth()

  return useMutation({
    mutationFn: (params: ResolveParams) => resolveGateRequest(params, getAuthHeader()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gates', 'pending'] })
    },
  })
}
