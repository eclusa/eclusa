import { ResponsiveContainer, RadialBar, RadialBarChart, BarChart, Bar, PolarAngleAxis, XAxis, YAxis, ReferenceLine } from 'recharts'

type MetricType = 'rate' | 'latency'

export interface MetricChartProps {
  value: number
  type: MetricType
  title: string
  description: string
}

function getRateTone(value: number) {
  if (value > 0.7) {
    return {
      accent: '#22c55e',
      text: 'text-emerald-400',
      hint: 'healthy',
    }
  }

  if (value > 0.4) {
    return {
      accent: '#f59e0b',
      text: 'text-amber-400',
      hint: 'watch',
    }
  }

  return {
    accent: '#ef4444',
    text: 'text-red-400',
    hint: 'at risk',
  }
}

function getLatencyTone(value: number) {
  if (value < 3600) {
    return {
      accent: '#22c55e',
      text: 'text-emerald-400',
      hint: 'under 1h',
    }
  }

  if (value <= 86400) {
    return {
      accent: '#f59e0b',
      text: 'text-amber-400',
      hint: 'within 24h',
    }
  }

  return {
    accent: '#ef4444',
    text: 'text-red-400',
    hint: 'over 24h',
  }
}

function formatLatency(value: number) {
  if (value < 60) {
    return `${value.toFixed(0)}s`
  }

  if (value < 3600) {
    return `${(value / 60).toFixed(1)}m`
  }

  if (value < 86400) {
    return `${(value / 3600).toFixed(1)}h`
  }

  return `${(value / 86400).toFixed(1)}d`
}

export function MetricChart({ value, type, title, description }: MetricChartProps) {
  if (type === 'rate') {
    const tone = getRateTone(value)
    const percent = value * 100
    const chartData = [{ name: title, value: percent }]

    return (
      <div className="space-y-3">
        <div className="relative h-40">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart data={chartData} cx="50%" cy="54%" innerRadius="72%" outerRadius="100%" startAngle={180} endAngle={0}>
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} axisLine={false} />
              <RadialBar dataKey="value" background={{ fill: '#27272a' }} cornerRadius={999} fill={tone.accent} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <div className={`font-mono text-4xl font-semibold ${tone.text}`}>{percent.toFixed(1)}%</div>
            <div className="mt-1 text-[10px] uppercase tracking-[0.35em] text-zinc-500">{tone.hint}</div>
          </div>
        </div>
        <p className="text-xs text-zinc-500">{description}</p>
      </div>
    )
  }

  const tone = getLatencyTone(value)
  const chartData = [{ name: title, value }]
  const domainMax = Math.max(86400, value * 1.25 || 1)

  return (
    <div className="space-y-3">
      <div className="relative h-40">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <XAxis type="number" hide domain={[0, domainMax]} />
            <YAxis type="category" dataKey="name" hide />
            <ReferenceLine x={3600} stroke="#3f3f46" strokeDasharray="3 3" />
            <ReferenceLine x={86400} stroke="#3f3f46" strokeDasharray="3 3" />
            <Bar dataKey="value" barSize={16} radius={[999, 999, 999, 999]} fill={tone.accent} />
          </BarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <div className={`font-mono text-4xl font-semibold ${tone.text}`}>{formatLatency(value)}</div>
          <div className="mt-1 text-[10px] uppercase tracking-[0.35em] text-zinc-500">sec avg</div>
          <div className="mt-1 text-[10px] uppercase tracking-[0.35em] text-zinc-500">{tone.hint}</div>
        </div>
      </div>
      <p className="text-xs text-zinc-500">{description}</p>
    </div>
  )
}
