import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '@/auth/AuthProvider'
import type { SessionMessage } from '@/api/sessions'
import { useWebSocket } from './useWebSocket'

function messageKey(message: SessionMessage) {
  return message.id ?? `${message.created_at}:${message.role}:${JSON.stringify(message.content)}`
}

function normalizeMessage(value: unknown) {
  if (!value || typeof value !== 'object') {
    return null
  }

  const message = value as Partial<SessionMessage>
  if (typeof message.role !== 'string' || typeof message.created_at !== 'string') {
    return null
  }

  return message as SessionMessage
}

export function useSessionStream(sessionId: string | null) {
  const { token } = useAuth()
  const [messages, setMessages] = useState<SessionMessage[]>([])
  const isEnabled = Boolean(sessionId && token)

  const wsUrl = useMemo(() => {
    if (!sessionId || !token) {
      return '/ws/sessions/disabled'
    }

    return `/ws/sessions/${sessionId}?token=${encodeURIComponent(token)}`
  }, [sessionId, token])

  const { lastJsonMessage, readyState } = useWebSocket(wsUrl, {
    shouldReconnect: () => true,
    reconnectAttempts: 10,
    reconnectInterval: 3_000,
    share: true,
  } as any)

  useEffect(() => {
    setMessages([])
  }, [sessionId])

  useEffect(() => {
    if (!isEnabled) {
      setMessages([])
    }
  }, [isEnabled])

  useEffect(() => {
    if (Array.isArray(lastJsonMessage)) {
      const batch = lastJsonMessage.map(normalizeMessage).filter(Boolean) as SessionMessage[]
      if (batch.length > 0) {
        setMessages(batch)
      }
      return
    }

    const message = normalizeMessage(lastJsonMessage)
    if (!message) {
      return
    }

    setMessages((previous) => {
      const nextKey = messageKey(message)
      if (previous.some((item) => messageKey(item) === nextKey)) {
        return previous
      }

      return [...previous, message]
    })
  }, [lastJsonMessage])

  return {
    messages,
    isConnected: isEnabled && readyState === 1,
  }
}
