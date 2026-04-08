import type { ReactNode } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface EmptyStateGuardProps {
  value: number | null | undefined
  title: string
  children: ReactNode
}

export function EmptyStateGuard({ value, title, children }: EmptyStateGuardProps) {
  if (value === null || value === undefined) {
    return (
      <Card className="border-zinc-800 bg-zinc-950/80 text-zinc-100">
        <CardHeader className="space-y-2 pb-3">
          <CardTitle className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">{title}</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <p className="text-sm text-zinc-500">Requires 10+ resolved gates to compute.</p>
        </CardContent>
      </Card>
    )
  }

  return <>{children}</>
}
