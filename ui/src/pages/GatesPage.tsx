import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { usePendingGates } from '@/api/gates'
import { GateContextPanel } from '@/components/gate/GateContextPanel'

function GateSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="space-y-3">
        <Skeleton className="h-4 w-28 bg-zinc-800" />
        <Skeleton className="h-4 w-1/2 bg-zinc-800" />
        <Skeleton className="h-24 w-full bg-zinc-800" />
      </div>
    </div>
  )
}

export function GatesPage() {
  const [filter, setFilter] = useState<'all' | 'blocked'>('blocked')
  const { data, isLoading, error } = usePendingGates()
  const gates = data ?? []

  const visibleGates = useMemo(() => {
    if (filter === 'all') {
      return gates
    }

    return gates.filter((gate) => gate.state === 'blocked')
  }, [filter, gates])

  const pendingCount = gates.length

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Gates</div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold text-zinc-100">Pending Gates</h1>
              <Badge
                variant="outline"
                className={
                  pendingCount > 0
                    ? 'border-amber-800/50 bg-amber-950/40 text-amber-300'
                    : 'border-zinc-800 bg-zinc-950/40 text-zinc-400'
                }
              >
                {pendingCount}
              </Badge>
            </div>
          </div>

          <div className="inline-flex rounded-md border border-zinc-800 bg-zinc-950 p-1">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setFilter('blocked')}
              className={
                filter === 'blocked'
                  ? 'border-zinc-100 bg-zinc-100 text-zinc-900 hover:bg-zinc-200 hover:text-zinc-950'
                  : 'border-zinc-700 bg-transparent text-zinc-400 hover:border-zinc-600 hover:bg-zinc-900 hover:text-zinc-100'
              }
            >
              Blocked
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setFilter('all')}
              className={
                filter === 'all'
                  ? 'border-zinc-100 bg-zinc-100 text-zinc-900 hover:bg-zinc-200 hover:text-zinc-950'
                  : 'border-zinc-700 bg-transparent text-zinc-400 hover:border-zinc-600 hover:bg-zinc-900 hover:text-zinc-100'
              }
            >
              All
            </Button>
          </div>
        </div>
      </header>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 2 }, (_, index) => (
            <GateSkeleton key={index} />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">Failed to load gates</div>
      ) : visibleGates.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-500">No pending gates</div>
      ) : (
        <div className="space-y-3">
          {visibleGates.map((gate) => (
            <GateContextPanel key={gate.id} gate={gate} />
          ))}
        </div>
      )}
    </div>
  )
}
