import { describe, expect, it, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'

let handlers = {}

vi.mock('../services/api', () => ({
  connectRealtime: vi.fn((_userId, _token, h) => {
    handlers = h
    return {
      close: vi.fn(),
      onopen: null,
      onclose: null,
      onerror: null,
      onmessage: null,
    }
  }),
}))

import useRealtimeAlerts from '../hooks/useRealtimeAlerts'

describe('useRealtimeAlerts', () => {
  it('handles websocket message and failure safely', async () => {
    const { result } = renderHook(() => useRealtimeAlerts({ userId: 'u1', accessToken: 't', enabled: true }))

    act(() => {
      handlers.onOpen?.()
      handlers.onMessage?.({ data: JSON.stringify({ alert_id: 'a1', severity: 'High', title: 'Alert', message: 'Hello' }) })
      handlers.onError?.()
      handlers.onClose?.()
    })

    expect(result.current.liveEvents.length).toBeGreaterThanOrEqual(1)
    expect(['error', 'disconnected', 'reconnecting', 'connected']).toContain(result.current.connectionStatus)
  })
})
