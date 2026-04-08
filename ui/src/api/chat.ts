import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '@/auth/AuthProvider'

export type ChatRole = 'user' | 'assistant'

export interface ChatSession {
  id: string
  model: string
  state: string
  created_at: string
  preview: string
}

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  createdAt: string
}

interface StreamEvent {
  event?: string
  data: string
}

export type SccStage = 'refine' | 'fanout' | 'match' | 'cohere' | 'formalize' | 'derive' | 'generate'

export interface SccModelConfig {
  default_model?: string
  stage_overrides?: Partial<Record<SccStage, string>>
}

interface UseChatOptions {
  model: string
  modelConfig?: SccModelConfig
  mode?: 'chat' | 'build'
}

interface ChatRequestBody {
  messages: Array<Pick<ChatMessage, 'role' | 'content'>>
  model: string
  session_id: string | null
  model_config?: SccModelConfig
  mode?: 'chat' | 'build'
}

export function classifyIntent(text: string): 'chat' | 'build' {
  const lower = text.toLowerCase()
  const buildPatterns = [
    /\bbuild\b/, /\bcreate\b/, /\bmake\b/, /\bgenerate\b/, /\bscaffold\b/,
    /\bimplement\b/, /\bdevelop\b/, /\bwrite (a |an |the )?(app|service|api|component|function|script)/,
    /\bapp\b.*\bfor\b/, /\btodo app\b/, /\bcrud\b/,
  ]
  return buildPatterns.some(p => p.test(lower)) ? 'build' : 'chat'
}

function createId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }

  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function extractDelta(value: unknown) {
  if (!value || typeof value !== 'object') {
    return ''
  }

  const payload = value as Record<string, unknown>
  const candidates = ['delta', 'chunk', 'text', 'content', 'message', 'response', 'token', 'append']

  for (const key of candidates) {
    const candidate = payload[key]
    if (typeof candidate === 'string' && candidate.length > 0) {
      return candidate
    }
  }

  return ''
}

function extractSessionId(value: unknown) {
  if (!value || typeof value !== 'object') {
    return null
  }

  const payload = value as Record<string, unknown>
  const sessionId = payload['session_id'] ?? payload['sessionId'] ?? payload['id']
  return typeof sessionId === 'string' && sessionId.length > 0 ? sessionId : null
}

function extractDone(value: unknown, eventName?: string) {
  if (eventName === 'done' || eventName === 'close' || eventName === 'end') {
    return true
  }

  if (!value || typeof value !== 'object') {
    return false
  }

  const payload = value as Record<string, unknown>
  return (
    payload['done'] === true ||
    payload['completed'] === true ||
    payload['final'] === true ||
    payload['type'] === 'done' ||
    payload['finishReason'] != null
  )
}

function parseEvent(block: string): StreamEvent | null {
  const lines = block.split(/\r?\n/)
  let event: string | undefined
  const dataParts: string[] = []

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
      continue
    }

    if (line.startsWith('data:')) {
      dataParts.push(line.slice(5).replace(/^ /, ''))
      continue
    }

    // Vercel AI Data Stream Protocol: 0:"text" or d:{...}
    const prefixMatch = line.match(/^([0-9a-z]):(.+)/)
    if (prefixMatch?.[2]) {
      dataParts.push(prefixMatch[2])
    }
  }

  if (dataParts.length === 0) {
    return null
  }

  return {
    event,
    data: dataParts.join('\n'),
  }
}

function parsePayload(data: string) {
  const trimmed = data.trim()
  if (!trimmed || trimmed === '[DONE]') {
    return { raw: trimmed, value: null, done: trimmed === '[DONE]' }
  }

  try {
    return { raw: trimmed, value: JSON.parse(trimmed), done: false }
  } catch {
    return { raw: trimmed, value: trimmed, done: false }
  }
}

export function useChatSessions() {
  const { getAuthHeader } = useAuth()
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const resp = await fetch('/api/chat/sessions', { headers: getAuthHeader() })
      if (resp.ok) {
        setSessions(await resp.json())
      }
    } finally {
      setLoading(false)
    }
  }, [getAuthHeader])

  useEffect(() => { refresh() }, [refresh])

  return { sessions, loading, refresh }
}

export function useChat({ model, modelConfig, mode = 'chat' }: UseChatOptions) {
  const { getAuthHeader } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const requestHeaders = useMemo(
    () => ({
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    }),
    [getAuthHeader],
  )

  const sendMessage = useCallback(
    async (content: string, modeOverride?: 'chat' | 'build') => {
      const effectiveMode = modeOverride ?? mode
      const trimmed = content.trim()
      if (!trimmed || isStreaming) {
        return
      }

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: trimmed,
        createdAt: new Date().toISOString(),
      }

      const assistantMessageId = createId()
      const assistantCreatedAt = new Date().toISOString()

      setMessages((previous) => [
        ...previous,
        userMessage,
        {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          createdAt: assistantCreatedAt,
        },
      ])
      setIsStreaming(true)

      let accumulated = ''

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: requestHeaders,
          body: JSON.stringify({
            messages: [...messages, userMessage].map(({ role, content: messageContent }) => ({ role, content: messageContent })),
            model,
            session_id: sessionId,
            mode: effectiveMode,
            ...(modelConfig ? { model_config: modelConfig } : {}),
          } satisfies ChatRequestBody),
          signal: controller.signal,
        })

        if (!response.ok || !response.body) {
          throw new Error(`Request failed (${response.status})`)
        }

        // Build mode returns JSON, not a stream
        if (response.headers.get('content-type')?.includes('application/json')) {
          const data = await response.json()
          const buildMsg = data.cascade_id
            ? `SCC cascade created. cascade_id: ${data.cascade_id}`
            : 'SCC cascade created.'
          setMessages((previous) =>
            previous.map((message) =>
              message.id === assistantMessageId ? { ...message, content: buildMsg } : message,
            ),
          )
          setIsStreaming(false)
          abortRef.current = null
          return
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { value, done } = await reader.read()
          if (done) {
            break
          }

          buffer += decoder.decode(value, { stream: true })

          while (true) {
            const separatorIndex = buffer.indexOf('\n\n')
            const carriageIndex = buffer.indexOf('\r\n\r\n')
            const splitIndex =
              separatorIndex === -1
                ? carriageIndex
                : carriageIndex === -1
                  ? separatorIndex
                  : Math.min(separatorIndex, carriageIndex)

            if (splitIndex === -1) {
              break
            }

            const delimiterLength = buffer.startsWith('\r\n\r\n', splitIndex) ? 4 : 2
            const rawEvent = buffer.slice(0, splitIndex)
            buffer = buffer.slice(splitIndex + delimiterLength)

            const parsedEvent = parseEvent(rawEvent)
            if (!parsedEvent) {
              continue
            }

            const parsedPayload = parsePayload(parsedEvent.data)

            if (parsedPayload.done || extractDone(parsedPayload.value, parsedEvent.event)) {
              if (typeof parsedPayload.value === 'object' && parsedPayload.value) {
                const nextSessionId = extractSessionId(parsedPayload.value)
                if (nextSessionId) {
                  setSessionId(nextSessionId)
                }
              }
              break
            }

            if (typeof parsedPayload.value === 'object' && parsedPayload.value) {
              const nextSessionId = extractSessionId(parsedPayload.value)
              if (nextSessionId) {
                setSessionId(nextSessionId)
              }
            }

            const delta =
              typeof parsedPayload.value === 'string'
                ? parsedPayload.value
                : extractDelta(parsedPayload.value)

            if (delta) {
              accumulated += delta
              setMessages((previous) =>
                previous.map((message) =>
                  message.id === assistantMessageId ? { ...message, content: accumulated } : message,
                ),
              )
            }
          }
        }

        const tail = buffer.trim()
        if (tail) {
          const fallbackPayload = parsePayload(tail)
          if (typeof fallbackPayload.value === 'object' && fallbackPayload.value) {
            const nextSessionId = extractSessionId(fallbackPayload.value)
            if (nextSessionId) {
              setSessionId(nextSessionId)
            }
            const delta = extractDelta(fallbackPayload.value)
            if (delta) {
              accumulated += delta
            }
          } else if (typeof fallbackPayload.value === 'string') {
            accumulated += fallbackPayload.value
          }
        }

        setMessages((previous) =>
          previous.map((message) => (message.id === assistantMessageId ? { ...message, content: accumulated } : message)),
        )
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          setMessages((previous) =>
            previous.map((message) =>
              message.id === assistantMessageId
                ? { ...message, content: 'Failed to stream response. Please try again.' }
                : message,
            ),
          )
        }
      } finally {
        abortRef.current = null
        setIsStreaming(false)
      }
    },
    [isStreaming, messages, mode, model, modelConfig, requestHeaders, sessionId],
  )

  const loadSession = useCallback(
    async (id: string) => {
      if (isStreaming) return
      try {
        const resp = await fetch(`/api/sessions/${id}/messages`, { headers: requestHeaders })
        if (!resp.ok) return
        const data: Array<{ id: string; role: string; content: Record<string, string>; created_at: string }> = await resp.json()
        const loaded: ChatMessage[] = data.map((m) => ({
          id: m.id,
          role: m.role as ChatRole,
          content: m.content?.['text'] ?? JSON.stringify(m.content),
          createdAt: m.created_at,
        }))
        setMessages(loaded)
        setSessionId(id)
      } catch {
        // ignore load errors
      }
    },
    [isStreaming, requestHeaders],
  )

  const newThread = useCallback(() => {
    if (isStreaming) return
    setMessages([])
    setSessionId(null)
  }, [isStreaming])

  return {
    messages,
    sendMessage,
    isStreaming,
    sessionId,
    loadSession,
    newThread,
  }
}
