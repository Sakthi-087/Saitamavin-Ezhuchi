import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import BehaviorDriftPanel from '../components/BehaviorDriftPanel'

const behaviorPayload = {
  drift_score: 72,
  drift_severity: 'High',
  last_7_days_spend: 1000,
  last_30_days_spend: 3000,
  last_90_days_spend: 9000,
  previous_30_days_spend: 2500,
  spend_velocity_7d_vs_30d: 0.9,
  month_over_month_change: 12,
  category_drift: [{ category: 'Food', drift_percentage: 60, severity: 'High' }],
  anomaly_events: [{ event_type: 'spending_velocity_spike', severity: 'High' }],
  merchant_recurrence: [{ merchant: 'NETFLIX', recurrence_confidence: 0.8 }],
  parse_errors: ['bad row'],
}

describe('BehaviorDriftPanel', () => {
  it('renders drift and anomaly fields', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue(behaviorPayload),
      }),
    )

    render(<BehaviorDriftPanel accessToken="t" />)

    await waitFor(() => expect(screen.getByText('Behavior Drift')).toBeInTheDocument())
    expect(screen.getByText(/72.0/)).toBeInTheDocument()
    expect(screen.getByText(/spending_velocity_spike/i)).toBeInTheDocument()
    expect(screen.getByText(/Parse warnings:/i)).toBeInTheDocument()
  })
})
