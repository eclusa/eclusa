import { Fragment } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { StageStatusBadge } from '@/components/cascade/StageStatusBadge'
import { cn } from '@/lib/utils'
import type { StageDetail } from '@/api/cascades'

const SCC_ORDER = ['refine', 'intent_validation_fanout', 'match', 'cohere', 'formalize', 'derive', 'generate']

interface SccPipelineViewProps {
  stages: StageDetail[]
  onStageClick?: (stage: StageDetail) => void
  activeStageId?: string | null
}

const STATUS_CLASSES: Record<string, string> = {
  pending: 'border-zinc-700/50 bg-zinc-800/40',
  active: 'border-blue-700/60 bg-blue-950/40 ring-1 ring-blue-700/30',
  resolved: 'border-emerald-700/50 bg-emerald-950/30',
  failed: 'border-red-700/50 bg-red-950/30',
  blocked: 'border-amber-700/50 bg-amber-950/30',
}

const STATUS_DOT_CLASSES: Record<string, string> = {
  pending: 'bg-zinc-500',
  active: 'bg-blue-500 animate-pulse',
  resolved: 'bg-green-500',
  failed: 'bg-red-500',
  blocked: 'bg-amber-500',
}

function getSortKey(stage: StageDetail) {
  if (stage.scc_stage) {
    const normalizedStage = stage.scc_stage === 'fanout' ? 'intent_validation_fanout' : stage.scc_stage
    const index = SCC_ORDER.indexOf(normalizedStage)
    return index >= 0 ? index : SCC_ORDER.length
  }

  return SCC_ORDER.length + 1
}

function sortStages(stages: StageDetail[]) {
  return [...stages].sort((a, b) => {
    const orderDelta = getSortKey(a) - getSortKey(b)
    if (orderDelta !== 0) {
      return orderDelta
    }

    const createdDelta = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    if (createdDelta !== 0) {
      return createdDelta
    }

    return a.id.localeCompare(b.id)
  })
}

export function SccPipelineView({ stages, onStageClick, activeStageId }: SccPipelineViewProps) {
  const orderedStages = sortStages(stages)

  if (orderedStages.length === 0) {
    return <div className="text-sm text-zinc-500">No stages found</div>
  }

  return (
    <div className="space-y-3">
      <div className="text-xs font-mono uppercase tracking-[0.25em] text-zinc-500">Pipeline</div>
      <div className="flex flex-col lg:flex-row lg:items-stretch">
        {orderedStages.map((stage, index) => {
          const interactive = Boolean(onStageClick) && (stage.state === 'resolved' || stage.state === 'active')
          const statusClass = STATUS_CLASSES[stage.state] ?? STATUS_CLASSES['pending']
          const dotClass = STATUS_DOT_CLASSES[stage.state] ?? STATUS_DOT_CLASSES['pending']

          return (
            <Fragment key={stage.id}>
              {index > 0 ? (
                <div className="flex items-center justify-center py-2 lg:px-3 lg:py-0">
                  <ChevronDown className="h-4 w-4 text-zinc-600 lg:hidden" />
                  <ChevronRight className="hidden h-4 w-4 text-zinc-600 lg:block" />
                </div>
              ) : null}

              <button
                type="button"
                onClick={interactive ? () => onStageClick?.(stage) : undefined}
                disabled={!interactive}
                className={cn(
                  'min-w-[100px] rounded-lg border p-3 text-left transition-colors',
                  statusClass,
                  activeStageId === stage.id && 'ring-2 ring-blue-500/50',
                  interactive ? 'cursor-pointer hover:border-zinc-600' : 'cursor-default',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 space-y-2">
                    <div className="truncate text-xs font-mono uppercase tracking-[0.25em] text-zinc-300">
                      {stage.display_name}
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                      <span className={cn('h-2 w-2 rounded-full', dotClass)} />
                      <span className="uppercase tracking-[0.2em]">{stage.scc_stage ?? 'unmapped'}</span>
                    </div>
                  </div>
                  <StageStatusBadge state={stage.state} />
                </div>
              </button>
            </Fragment>
          )
        })}
      </div>
    </div>
  )
}
