import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/auth/AuthProvider'

export interface StageStatus {
  id: string
  type: string
  state: string
  created_at: string
}

export interface CascadeItem {
  id: string
  title: string
  state: string
  created_at: string
  stage_count: number
  blocked_stage_count: number
}

export interface CascadeDetail extends CascadeItem {
  stages: StageStatus[]
}

export interface StageDetail {
  id: string
  type: string
  state: string
  scc_stage: string | null
  display_name: string
  depends_on: string[]
  resolved_at: string | null
  output_summary: string | null
  created_at: string
}

export interface StageOutput {
  stage_id: string
  scc_stage: string | null
  display_name: string
  state: string
  output: unknown
  output_summary: string | null
  resolved_at: string | null
}

async function requestJson<T>(url: string, headers: Record<string, string>) {
  const response = await fetch(url, { headers })
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function fetchActiveCascades(headers: Record<string, string>) {
  return requestJson<CascadeItem[]>('/api/cascades', headers)
}

export function fetchCascadeDetail(id: string, headers: Record<string, string>) {
  return requestJson<CascadeDetail>(`/api/cascades/${id}`, headers)
}

export function fetchCascadeStages(id: string, headers: Record<string, string>) {
  return requestJson<StageDetail[]>(`/api/cascades/${id}/stages`, headers)
}

export function fetchStageOutput(cascadeId: string, stageId: string, headers: Record<string, string>) {
  return requestJson<StageOutput>(`/api/cascades/${cascadeId}/stages/${stageId}/output`, headers)
}

export function useActiveCascades() {
  const { getAuthHeader } = useAuth()

  return useQuery<CascadeItem[]>({
    queryKey: ['cascades', 'active'],
    queryFn: () => fetchActiveCascades(getAuthHeader()),
    refetchInterval: 15_000,
  })
}

export function useCascadeDetail(id: string | null) {
  const { getAuthHeader } = useAuth()

  return useQuery<CascadeDetail>({
    queryKey: ['cascades', id],
    queryFn: () => {
      if (!id) {
        throw new Error('Cascade id is required')
      }

      return fetchCascadeDetail(id, getAuthHeader())
    },
    enabled: Boolean(id),
  })
}

export function useCascadeStages(id: string | null) {
  const { getAuthHeader } = useAuth()

  return useQuery<StageDetail[]>({
    queryKey: ['cascades', id, 'stages'],
    queryFn: () => {
      if (!id) {
        throw new Error('Cascade id is required')
      }

      return fetchCascadeStages(id, getAuthHeader())
    },
    enabled: Boolean(id),
    refetchInterval: 5_000,
  })
}

export function useStageOutput(cascadeId: string | null, stageId: string | null) {
  const { getAuthHeader } = useAuth()

  return useQuery<StageOutput>({
    queryKey: ['cascades', cascadeId, 'stages', stageId, 'output'],
    queryFn: () => {
      if (!cascadeId || !stageId) {
        throw new Error('ids required')
      }

      return fetchStageOutput(cascadeId, stageId, getAuthHeader())
    },
    enabled: Boolean(cascadeId) && Boolean(stageId),
  })
}
