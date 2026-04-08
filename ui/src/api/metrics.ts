import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/auth/AuthProvider'

export interface CalibrationMetrics {
  gate_necessity: number | null
  orchestrator_absorption: number | null
  resolution_latency: number | null
  decision_durability: number | null
  cascade_rework: number | null
  model_convergence: number | null
  minority_accuracy: number | null
  fanout_necessity: number | null
}

async function requestJson<T>(url: string, headers: Record<string, string>) {
  const response = await fetch(url, { headers })
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }

  return response.json() as Promise<T>
}

export function fetchCalibrationMetrics(headers: Record<string, string>) {
  return requestJson<CalibrationMetrics>('/api/metrics', headers)
}

export function useCalibrationMetrics() {
  const { getAuthHeader } = useAuth()

  return useQuery<CalibrationMetrics>({
    queryKey: ['metrics', 'calibration'],
    queryFn: () => fetchCalibrationMetrics(getAuthHeader()),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
}
