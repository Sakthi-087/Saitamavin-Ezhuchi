import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import RiskIntelligencePanel from '../components/RiskIntelligencePanel'

describe('RiskIntelligencePanel', () => {
  it('renders risk score and events', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          overall_risk_score: 66,
          risk_level: 'High',
          confidence: 0.8,
          risk_events: [{ risk_event_id: 'r1', event_type: 'cashflow_instability', severity: 'High', recommendation: 'Reduce spend', source_signals: ['x'] }],
          risk_signals: ['cashflow'],
          evidence_summary: 'Detected issues',
          recommendation_text: 'Take action',
        }),
      }),
    )

    render(<RiskIntelligencePanel accessToken="t" />)
    await waitFor(() => expect(screen.getByText('Risk Intelligence')).toBeInTheDocument())
    expect(screen.getByText(/66.0/)).toBeInTheDocument()
    expect(screen.getByText(/cashflow_instability/)).toBeInTheDocument()
  })
})
