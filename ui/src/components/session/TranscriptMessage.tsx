import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { SessionContent, SessionCost, SessionMessage, SessionToolCall } from '@/api/sessions'
import { CostChip } from './CostChip'
import { JudgmentVerdictCard } from './JudgmentVerdictCard'
import { ToolCallTree } from './ToolCallTree'

const roleStyles: Record<SessionMessage['role'], string> = {
  user: 'border-zinc-800 bg-zinc-950/60 text-zinc-300',
  assistant: 'border-blue-900/40 bg-blue-950/20 text-blue-300',
  tool: 'border-amber-900/40 bg-amber-950/15 text-amber-300',
  system: 'border-zinc-800 bg-zinc-900/70 text-zinc-500',
}

function asContentObject(content: SessionContent | string) {
  if (typeof content === 'string') {
    return { type: 'text', text: content } as SessionContent
  }

  return content
}

function extractToolCalls(content: SessionContent) {
  if (Array.isArray(content.tool_calls) && content.tool_calls.length > 0) {
    return content.tool_calls
  }

  if (content.tool_call) {
    return [content.tool_call]
  }

  if (content.type === 'tool-call' || content.args !== undefined || content.result !== undefined) {
    return [{ name: content.name, function: content.function, args: content.args, result: content.result } satisfies SessionToolCall]
  }

  return []
}

function resolveCost(content: SessionContent, cost?: SessionCost | null) {
  return cost ?? content.cost ?? null
}

export function TranscriptMessage({
  role,
  content,
  cost,
  model,
}: {
  role: SessionMessage['role']
  content: SessionContent | string
  cost?: SessionCost | null
  model?: string | null
}) {
  const normalizedContent = asContentObject(content)
  const verdict = normalizedContent.verdict
  const text = normalizedContent.text
  const toolCalls = extractToolCalls(normalizedContent)
  const resolvedCost = resolveCost(normalizedContent, cost)

  return (
    <div className="flex gap-3 border-b border-zinc-800/50 py-3">
      <Badge variant="outline" className={cn('h-fit border text-xs font-mono uppercase tracking-wide', roleStyles[role])}>
        {role}
        {model ? <span className="ml-2 text-[10px] normal-case tracking-normal text-zinc-500">{model}</span> : null}
      </Badge>

      <div className="min-w-0 flex-1 space-y-2">
        {text ? <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">{text}</p> : null}

        {toolCalls.length > 0 ? (
          <div className="space-y-2">
            {toolCalls.map((call, index) => (
              <ToolCallTree key={`${call.function ?? call.name ?? 'tool'}-${index}`} call={call} />
            ))}
          </div>
        ) : null}

        {verdict ? <JudgmentVerdictCard verdict={verdict} /> : null}
      </div>

      <CostChip cost={resolvedCost} />
    </div>
  )
}
