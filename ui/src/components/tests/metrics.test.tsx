import { renderToStaticMarkup } from 'react-dom/server'
import { vi } from 'vitest'
import { EmptyStateGuard } from '@/components/metrics/EmptyStateGuard'
import { MetricCard } from '@/components/metrics/MetricCard'
import { MetricChart } from '@/components/metrics/MetricChart'
import MetricsPage from '@/pages/MetricsPage'

vi.mock('@/api/metrics', () => ({
  useCalibrationMetrics: () => ({
    data: {
      gate_necessity: 0.85,
      orchestrator_absorption: 0.91,
      resolution_latency: 5400,
      decision_durability: 0.74,
      cascade_rework: 0.12,
      model_convergence: 0.68,
      minority_accuracy: 0.43,
      fanout_necessity: null,
    },
    isLoading: false,
    error: null,
    dataUpdatedAt: Date.parse('2026-04-05T12:00:00.000Z'),
  }),
}))

test('empty state guard renders the insufficient data message', () => {
  const html = renderToStaticMarkup(
    <EmptyStateGuard value={null} title="Gate Necessity Rate">
      <div>unused</div>
    </EmptyStateGuard>,
  )

  expect(html).toContain('Requires 10+ resolved gates to compute.')
  expect(html).toContain('Gate Necessity Rate')
})

test('metric chart renders rate values as percentages', () => {
  const html = renderToStaticMarkup(
    <MetricChart value={0.85} type="rate" title="Gate Necessity Rate" description="% where human chose different from model recommendation" />,
  )

  expect(html).toContain('85.0%')
  expect(html).toContain('healthy')
})

test('metric card renders guarded empty state when value is missing', () => {
  const html = renderToStaticMarkup(
    <MetricCard
      title="Fan-out Necessity Rate"
      description="% of fan-outs where multi-model differed from single-model"
      type="rate"
      value={null}
    />,
  )

  expect(html).toContain('Requires 10+ resolved gates to compute.')
  expect(html).toContain('Fan-out Necessity Rate')
})

test('metrics page renders all eight calibration cards', () => {
  const html = renderToStaticMarkup(<MetricsPage />)

  expect(html).toContain('Metrics Dashboard')
  expect(html).toContain('Gate Necessity Rate')
  expect(html).toContain('Absorption Rate')
  expect(html).toContain('Resolution Latency')
  expect(html).toContain('Decision Durability')
  expect(html).toContain('Cascade Rework Rate')
  expect(html).toContain('Model Convergence Rate')
  expect(html).toContain('Minority Model Accuracy')
  expect(html).toContain('Fan-out Necessity Rate')
  expect(html).toContain('85.0%')
  expect(html).toContain('Requires 10+ resolved gates to compute.')
})
