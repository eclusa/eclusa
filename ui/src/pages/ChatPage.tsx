import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { ChatInput } from '@/components/chat/ChatInput'
import { ChatMessage } from '@/components/chat/ChatMessage'
import { useChat, classifyIntent, type SccModelConfig, type SccStage } from '@/api/chat'
import { cn } from '@/lib/utils'

const modelOptions = [
  'openai:glm-5.1',
  'anthropic:claude-sonnet-4-6',
  'anthropic:claude-haiku-4-5',
  'openai:gpt-4o',
]

export function ChatPage() {
  const [searchParams] = useSearchParams()
  const [input, setInput] = useState('')
  const [model, setModel] = useState(modelOptions[0] ?? 'openai:glm-5.1')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [sccDefaultModel, setSccDefaultModel] = useState('')
  const [stageOverrides, setStageOverrides] = useState<Partial<Record<SccStage, string>>>({})

  const modelConfig = useMemo<SccModelConfig | undefined>(() => {
    const overrides = Object.fromEntries(
      Object.entries(stageOverrides).filter(([, v]) => v !== '')
    ) as Partial<Record<SccStage, string>>
    if (!sccDefaultModel && Object.keys(overrides).length === 0) return undefined
    return {
      ...(sccDefaultModel ? { default_model: sccDefaultModel } : {}),
      ...(Object.keys(overrides).length > 0 ? { stage_overrides: overrides } : {}),
    }
  }, [sccDefaultModel, stageOverrides])

  const [buildMode, setBuildMode] = useState(false)
  const { messages, sendMessage, isStreaming, sessionId, loadSession, newThread } = useChat({ model, modelConfig, mode: buildMode ? 'build' : 'chat' })
  const bottomRef = useRef<HTMLDivElement | null>(null)

  // Load session from URL param
  const urlSession = searchParams.get('s')
  const loadedRef = useRef<string | null>(null)
  useEffect(() => {
    if (urlSession && urlSession !== loadedRef.current && urlSession !== sessionId) {
      loadedRef.current = urlSession
      loadSession(urlSession)
    } else if (!urlSession && loadedRef.current) {
      loadedRef.current = null
      newThread()
    }
  }, [urlSession, sessionId, loadSession, newThread])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isStreaming])

  const statusLabel = useMemo(() => {
    if (isStreaming) {
      return 'Streaming'
    }

    return sessionId ? 'Ready' : 'New thread'
  }, [isStreaming, sessionId])

  async function handleSend() {
    const next = input.trim()
    if (!next || isStreaming) return
    setInput('')
    const autoMode = (!buildMode && classifyIntent(next) === 'build') ? 'build' : (buildMode ? 'build' : 'chat')
    if (autoMode === 'build' && !buildMode) setBuildMode(true)
    await sendMessage(next, autoMode)
  }

  return (
    <div className="flex min-h-[calc(100vh-3rem)] flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-400">Chat</div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-zinc-100">Operator chat</h1>
            <Badge variant="outline" className={cn('border-zinc-800 bg-zinc-950/60 text-zinc-400')}>
              {statusLabel}
            </Badge>
            {sessionId ? (
              <Badge variant="outline" className="border-blue-900/40 bg-blue-950/20 text-blue-300">
                {sessionId}
              </Badge>
            ) : null}
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">Model</label>
          <Select
            value={model}
            onChange={(event) => setModel(event.target.value as (typeof modelOptions)[number])}
            disabled={isStreaming}
            className="min-w-80 border-zinc-800 bg-zinc-950/60 text-zinc-100"
          >
            {modelOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>

          <button
            type="button"
            className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 hover:text-zinc-300 transition-colors text-left"
            onClick={() => setShowModelConfig(v => !v)}
          >
            {showModelConfig ? '- Hide' : '+ Advanced'} SCC model config
          </button>
          {showModelConfig && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 space-y-3 min-w-80">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-zinc-500">Default SCC model</label>
                <select
                  value={sccDefaultModel}
                  onChange={e => setSccDefaultModel(e.target.value)}
                  className="border border-zinc-800 bg-zinc-950 text-zinc-100 text-xs rounded px-2 py-1"
                >
                  <option value="">Inherit from env (SCC_MODEL_DEFAULT)</option>
                  {modelOptions.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
              {(['refine','fanout','match','cohere','formalize','derive','generate'] as SccStage[]).map(stage => (
                <div key={stage} className="flex flex-col gap-1">
                  <label className="text-xs text-zinc-500">{stage}</label>
                  <select
                    value={stageOverrides[stage] ?? ''}
                    onChange={e => setStageOverrides(prev => ({ ...prev, [stage]: e.target.value }))}
                    className="border border-zinc-800 bg-zinc-950 text-zinc-100 text-xs rounded px-2 py-1"
                  >
                    <option value="">Inherit default</option>
                    {modelOptions.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 mt-2">
            <button
              type="button"
              onClick={() => setBuildMode(v => !v)}
              disabled={isStreaming}
              className={cn(
                'px-3 py-1 rounded text-xs font-mono uppercase tracking-[0.25em] border transition-colors',
                buildMode
                  ? 'border-blue-600 bg-blue-950/60 text-blue-300'
                  : 'border-zinc-800 bg-zinc-950/60 text-zinc-500 hover:text-zinc-300'
              )}
            >
              {buildMode ? 'Build mode ON' : 'Build mode OFF'}
            </button>
            {buildMode && (
              <span className="text-xs text-zinc-500">Creates SCC cascade (7 stages)</span>
            )}
          </div>
        </div>
      </header>

      <Card className="flex min-h-0 flex-1 flex-col border-zinc-800 bg-zinc-950/60 text-zinc-100 shadow-none">
        <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-zinc-800 p-4">
          <CardTitle className="text-base">Conversation</CardTitle>
          <div className="text-sm text-zinc-500">
            {messages.length > 0 ? `${messages.length} messages` : 'Start the first request'}
          </div>
        </CardHeader>

        <CardContent className="flex min-h-0 flex-1 flex-col gap-4 p-4">
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            <div className="space-y-3">
              {messages.length > 0 ? (
                messages.map((message, index) => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    isStreaming={isStreaming && index === messages.length - 1 && message.role === 'assistant'}
                  />
                ))
              ) : (
                <div className="flex h-full min-h-[24rem] items-center justify-center rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 p-6 text-center text-sm text-zinc-500">
                  Send a request to start a new operator conversation.
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
            <ChatInput value={input} onChange={setInput} onSubmit={handleSend} disabled={isStreaming} />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
            <span>Enter sends a message.</span>
            <Button variant="ghost" size="sm" onClick={() => setInput('')} disabled={!input}>
              Clear
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
