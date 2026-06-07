import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearSession, signIn, signUp } from '../services/auth'

describe('auth development fallback', () => {
  beforeEach(() => {
    clearSession()
    vi.restoreAllMocks()
  })

  it('falls back to a local dev session when sign in cannot reach Supabase in development', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const session = await signIn('demo@carebank.local', 'password123')

    expect(session.access_token).toContain('carebank-dev:')
    expect(session.user.email).toBe('demo@carebank.local')
    expect(localStorage.getItem('carebank.supabase.session')).toContain('carebank-dev:')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('falls back to a local dev session when sign up cannot reach Supabase in development', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const result = await signUp('demo+signup@carebank.local', 'password123')

    expect(result.session.access_token).toContain('carebank-dev:')
    expect(result.session.user.email).toBe('demo+signup@carebank.local')
    expect(result.message).toMatch(/local demo session/i)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
