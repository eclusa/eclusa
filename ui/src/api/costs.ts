import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/auth/AuthProvider'

export interface CostSummaryCascadeItem {
  cascade_id: string
  total_tokens_in: number
  total_tokens_out: number
  total_usd: number
}

export interface CostSummarySessionItem {
  session_id: string
  total_tokens_in: number
  total_tokens_out: number
  total_usd: number
}

export interface CostSummaryModelItem {
  model: string
  total_tokens_in: number
  total_tokens_out: number
  total_usd: number
  session_count: number
}

export interface CostSummary {
  by_cascade: CostSummaryCascadeItem[]
  by_session: CostSummarySessionItem[]
  by_model: CostSummaryModelItem[]
}

async function requestJson<T>(url: string, headers: Record<string, string>) {
  const response = await fetch(url, { headers })
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function fetchCostSummary(headers: Record<string, string>) {
  return requestJson<CostSummary>('/api/costs', headers)
}

export function useCostSummary() {
  const { getAuthHeader } = useAuth()

  return useQuery<CostSummary>({
    queryKey: ['costs', 'summary'],
    queryFn: () => fetchCostSummary(getAuthHeader()),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
}
