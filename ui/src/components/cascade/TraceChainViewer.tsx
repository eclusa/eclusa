import { Link } from 'react-router-dom'
import type { TraceHop } from '@/api/trace'
import { useTraceChain } from '@/api/trace'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'

interface TraceChainViewerProps {
  artifactId: string | null
}

function HopRow({ hop }: { hop: TraceHop }) {
  const content = (
    <div
      className={cn(
        'flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors',
        hop.href
          ? 'border-zinc-800 bg-zinc-950/40 hover:border-zinc-700 hover:bg-zinc-900/80'
          : 'border-zinc-800/70 bg-zinc-950/20',
      )}
    >
      <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[11px] font-mono uppercase tracking-[0.2em] text-zinc-400">
        {hop.type}
      </span>
      <span className="font-mono text-[11px] text-zinc-500">{hop.id}</span>
      <span className="min-w-0 flex-1 text-zinc-200">{hop.label}</span>
    </div>
  )

  if (!hop.href) {
    return content
  }

  return (
    <Link to={hop.href} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-900/60">
      {content}
    </Link>
  )
}

export function TraceChainViewer({ artifactId }: TraceChainViewerProps) {
  const traceQuery = useTraceChain(artifactId)

  if (!artifactId) {
    return null
  }

  return (
    <section className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-900 p-4 shadow-2xl shadow-black/20">
      <div className="space-y-1">
        <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Trace chain</div>
        <div className="text-sm text-zinc-500">Artifact ancestry from session to intent</div>
      </div>

      {traceQuery.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} className="h-12 bg-zinc-800" />
          ))}
        </div>
      ) : traceQuery.isError ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">Failed to load trace chain</div>
      ) : traceQuery.data?.hops.length ? (
        <div className="space-y-2">
          {traceQuery.data.hops.map((hop) => (
            <HopRow key={`${hop.type}:${hop.id}`} hop={hop} />
          ))}
        </div>
      ) : (
        <div className="text-sm text-zinc-500">No trace hops found</div>
      )}
    </section>
  )
}
