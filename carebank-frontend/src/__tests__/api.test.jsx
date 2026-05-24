import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fetchAnalysis } from '../services/api'

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
})
