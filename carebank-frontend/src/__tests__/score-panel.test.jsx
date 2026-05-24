import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ScoreExplainabilityPanel from '../components/ScoreExplainabilityPanel'

describe('ScoreExplainabilityPanel', () => {
  it('renders confidence contributions and penalties', () => {
    const score = {
      scoring_version: 'v1',
      confidence: { confidence_score: 0.8, data_quality_score: 0.7, limitations: ['limited history'] },
      explainability: {
        contributions: [{ component: 'savings_score', raw_score: 80, weight: 0.35, explanation: 'good' }],
        penalties: [{ penalty_type: 'high_risk', points_deducted: 10, reason: 'risk' }],
      },
    }
    render(<ScoreExplainabilityPanel score={score} />)
    expect(screen.getByText('Score Explainability')).toBeInTheDocument()
    expect(screen.getByText(/Confidence:/)).toBeInTheDocument()
    expect(screen.getByText(/high_risk/)).toBeInTheDocument()
  })
})
