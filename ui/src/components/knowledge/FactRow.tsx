import type { Fact } from '@/api/knowledge'
import { BiTemporalBadge } from './BiTemporalBadge'

export function FactRow({ fact }: { fact: Fact }) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950/70 px-3 py-2">
      <div className="space-y-1">
        <div className="font-mono text-sm text-amber-300">{fact.predicate}</div>
        <div className="text-sm text-zinc-300">{fact.object_value ?? fact.object_id ?? 'null'}</div>
        <BiTemporalBadge fact={fact} />
      </div>
    </div>
  )
}
