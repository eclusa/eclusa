import { useMemo } from 'react'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useActiveCascades } from '@/api/cascades'
import { CascadeCard } from '@/components/cascade/CascadeCard'

function CascadeSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="space-y-3">
        <Skeleton className="h-5 w-2/3 bg-zinc-800" />
        <Skeleton className="h-4 w-1/3 bg-zinc-800" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-24 bg-zinc-800" />
          <Skeleton className="h-6 w-24 bg-zinc-800" />
        </div>
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { data, isLoading, error } = useActiveCascades()
  const cascades = data ?? []
  const activeCount = useMemo(() => cascades.length, [cascades.length])

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Cascades</div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-zinc-100">Active Cascades</h1>
          <Badge variant="outline" className="border-blue-800/50 bg-blue-950/40 text-blue-300">
            {activeCount}
          </Badge>
        </div>
      </header>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <CascadeSkeleton key={index} />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">Failed to load cascades</div>
      ) : cascades.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6 text-sm text-zinc-500">No active cascades</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {cascades.map((cascade) => (
            <CascadeCard key={cascade.id} cascade={cascade} />
          ))}
        </div>
      )}
    </div>
  )
}
