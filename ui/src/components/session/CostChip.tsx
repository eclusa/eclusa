import { cn } from '@/lib/utils'

export interface MessageCost {
  estimated_usd?: number
  tokens_in?: number
  tokens_out?: number
}

export function CostChip({ cost, className }: { cost: MessageCost | null | undefined; className?: string }) {
  if (!cost || typeof cost.estimated_usd !== 'number') {
    return null
  }

  const titleParts = [cost.tokens_in !== undefined ? `tokens in: ${cost.tokens_in}` : null, cost.tokens_out !== undefined ? `tokens out: ${cost.tokens_out}` : null].filter(Boolean)

  return (
    <span
      className={cn('shrink-0 font-mono text-xs tabular-nums text-zinc-500', className)}
      title={titleParts.length > 0 ? titleParts.join(' | ') : undefined}
    >
      {cost.estimated_usd.toFixed(4)} USD
    </span>
  )
}
