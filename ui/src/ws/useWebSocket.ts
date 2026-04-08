import { useEffect, useRef, useState } from 'react'

type ReconnectOption = boolean | ((event: CloseEvent) => boolean)

export type UseWebSocketOptions = {
  shouldReconnect?: ReconnectOption
  reconnectInterval?: number
  reconnectAttempts?: number
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const { shouldReconnect = true, reconnectInterval = 3000, reconnectAttempts = 10 } = options
  const [lastJsonMessage, setLastJsonMessage] = useState<unknown>(null)
  const [readyState, setReadyState] = useState<number>(WebSocket.CLOSED)
  const socketRef = useRef<WebSocket | null>(null)
  const attemptsRef = useRef(0)
  const retryRef = useRef<number | null>(null)
  const shouldReconnectRef = useRef<ReconnectOption>(shouldReconnect)

  useEffect(() => {
    shouldReconnectRef.current = shouldReconnect
  }, [shouldReconnect])

  useEffect(() => {
    if (retryRef.current !== null) {
      window.clearTimeout(retryRef.current)
      retryRef.current = null
    }
    socketRef.current?.close()
    socketRef.current = null
    setLastJsonMessage(null)

    if (!url || url.includes('disabled')) {
      setReadyState(WebSocket.CLOSED)
      return
    }

    attemptsRef.current = 0
    let cancelled = false

    const connect = () => {
      if (cancelled) return

      const socket = new WebSocket(url)
      socketRef.current = socket
      setReadyState(socket.readyState)

      socket.onopen = () => {
        attemptsRef.current = 0
        setReadyState(WebSocket.OPEN)
      }

      socket.onmessage = (event) => {
        try {
          setLastJsonMessage(JSON.parse(event.data))
        } catch {
          // Ignore non-JSON messages.
        }
      }

      socket.onerror = () => {
        setReadyState(socket.readyState)
      }

      socket.onclose = (event) => {
        setReadyState(WebSocket.CLOSED)
        if (cancelled) return

        const currentShouldReconnect = shouldReconnectRef.current
        const wantsReconnect =
          typeof currentShouldReconnect === 'function' ? currentShouldReconnect(event) : currentShouldReconnect
        if (!wantsReconnect || attemptsRef.current >= reconnectAttempts) return

        attemptsRef.current += 1
        retryRef.current = window.setTimeout(connect, reconnectInterval)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (retryRef.current !== null) {
        window.clearTimeout(retryRef.current)
        retryRef.current = null
      }
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [url, reconnectAttempts, reconnectInterval])

  return { lastJsonMessage, readyState }
}
