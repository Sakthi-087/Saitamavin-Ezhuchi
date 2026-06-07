import { describe, expect, it, vi, beforeEach } from 'vitest'
import { connectRealtime, fetchAnalysis, requestRealtimeTicket } from '../services/api'

describe('api safe error mapping', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('maps network failures to safe message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('socket fail')))
    await expect(fetchAnalysis('token')).rejects.toMatchObject({ message: 'Network connection failed. Please check your connection and try again.' })
  })

  it('maps server errors safely', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: vi.fn().mockRejectedValue(new Error('bad json')),
      }),
    )
    await expect(fetchAnalysis('token')).rejects.toMatchObject({ message: 'The server is temporarily unavailable. Please try again.' })
  })

  it('requests realtime tickets with bearer auth and no websocket token leakage', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ ticket: 'ticket-123', expires_in: 60, expires_at: '2026-01-01T00:00:00Z' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const socketMock = vi.fn()
    vi.stubGlobal('WebSocket', socketMock)

    const ticket = await requestRealtimeTicket('access-token-123')
    expect(ticket.ticket).toBe('ticket-123')
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toContain('/realtime/ws-ticket')
    expect(options.method).toBe('POST')
    expect(options.headers.get('Authorization')).toBe('Bearer access-token-123')

    connectRealtime('user-1', ticket.ticket)
    expect(socketMock).toHaveBeenCalledWith(expect.stringContaining('ticket=ticket-123'))
    const wsUrl = socketMock.mock.calls[0][0]
    expect(wsUrl).not.toContain('access-token-123')
    expect(wsUrl).not.toContain('token=')
  })
})
