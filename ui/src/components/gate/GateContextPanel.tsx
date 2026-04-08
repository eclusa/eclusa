import { formatDistanceToNow } from 'date-fns'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import type { GateItem } from '@/api/gates'
import { StageStatusBadge } from '@/components/cascade/StageStatusBadge'
import { GateResolveForm } from './GateResolveForm'

function formatContext(input: Record<string, unknown>) {
  return JSON.stringify(input, null, 2)
}

export function GateContextPanel({ gate }: { gate: GateItem }) {
  const createdLabel = formatDistanceToNow(new Date(gate.created_at), { addSuffix: true })

  return (
    <Card className="border-zinc-800 bg-zinc-900 text-zinc-100">
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <div className="text-xs uppercase tracking-[0.25em] text-zinc-500">Gate</div>
            <code className="block max-w-full truncate rounded bg-zinc-950 px-2 py-1 font-mono text-xs text-zinc-300" title={gate.id}>
              {gate.id}
            </code>
            <div className="text-xs text-zinc-500">
              Cascade{' '}
              <Link className="text-zinc-300 underline decoration-zinc-700 underline-offset-2 hover:text-zinc-100" to={`/cascades/${gate.cascade_id}`}>
                {gate.cascade_id}
              </Link>
              {' · '}
              {createdLabel}
            </div>
          </div>

          <div className="flex flex-col items-end gap-2">
            <StageStatusBadge state={gate.state} />
            {gate.model_recommendation ? (
              <Badge variant="outline" className="border-emerald-800/50 bg-emerald-950/30 text-emerald-300">
                {gate.model_recommendation}
              </Badge>
            ) : null}
          </div>
        </div>

        <pre className="max-h-48 overflow-auto rounded bg-zinc-950 p-3 text-xs text-zinc-400">{formatContext(gate.input)}</pre>

        <GateResolveForm gateId={gate.id} />
      </div>
    </Card>
  )
}
