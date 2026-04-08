import { useMemo } from 'react'
import {
  BarChart as RawBarChart,
  Bar as RawBar,
  CartesianGrid as RawCartesianGrid,
  Cell as RawCell,
  LineChart as RawLineChart,
  Line as RawLine,
  ResponsiveContainer as RawResponsiveContainer,
  Tooltip as RawTooltip,
  XAxis as RawXAxis,
  YAxis as RawYAxis,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useCostSummary } from '@/api/costs'

const BarChart = RawBarChart as any
const Bar = RawBar as any
const CartesianGrid = RawCartesianGrid as any
const Cell = RawCell as any
const LineChart = RawLineChart as any
const Line = RawLine as any
const ResponsiveContainer = RawResponsiveContainer as any
const Tooltip = RawTooltip as any
const XAxis = RawXAxis as any
const YAxis = RawYAxis as any

const AMBER = '#fbbf24'
const BLUE = '#60a5fa'

function CardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4">
      <Skeleton className="mb-4 h-5 w-40 bg-zinc-800" />
      <Skeleton className="h-64 w-full bg-zinc-800" />
    </div>
  )
}

function formatUsd(value: number, digits = 4) {
  return `${value.toFixed(digits)} USD`
}

function truncateId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value
}

export function CostsPage() {
  const { data, isLoading, error } = useCostSummary()

  const cascadeData = data?.by_cascade ?? []
  const modelData = data?.by_model ?? []
  const sessionData = data?.by_session ?? []

  const cumulativeSessionData = useMemo(() => {
    return [...sessionData]
      .sort((left, right) => left.session_id.localeCompare(right.session_id))
      .reduce<Array<{ session_id: string; cumulative_usd: number; total_usd: number }>>((accumulator, item) => {
        const previousEntry = accumulator[accumulator.length - 1]
        const previous = previousEntry ? previousEntry.cumulative_usd : 0
        accumulator.push({
          session_id: item.session_id,
          cumulative_usd: previous + item.total_usd,
          total_usd: item.total_usd,
        })
        return accumulator
      }, [])
  }, [sessionData])

  const isEmpty = !isLoading && !error && cascadeData.length === 0 && modelData.length === 0 && sessionData.length === 0

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Costs</div>
        <h1 className="text-2xl font-semibold text-zinc-100">Cost dashboard</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-zinc-500">Breakdown of estimated spend by cascade, session, and model.</p>
      </header>

      {isLoading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <CardSkeleton />
          <CardSkeleton />
          <div className="lg:col-span-2">
            <CardSkeleton />
          </div>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">Failed to load costs</div>
      ) : isEmpty ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-6 text-sm text-zinc-500">No cost data yet</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="border-zinc-800 bg-zinc-950/60 text-zinc-100 shadow-none" data-testid="cost-by-cascade-chart">
            <CardHeader className="border-b border-zinc-800 p-4">
              <CardTitle className="text-base">Cost by cascade</CardTitle>
            </CardHeader>
            <CardContent className="h-72 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cascadeData}>
                  <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                  <XAxis dataKey="cascade_id" tickFormatter={truncateId} stroke="#71717a" />
                  <YAxis tickFormatter={(value: unknown) => Number(value).toFixed(4)} stroke="#71717a" />
                  <Tooltip formatter={(value: unknown) => [formatUsd(Number(value), 6), 'Estimated USD']} />
                  <Bar dataKey="total_usd" fill={AMBER} radius={[4, 4, 0, 0]}>
                    {cascadeData.map((entry) => (
                      <Cell key={entry.cascade_id} fill={AMBER} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="border-zinc-800 bg-zinc-950/60 text-zinc-100 shadow-none" data-testid="cost-by-model-chart">
            <CardHeader className="border-b border-zinc-800 p-4">
              <CardTitle className="text-base">Cost by model</CardTitle>
            </CardHeader>
            <CardContent className="h-72 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={modelData}>
                  <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                  <XAxis dataKey="model" tickFormatter={(value: unknown) => String(value).replace(/^(.{0,12}).*$/, '$1')} stroke="#71717a" />
                  <YAxis tickFormatter={(value: unknown) => Number(value).toFixed(4)} stroke="#71717a" />
                  <Tooltip formatter={(value: unknown) => [formatUsd(Number(value), 6), 'Estimated USD']} />
                  <Bar dataKey="total_usd" fill={AMBER} radius={[4, 4, 0, 0]}>
                    {modelData.map((entry) => (
                      <Cell key={entry.model} fill={AMBER} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="border-zinc-800 bg-zinc-950/60 text-zinc-100 shadow-none lg:col-span-2" data-testid="cost-by-session-chart">
            <CardHeader className="border-b border-zinc-800 p-4">
              <CardTitle className="text-base">Cumulative spend over time</CardTitle>
            </CardHeader>
            <CardContent className="h-72 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={cumulativeSessionData}>
                  <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                  <XAxis dataKey="session_id" tickFormatter={truncateId} stroke="#71717a" />
                  <YAxis tickFormatter={(value: unknown) => Number(value).toFixed(4)} stroke="#71717a" />
                  <Tooltip formatter={(value: unknown) => [formatUsd(Number(value), 6), 'Cumulative USD']} />
                  <Line type="monotone" dataKey="cumulative_usd" stroke={BLUE} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
