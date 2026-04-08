import { format } from 'date-fns'
import type { Fact } from '@/api/knowledge'

function formatDate(value: string) {
  return format(new Date(value), 'yyyy-MM-dd')
}

export function BiTemporalBadge({ fact }: { fact: Fact }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs font-mono text-zinc-500">
      <span>t_valid: {formatDate(fact.t_valid)}</span>
      <span>t_invalid: {fact.t_invalid ? formatDate(fact.t_invalid) : 'current'}</span>
      <span>t_created: {formatDate(fact.t_created)}</span>
      <span>t_expired: {fact.t_expired ? formatDate(fact.t_expired) : 'active'}</span>
    </div>
  )
}
