import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/auth/AuthProvider'

export type TraceHopType = 'artifact' | 'session' | 'stage' | 'cascade' | 'intent'

export interface TraceHop {
  type: TraceHopType
  id: string
  label: string
  href: string | null
}

export interface TraceChain {
  artifact_id: string
  hops: TraceHop[]
}

async function requestJson<T>(url: string, headers: Record<string, string>) {
  const response = await fetch(url, { headers })
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function fetchTraceChain(artifactId: string, headers: Record<string, string>) {
  return requestJson<TraceChain>(`/api/trace/${artifactId}`, headers)
}

export function useTraceChain(artifactId: string | null) {
  const { getAuthHeader } = useAuth()

  return useQuery<TraceChain>({
    queryKey: ['trace', artifactId],
    queryFn: () => {
      if (!artifactId) {
        throw new Error('Artifact id is required')
      }

      return fetchTraceChain(artifactId, getAuthHeader())
    },
    enabled: Boolean(artifactId),
  })
}
