import { describe, expect, it, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'

const { connectRealtimeMock, requestRealtimeTicketMock } = vi.hoisted(() => {
  const connectRealtimeMockImpl = vi.fn((_userId, ticket, h) => {
    globalThis.__carebankRealtimeHandlers = h
    return {
      close: vi.fn(),
      onopen: null,
      onclose: null,
      onerror: null,
      onmessage: null,
      ticket,
    }
  })
  const requestRealtimeTicketMockImpl = vi.fn(async () => ({ ticket: 'ticket-123', expires_in: 60, expires_at: '2026-01-01T00:00:00Z' }))
  return {
    connectRealtimeMock: connectRealtimeMockImpl,
    requestRealtimeTicketMock: requestRealtimeTicketMockImpl,
  }
})

vi.mock('../services/api', () => ({
  connectRealtime: connectRealtimeMock,
  requestRealtimeTicket: requestRealtimeTicketMock,
}))

import useRealtimeAlerts from '../hooks/useRealtimeAlerts'

describe('useRealtimeAlerts', () => {
  it('handles websocket message and failure safely', async () => {
    const { result } = renderHook(() => useRealtimeAlerts({ userId: 'u1', accessToken: 't', enabled: true }))

    await act(async () => {
      await Promise.resolve()
      globalThis.__carebankRealtimeHandlers?.onOpen?.()
      globalThis.__carebankRealtimeHandlers?.onMessage?.({ data: JSON.stringify({ alert_id: 'a1', severity: 'High', title: 'Alert', message: 'Hello' }) })
      globalThis.__carebankRealtimeHandlers?.onError?.()
      globalThis.__carebankRealtimeHandlers?.onClose?.()
    })

    expect(result.current.liveEvents.length).toBeGreaterThanOrEqual(1)
    expect(['error', 'disconnected', 'reconnecting', 'connected']).toContain(result.current.connectionStatus)
    expect(requestRealtimeTicketMock).toHaveBeenCalledWith('t')
    expect(connectRealtimeMock).toHaveBeenCalledWith('u1', 'ticket-123', expect.any(Object))
  })
})
