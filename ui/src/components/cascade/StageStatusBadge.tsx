import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const colorMap: Record<string, string> = {
  active: 'border-blue-800/50 bg-blue-900/40 text-blue-300',
  blocked: 'border-amber-800/50 bg-amber-900/40 text-amber-300',
  resolved: 'border-emerald-800/50 bg-emerald-900/40 text-emerald-300',
  failed: 'border-red-800/50 bg-red-900/40 text-red-300',
  pending: 'border-zinc-700/50 bg-zinc-800/40 text-zinc-400',
  skipped: 'border-zinc-700/30 bg-zinc-800/30 text-zinc-500',
}

export function StageStatusBadge({ state }: { state: string }) {
  return (
    <Badge variant="outline" className={cn('border text-xs font-mono uppercase tracking-wide', colorMap[state] ?? colorMap['pending'])}>
      {state}
    </Badge>
  )
}
