import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import RealtimeAlertCenter from '../components/RealtimeAlertCenter'

describe('RealtimeAlertCenter', () => {
  it('renders severity title and dismiss', () => {
    const onDismiss = vi.fn()
    render(
      <RealtimeAlertCenter
        connectionStatus="connected"
        liveEvents={[{ eventId: 'e1', severity: 'High', title: 'Risk Alert', message: 'Take action', createdAt: new Date().toISOString() }]}
        onDismiss={onDismiss}
      />,
    )
    expect(screen.getByText('Risk Alert')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(onDismiss).toHaveBeenCalledWith('e1')
  })
})
