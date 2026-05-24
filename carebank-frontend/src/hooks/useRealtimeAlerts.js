import { useCallback, useEffect, useRef, useState } from 'react'
import { connectRealtime } from '../services/api'

const MAX_EVENTS = 50

function sanitizeText(value, fallback = 'N/A') {
  if (typeof value !== 'string') return fallback
  const text = value.replace(/bearer\s+[a-z0-9\-_.]+/gi, '[redacted]').trim()
  return text.slice(0, 240) || fallback
}

function sanitizeEvent(raw) {
  const severity = String(raw?.severity || raw?.level || 'Info')
  const createdAt = raw?.created_at || raw?.timestamp || new Date().toISOString()

  return {
    eventId: String(raw?.alert_id || raw?.event_id || `${Date.now()}-${Math.random()}`),
    severity: sanitizeText(severity, 'Info'),
    title: sanitizeText(raw?.title || raw?.event_type || 'Realtime update', 'Realtime update'),
    message: sanitizeText(raw?.message || raw?.summary || 'New intelligence event received.'),
    createdAt: sanitizeText(String(createdAt), new Date().toISOString()),
  }
}

export default function useRealtimeAlerts({ userId, accessToken, enabled = true }) {
  const [connectionStatus, setConnectionStatus] = useState('disconnected')
  const [liveEvents, setLiveEvents] = useState([])
  const [latestAlert, setLatestAlert] = useState(null)
  const socketRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const attemptsRef = useRef(0)

  const dismissEvent = useCallback((eventId) => {
    setLiveEvents((current) => current.filter((event) => event.eventId !== eventId))
  }, [])

  const clearSocket = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }

    const socket = socketRef.current
    if (socket) {
      socket.onopen = null
      socket.onmessage = null
      socket.onclose = null
      socket.onerror = null
      socket.close()
      socketRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!enabled || !userId || !accessToken) {
      setConnectionStatus('disabled')
      clearSocket()
      return
    }

    let stopped = false

    const scheduleReconnect = () => {
      if (stopped) return
      const delayMs = Math.min(1000 * Math.pow(2, attemptsRef.current), 15000)
      reconnectTimerRef.current = setTimeout(() => {
        attemptsRef.current += 1
        openSocket()
      }, delayMs)
    }

    const openSocket = () => {
      try {
        setConnectionStatus(attemptsRef.current ? 'reconnecting' : 'connecting')
        socketRef.current = connectRealtime(userId, accessToken, {
          onOpen: () => {
            attemptsRef.current = 0
            setConnectionStatus('connected')
          },
          onMessage: (event) => {
            try {
              const parsed = JSON.parse(event.data)
              const sanitized = sanitizeEvent(parsed)
              setLatestAlert(sanitized)
              setLiveEvents((current) => [sanitized, ...current].slice(0, MAX_EVENTS))
            } catch {
              // Ignore malformed messages.
            }
          },
          onClose: () => {
            if (stopped) return
            setConnectionStatus('disconnected')
            scheduleReconnect()
          },
          onError: () => {
            setConnectionStatus('error')
          },
        })
      } catch {
        setConnectionStatus('error')
        scheduleReconnect()
      }
    }

    openSocket()

    return () => {
      stopped = true
      clearSocket()
      setConnectionStatus('disconnected')
    }
  }, [accessToken, clearSocket, enabled, userId])

  return {
    connectionStatus,
    liveEvents,
    latestAlert,
    dismissEvent,
  }
}
