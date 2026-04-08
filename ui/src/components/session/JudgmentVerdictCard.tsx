import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { SessionVerdict } from '@/api/sessions'

function confidenceLabel(confidence?: number) {
  if (typeof confidence !== 'number' || Number.isNaN(confidence)) {
    return 'n/a'
  }

  return `${(confidence * 100).toFixed(1)}%`
}

export function JudgmentVerdictCard({ verdict, className }: { verdict: SessionVerdict; className?: string }) {
  const isApproved = verdict.decision === 'approved'
  const borderClass = isApproved ? 'border-emerald-800/40' : 'border-amber-800/40'
  const confidence = confidenceLabel(verdict.confidence)
  const confidenceClass = typeof verdict.confidence === 'number' && verdict.confidence > 0.7 ? 'text-emerald-300' : 'text-zinc-400'

  return (
    <Card className={cn('border-l-4 border-zinc-800 bg-zinc-950/70 text-zinc-100 shadow-none', borderClass, className)}>
      <CardHeader className="space-y-2 p-4">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm font-semibold text-zinc-100">Judgment</CardTitle>
          <Badge
            variant="outline"
            className={cn(
              'border text-xs font-mono uppercase tracking-wide',
              isApproved ? 'border-emerald-800/50 bg-emerald-950/30 text-emerald-300' : 'border-amber-800/50 bg-amber-950/30 text-amber-300',
            )}
          >
            {verdict.decision ?? 'unknown'}
          </Badge>
        </div>
        <div className="font-mono text-xs text-zinc-400">{verdict.model ?? 'unknown model'}</div>
      </CardHeader>
      <CardContent className="space-y-2 px-4 pb-4">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-zinc-500">Confidence</span>
          <span className={confidenceClass}>{confidence}</span>
        </div>
        {verdict.rationale ? <p className="text-sm italic leading-relaxed text-zinc-300">{verdict.rationale}</p> : null}
      </CardContent>
    </Card>
  )
}
