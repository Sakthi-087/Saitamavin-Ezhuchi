import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

import Chat from '../components/Chat'

describe('Chat floating copilot', () => {
  it('renders metadata in Why this answer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          answer: 'Grounded response',
          copilot: {
            intent: 'risk_explanation',
            confidence: 0.82,
            evidence_keys: ['risk_intelligence'],
            limitations: ['Based on uploaded data only'],
            safety_status: 'grounded',
            fallback_used: false,
          },
        }),
      }),
    )

    render(<Chat accessToken="t" />)
    fireEvent.click(screen.getByLabelText('Open Copilot'))
    fireEvent.change(screen.getByPlaceholderText('Why did I spend more this month?'), { target: { value: 'Explain risk' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByText('Grounded response')).toBeInTheDocument())
    const metaToggle = screen.getByRole('button', { name: 'Why this answer?' })
    fireEvent.click(metaToggle)
    const metadata = metaToggle.nextElementSibling
    expect(metadata).not.toBeNull()
    expect(within(metadata).getByText(/risk_explanation/)).toBeInTheDocument()
  })
})
