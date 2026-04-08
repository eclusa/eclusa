import { formatDistanceToNow } from 'date-fns'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { StageStatusBadge } from './StageStatusBadge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { useStageOutput, type StageDetail } from '@/api/cascades'

interface Props {
  cascadeId: string
  stage: StageDetail
  onClose: () => void
}

const SECTION_FIELDS = [
  { label: 'Scope doc', keys: ['scope_doc', 'scopeDoc'] },
  { label: 'Matched sources', keys: ['matched_sources', 'matchedSources'] },
  { label: 'Coherence report', keys: ['coherence_report', 'coherenceReport'] },
  { label: 'Constraints', keys: ['constraints'] },
  { label: 'Tests', keys: ['tests'] },
  { label: 'Code sections', keys: ['code_sections', 'codeSections'] },
] as const

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isPrimitive(value: unknown): value is string | number | boolean | null {
  return value === null || ['string', 'number', 'boolean'].includes(typeof value)
}

function formatLabel(label: string) {
  return label
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^./, (character) => character.toUpperCase())
}

function pickField(output: unknown, keys: readonly string[]) {
  if (!isRecord(output)) {
    return undefined
  }

  for (const key of keys) {
    if (key in output) {
      return output[key]
    }
  }

  return undefined
}

function renderValue(value: unknown, depth = 0): ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-zinc-500">None</span>
  }

  if (typeof value === 'string') {
    if (value.includes('\n')) {
      return <pre className="whitespace-pre-wrap break-words font-mono text-xs text-zinc-300">{value}</pre>
    }

    return <span className="text-zinc-200">{value}</span>
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return <span className="text-zinc-200">{String(value)}</span>
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-zinc-500">Empty</span>
    }

    if (value.every(isPrimitive)) {
      return (
        <ul className="space-y-2">
          {value.map((item, index) => (
            <li key={`${index}-${String(item)}`} className="text-zinc-300">
              {renderValue(item, depth + 1)}
            </li>
          ))}
        </ul>
      )
    }

    return (
      <div className="space-y-2">
        {value.map((item, index) => (
          <div key={index} className="rounded-md border border-zinc-800 bg-zinc-950/40 p-3">
            {renderValue(item, depth + 1)}
          </div>
        ))}
      </div>
    )
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).filter(([, nested]) => nested !== undefined)

    if (entries.length === 0) {
      return <span className="text-zinc-500">Empty object</span>
    }

    if (depth >= 2) {
      return <pre className="whitespace-pre-wrap break-words font-mono text-xs text-zinc-300">{JSON.stringify(value, null, 2)}</pre>
    }

    return (
      <dl className="grid grid-cols-[minmax(0,12rem)_minmax(0,1fr)] gap-x-4 gap-y-3">
        {entries.map(([key, nested]) => (
          <div key={key} className="contents">
            <dt className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">{formatLabel(key)}</dt>
            <dd className="min-w-0 text-sm text-zinc-300">{renderValue(nested, depth + 1)}</dd>
          </div>
        ))}
      </dl>
    )
  }

  return <span className="text-zinc-300">{String(value)}</span>
}

export function StageOutputPanel({ cascadeId, stage, onClose }: Props) {
  const stageOutputQuery = useStageOutput(cascadeId, stage.state === 'resolved' ? stage.id : null)
  const resolvedLabel = stage.resolved_at ? formatDistanceToNow(new Date(stage.resolved_at), { addSuffix: true }) : null
  const output = stageOutputQuery.data?.output
  const outputSummary = stageOutputQuery.data?.output_summary ?? stage.output_summary
  const structuredSections = SECTION_FIELDS.map((section) => ({
    label: section.label,
    value: pickField(output, section.keys),
  })).filter((section) => section.value !== undefined && section.value !== null)

  const hasStructuredOutput = structuredSections.length > 0
  const showGenericOutput = !hasStructuredOutput && output !== undefined && output !== null

  return (
    <div className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-900 p-4 shadow-2xl shadow-black/20">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">{stage.display_name}</div>
          <div className="flex flex-wrap items-center gap-2">
            <StageStatusBadge state={stage.state} />
            {resolvedLabel ? <div className="text-xs text-zinc-500">Resolved {resolvedLabel}</div> : null}
          </div>
          {outputSummary ? <div className="text-sm text-zinc-400">{outputSummary}</div> : null}
        </div>
        <button
          type="button"
          onClick={onClose}
          className={cn(
            'rounded-md border border-zinc-800 p-1.5 text-zinc-500 transition-colors',
            'hover:border-zinc-700 hover:text-zinc-300',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-900/60',
          )}
          aria-label={`Close ${stage.display_name} output`}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {stage.state !== 'resolved' ? (
        <div className="text-sm text-zinc-500">Stage is {stage.state} — output not yet available.</div>
      ) : stageOutputQuery.isLoading ? (
        <Skeleton className="h-32 bg-zinc-800" />
      ) : stageOutputQuery.isError ? (
        <div className="text-sm text-red-400">Failed to load output</div>
      ) : output === null || output === undefined ? (
        <div className="text-sm text-zinc-500">No output recorded.</div>
      ) : hasStructuredOutput ? (
        <div className="space-y-3">
          {structuredSections.map((section) => (
            <section key={section.label} className="rounded-md border border-zinc-800 bg-zinc-950/30 p-3">
              <div className="mb-2 text-[11px] font-mono uppercase tracking-[0.25em] text-zinc-500">{section.label}</div>
              <div className="space-y-2 text-sm text-zinc-300">{renderValue(section.value)}</div>
            </section>
          ))}
        </div>
      ) : showGenericOutput ? (
        <section className="rounded-md border border-zinc-800 bg-zinc-950/30 p-3">
          <div className="mb-2 text-[11px] font-mono uppercase tracking-[0.25em] text-zinc-500">Artifact output</div>
          <div className="space-y-2 text-sm text-zinc-300">{renderValue(output)}</div>
        </section>
      ) : null}
    </div>
  )
}
