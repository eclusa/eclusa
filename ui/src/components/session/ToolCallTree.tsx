import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ToolCallTreeItem {
  name?: string
  function?: string
  args?: unknown
  result?: unknown
}

function formatValue(value: unknown) {
  if (value === undefined) {
    return 'undefined'
  }

  if (typeof value === 'string') {
    return value
  }

  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function ToolCallTree({ call, className }: { call: ToolCallTreeItem; className?: string }) {
  const label = call.function ?? call.name ?? 'tool call'

  return (
    <details className={cn('group rounded-lg border border-amber-900/40 bg-amber-950/10', className)}>
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-xs text-zinc-200">
        <ChevronRight className="h-3.5 w-3.5 text-amber-400 transition-transform group-open:rotate-90" />
        <span className="font-mono text-xs text-amber-400">{label}</span>
      </summary>
      <div className="space-y-3 border-t border-amber-900/30 px-3 py-3">
        <div className="space-y-1">
          <div className="text-[11px] uppercase tracking-[0.25em] text-zinc-500">Args</div>
          <pre className="overflow-x-auto rounded-md bg-zinc-950/70 p-3 font-mono text-xs leading-relaxed text-zinc-300">
            {formatValue(call.args ?? call)}
          </pre>
        </div>
        {call.result !== undefined ? (
          <div className="space-y-1">
            <div className="text-[11px] uppercase tracking-[0.25em] text-zinc-500">Result</div>
            <pre className="overflow-x-auto rounded-md bg-zinc-950/70 p-3 font-mono text-xs leading-relaxed text-zinc-300">
              {formatValue(call.result)}
            </pre>
          </div>
        ) : null}
      </div>
    </details>
  )
}
