import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useCascadeDetail, useCascadeStages } from '@/api/cascades'
import { StageOutputPanel } from '@/components/cascade/StageOutputPanel'
import { SccPipelineView } from '@/components/cascade/SccPipelineView'
import { TraceChainViewer } from '@/components/cascade/TraceChainViewer'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useUIStore } from '@/store/ui'

export function CascadeDetailPage() {
  const { id } = useParams()
  const { data, isLoading: isCascadeLoading, error: cascadeError } = useCascadeDetail(id ?? null)
  const { data: stages = [], isLoading: isStagesLoading, error: stagesError } = useCascadeStages(id ?? null)
  const [searchParams] = useSearchParams()
  const setSelectedCascade = useUIStore((state) => state.setSelectedCascade)
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null)
  const artifactId = searchParams.get('artifact_id')?.trim() || null

  useEffect(() => {
    if (id) {
      setSelectedCascade(id)
      setSelectedStageId(null)
    }
  }, [id, setSelectedCascade])

  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? null
  const activeStageId = selectedStageId ?? stages.find((stage) => stage.state === 'active')?.id ?? null
  const isLoading = isCascadeLoading || isStagesLoading
  const error = cascadeError ?? stagesError

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Cascade detail</div>
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold text-zinc-100">{data?.title ?? 'Cascade'}</h1>
          <Link className="text-sm text-zinc-400 underline decoration-zinc-700 underline-offset-2 hover:text-zinc-100" to="/cascades">
            Back to dashboard
          </Link>
        </div>
      </div>

      {isLoading && !data ? (
        <div className="space-y-3">
          <Skeleton className="h-24 bg-zinc-800" />
          <Skeleton className="h-24 bg-zinc-800" />
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">Failed to load cascade</div>
      ) : data ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="text-lg font-medium text-zinc-100">{data.title}</div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="border-zinc-800 bg-zinc-950/40 text-zinc-400">
                    {data.stage_count} stages
                  </Badge>
                  <Badge variant="outline" className="border-amber-800/50 bg-amber-950/30 text-amber-300">
                    {data.blocked_stage_count} blocked
                  </Badge>
                  <Badge variant="outline" className="border-blue-800/50 bg-blue-950/40 text-blue-300">
                    {data.state}
                  </Badge>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
            <div className="space-y-4">
              {isStagesLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-24 bg-zinc-800" />
                  <Skeleton className="h-24 bg-zinc-800" />
                </div>
              ) : (
                <SccPipelineView
                  stages={stages}
                  onStageClick={(stage) => {
                    setSelectedStageId(stage.id)
                  }}
                  activeStageId={activeStageId}
                />
              )}
              {artifactId ? <TraceChainViewer artifactId={artifactId} /> : null}
            </div>

            {selectedStage ? (
              <StageOutputPanel
                cascadeId={id!}
                stage={selectedStage}
                onClose={() => {
                  setSelectedStageId(null)
                }}
              />
            ) : (
              <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-500">
                Select a resolved stage to inspect its output.
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
