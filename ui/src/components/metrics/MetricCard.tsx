import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyStateGuard } from '@/components/metrics/EmptyStateGuard'
import { MetricChart, type MetricChartProps } from '@/components/metrics/MetricChart'

export interface MetricCardProps extends Omit<MetricChartProps, 'value'> {
  value: number | null | undefined
}

export function MetricCard({ title, description, type, value }: MetricCardProps) {
  return (
    <EmptyStateGuard value={value} title={title}>
      <Card className="border-zinc-800 bg-zinc-900 text-zinc-100">
        <CardHeader className="space-y-2 pb-3">
          <CardTitle className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">{title}</CardTitle>
          <CardDescription className="text-sm text-zinc-500">{description}</CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <MetricChart value={value ?? 0} type={type} title={title} description={description} />
        </CardContent>
      </Card>
    </EmptyStateGuard>
  )
}
