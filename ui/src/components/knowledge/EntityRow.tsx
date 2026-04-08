import { ChevronDown, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useUIStore } from '@/store/ui'
import type { EntityResult } from '@/api/knowledge'
import { useEntityFacts } from '@/api/knowledge'
import { FactRow } from './FactRow'

export function EntityRow({ entity }: { entity: EntityResult }) {
  const panelId = `entity-${entity.id}`
  const isOpen = useUIStore((state) => state.openPanels.has(panelId))
  const togglePanel = useUIStore((state) => state.togglePanel)
  const { data, isLoading, error } = useEntityFacts(isOpen ? entity.id : null)

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-zinc-800/30"
        onClick={() => togglePanel(panelId)}
        aria-expanded={isOpen}
      >
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <div className="truncate text-sm font-medium text-zinc-100">{entity.name}</div>
            <Badge variant="outline" className="border-zinc-800 bg-zinc-800 text-[11px] font-mono uppercase tracking-[0.25em] text-zinc-200">
              {entity.entity_type}
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {typeof entity.score === 'number' ? (
            <span className="font-mono text-xs text-zinc-500">{(entity.score * 100).toFixed(1)}%</span>
          ) : null}
          {isOpen ? <ChevronDown className="h-4 w-4 text-zinc-500" /> : <ChevronRight className="h-4 w-4 text-zinc-500" />}
        </div>
      </button>

      {isOpen ? (
        <div className="space-y-3 border-t border-zinc-800 px-4 py-4">
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full bg-zinc-800" />
              <Skeleton className="h-10 w-full bg-zinc-800" />
            </div>
          ) : error ? (
            <div className="text-sm text-red-400">Failed to load facts</div>
          ) : data && data.length > 0 ? (
            <div className="space-y-2">
              {data.map((fact) => (
                <FactRow key={fact.id} fact={fact} />
              ))}
            </div>
          ) : (
            <div className="text-sm text-zinc-500">No facts found for this entity.</div>
          )}
        </div>
      ) : null}
    </div>
  )
}
