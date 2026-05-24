import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import HistoryTimeline from '../components/HistoryTimeline'

describe('HistoryTimeline', () => {
  it('renders empty state', () => {
    render(<HistoryTimeline items={[]} type="score" />)
    expect(screen.getByText('No history available')).toBeInTheDocument()
  })

  it('renders list state', () => {
    render(<HistoryTimeline items={[{ id: '1', created_at: new Date().toISOString(), score: 80, status: 'Good' }]} type="score" />)
    expect(screen.getByText(/Score 80/)).toBeInTheDocument()
  })
})
