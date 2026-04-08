import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/ui'
import type { CascadeItem } from '@/api/cascades'
import { StageStatusBadge } from './StageStatusBadge'

export function CascadeCard({ cascade }: { cascade: CascadeItem }) {
  const navigate = useNavigate()
  const setSelectedCascade = useUIStore((state) => state.setSelectedCascade)

  const createdLabel = formatDistanceToNow(new Date(cascade.created_at), { addSuffix: true })

  const handleActivate = () => {
    setSelectedCascade(cascade.id)
    navigate(`/cascades/${cascade.id}`)
  }

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={handleActivate}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          handleActivate()
        }
      }}
      className={cn(
        'cursor-pointer border-zinc-800 bg-zinc-900 text-zinc-100 transition-colors hover:border-zinc-700 hover:bg-zinc-900/90',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-900/60',
      )}
    >
      <div className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <div className="truncate text-base font-medium text-zinc-100">{cascade.title}</div>
            <div className="text-xs text-zinc-500">{createdLabel}</div>
          </div>
          <StageStatusBadge state={cascade.state} />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-zinc-800 bg-zinc-950/40 text-[11px] uppercase tracking-[0.25em] text-zinc-400">
            {cascade.stage_count} stages
          </Badge>
          <Badge variant="outline" className="border-amber-800/50 bg-amber-950/30 text-[11px] uppercase tracking-[0.25em] text-amber-300">
            {cascade.blocked_stage_count} blocked
          </Badge>
        </div>
      </div>
    </Card>
  )
}
