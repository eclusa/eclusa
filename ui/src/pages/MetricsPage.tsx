import { useCalibrationMetrics, type CalibrationMetrics } from '@/api/metrics'
import { MetricCard } from '@/components/metrics/MetricCard'
import { Skeleton } from '@/components/ui/skeleton'

type MetricType = 'rate' | 'latency'

interface MetricDefinition {
  key: keyof CalibrationMetrics
  title: string
  type: MetricType
  description: string
}

const METRIC_DEFINITIONS: MetricDefinition[] = [
  {
    key: 'gate_necessity',
    title: 'Gate Necessity Rate',
    type: 'rate',
    description: '% where human chose different from model recommendation',
  },
  {
    key: 'orchestrator_absorption',
    title: 'Absorption Rate',
    type: 'rate',
    description: '% of ambiguity resolved without escalating to human',
  },
  {
    key: 'resolution_latency',
    title: 'Resolution Latency',
    type: 'latency',
    description: 'Avg seconds from gate creation to human resolution',
  },
  {
    key: 'decision_durability',
    title: 'Decision Durability',
    type: 'rate',
    description: '% of resolutions with no subsequent rework in same cascade',
  },
  {
    key: 'cascade_rework',
    title: 'Cascade Rework Rate',
    type: 'rate',
    description: '% of completed cascades that were reopened',
  },
  {
    key: 'model_convergence',
    title: 'Model Convergence Rate',
    type: 'rate',
    description: '% of fan-outs where all models agreed',
  },
  {
    key: 'minority_accuracy',
    title: 'Minority Model Accuracy',
    type: 'rate',
    description: 'Rate at which human picked the minority model verdict',
  },
  {
    key: 'fanout_necessity',
    title: 'Fan-out Necessity Rate',
    type: 'rate',
    description: '% of fan-outs where multi-model differed from single-model',
  },
]

function MetricSkeleton() {
  return <Skeleton className="h-64 rounded-lg border border-zinc-800 bg-zinc-900/60" />
}

export default function MetricsPage() {
  const { data, isLoading, error } = useCalibrationMetrics()

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-2">
          <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Self-calibration</div>
          <h1 className="text-2xl font-semibold text-zinc-100">Metrics Dashboard</h1>
        </div>
      </header>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }, (_, index) => (
            <MetricSkeleton key={index} />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">Failed to load metrics</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {METRIC_DEFINITIONS.map((definition) => (
            <MetricCard
              key={definition.key}
              title={definition.title}
              description={definition.description}
              type={definition.type}
              value={data?.[definition.key] ?? null}
            />
          ))}
        </div>
      )}
    </div>
  )
}
