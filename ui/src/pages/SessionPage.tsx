import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useSessionMessages, useSessions, type SessionMessage } from '@/api/sessions'
import { useSessionStream } from '@/ws/useSessionStream'
import { TranscriptMessage } from '@/components/session/TranscriptMessage'

function TranscriptSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }, (_, index) => (
        <div key={index} className="flex gap-3 border-b border-zinc-800/50 py-3">
          <Skeleton className="h-6 w-24 bg-zinc-800" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-4/5 bg-zinc-800" />
            <Skeleton className="h-4 w-2/3 bg-zinc-800" />
          </div>
        </div>
      ))}
    </div>
  )
}

function messageKey(message: SessionMessage) {
  return message.id ?? `${message.created_at}:${message.role}:${JSON.stringify(message.content)}`
}

function mergeMessages(history: SessionMessage[], live: SessionMessage[]) {
  const merged: SessionMessage[] = []
  const seen = new Set<string>()

  for (const message of [...history, ...live]) {
    const key = messageKey(message)
    if (seen.has(key)) {
      continue
    }

    seen.add(key)
    merged.push(message)
  }

  return merged
}

export function SessionPage() {
  const { id } = useParams()
  const selectedSessionId = id ?? null
  const { data: sessions } = useSessions()
  const selectedSession = useMemo(() => sessions?.find((session) => session.id === selectedSessionId) ?? null, [sessions, selectedSessionId])
  const { data: historyMessages, isLoading: isHistoryLoading, error: historyError } = useSessionMessages(selectedSessionId)
  const { messages: liveMessages, isConnected } = useSessionStream(selectedSessionId)
  const transcript = useMemo(() => mergeMessages(historyMessages ?? [], liveMessages), [historyMessages, liveMessages])

  if (!selectedSessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-sm text-zinc-500">Select a session from the list</div>
      </div>
    )
  }

  return (
    <section className="min-w-0 space-y-4" data-testid="session-transcript">
      <header className="space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-zinc-100" title={selectedSession?.id}>
            {selectedSession?.title ?? 'Session'}
          </h1>
          {isConnected ? (
            <Badge variant="outline" className="border-emerald-800/50 bg-emerald-950/30 text-emerald-300">
              <span className="mr-2 h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_3px_rgba(16,185,129,0.15)]" />
              Live
            </Badge>
          ) : null}
        </div>
        {selectedSession ? (
          <div className="text-xs text-zinc-500">
            {selectedSession.model} &middot; {selectedSession.state}
          </div>
        ) : null}
      </header>

      <Card className="border-zinc-800 bg-zinc-950/60 text-zinc-100 shadow-none">
        <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-zinc-800 p-4">
          <CardTitle className="text-base">Transcript</CardTitle>
          <div className="text-sm text-zinc-500">
            {transcript.length > 0 ? `${transcript.length} messages` : null}
          </div>
        </CardHeader>
        <CardContent className="p-4">
          {isHistoryLoading ? (
            <TranscriptSkeleton />
          ) : historyError ? (
            <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-400">Failed to load transcript</div>
          ) : transcript.length > 0 ? (
            <div className="space-y-0">
              {transcript.map((message, index) => (
                <TranscriptMessage
                  key={message.id ?? `${message.created_at}-${index}`}
                  role={message.role}
                  content={message.content}
                  cost={message.cost ?? (typeof message.cost_estimated_usd === 'number' ? { estimated_usd: message.cost_estimated_usd, tokens_in: message.tokens_in, tokens_out: message.tokens_out } : null)}
                  model={message.model}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4 text-sm text-zinc-500">No transcript messages yet</div>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
