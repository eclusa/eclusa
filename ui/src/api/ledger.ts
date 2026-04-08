import { useQuery } from '@tanstack/react-query'
import type { PaginationState } from '@tanstack/react-table'
import { useAuth } from '@/auth/AuthProvider'

export interface LedgerEntry {
  id: string
  event_type: string
  cascade_id: string | null
  stage_id: string | null
  session_id: string | null
  content: Record<string, unknown>
  schema_version: string
  created_at: string
}

export interface LedgerResponse {
  items: LedgerEntry[]
  total_count: number
  page: number
  size: number
}

async function requestJson<T>(url: string, headers: Record<string, string>) {
  const response = await fetch(url, { headers })
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function fetchLedgerAsOf(asOf: string, pagination: PaginationState, headers: Record<string, string>) {
  const params = new URLSearchParams({
    as_of: asOf,
    page: String(pagination.pageIndex),
    size: String(pagination.pageSize),
  })

  return requestJson<LedgerResponse>(`/api/ledger?${params}`, headers)
}

export function useLedgerAsOf(asOf: string, pagination: PaginationState) {
  const { getAuthHeader } = useAuth()

  return useQuery<LedgerResponse>({
    queryKey: ['ledger', asOf, pagination.pageIndex, pagination.pageSize],
    queryFn: () => fetchLedgerAsOf(asOf, pagination, getAuthHeader()),
  })
}
