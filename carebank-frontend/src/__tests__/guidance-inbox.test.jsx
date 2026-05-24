import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import GuidanceInbox from '../components/GuidanceInbox'

describe('GuidanceInbox', () => {
  it('sorts by priority and renders steps', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          items: [
            { guidance_id: 'g1', priority: 'Positive', title: 'Keep habits', confidence: 0.6, actionability_score: 0.5, rationale: 'good', action_steps: ['step 1'], expected_impact: 'impact', source_signals: [], related_risk_events: [], ttl_days: 7 },
            { guidance_id: 'g2', priority: 'High', title: 'Cut spend', confidence: 0.9, actionability_score: 0.9, rationale: 'urgent', action_steps: ['step A'], expected_impact: 'impact', source_signals: [], related_risk_events: [], ttl_days: 7 },
          ],
        }),
      }),
    )

    render(<GuidanceInbox accessToken="t" />)
    await waitFor(() => expect(screen.getByText('Guidance Inbox')).toBeInTheDocument())
    expect(screen.getByText('Cut spend')).toBeInTheDocument()
    expect(screen.getByText('step A')).toBeInTheDocument()
  })
})
