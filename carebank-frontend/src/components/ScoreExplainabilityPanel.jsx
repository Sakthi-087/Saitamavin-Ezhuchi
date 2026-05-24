import { useState } from 'react'
import { SectionCard } from './Cards'
import EmptyState from './ui/EmptyState'

function pct(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '--'
  return `${(n * 100).toFixed(0)}%`
}

export default function ScoreExplainabilityPanel({ score }) {
  const [showFormula, setShowFormula] = useState(false)

  if (!score) {
    return <EmptyState title="No scoring data" description="Financial score data is unavailable." />
  }

  const confidence = score.confidence || {}
  const explainability = score.explainability || {}
  const contributions = explainability.contributions || []
  const penalties = explainability.penalties || []

  return (
    <SectionCard title="Score Explainability" subtitle="Why this score, what reduced it, and confidence quality">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">Scoring version</p>
          <p className="mt-2 font-semibold text-slate-900">{score.scoring_version || 'N/A'}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">How reliable is this score?</p>
          <p className="mt-2 font-semibold text-slate-900">Confidence: {pct(confidence.confidence_score)}</p>
          <p className="text-sm text-slate-600">Data quality: {pct(confidence.data_quality_score)}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">What reduced the score?</p>
          <p className="mt-2 font-semibold text-slate-900">{penalties.length} penalties</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 p-4">
          <p className="font-semibold text-slate-900">Why this score?</p>
          {contributions.length ? contributions.map((item, idx) => (
            <div key={`${item.component}-${idx}`} className="mt-3 rounded-xl bg-slate-50 p-3 text-sm">
              <p className="font-medium text-slate-900">{item.component}: {Number(item.raw_score ?? 0).toFixed(1)} (weight {item.weight})</p>
              <p className="text-slate-600">{item.explanation || 'No explanation provided.'}</p>
            </div>
          )) : <p className="mt-2 text-sm text-slate-600">No contribution trace available.</p>}
        </div>

        <div className="rounded-2xl border border-slate-200 p-4">
          <p className="font-semibold text-slate-900">What reduced the score?</p>
          {penalties.length ? penalties.map((item, idx) => (
            <div key={`${item.penalty_type}-${idx}`} className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-800">
              <p className="font-medium">-{Number(item.points_deducted ?? 0).toFixed(1)}: {item.penalty_type}</p>
              <p>{item.reason || 'No reason provided.'}</p>
            </div>
          )) : <p className="mt-2 text-sm text-slate-600">No penalty deductions recorded.</p>}
        </div>
      </div>

      {Array.isArray(confidence.limitations) && confidence.limitations.length ? (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">Limitations</p>
          <ul className="mt-2 list-disc pl-5">
            {confidence.limitations.map((item, idx) => <li key={idx}>{item}</li>)}
          </ul>
        </div>
      ) : null}

      {explainability.final_score_formula ? (
        <div className="mt-4">
          <button type="button" onClick={() => setShowFormula((v) => !v)} className="text-sm font-semibold text-blue-700 hover:text-blue-900">
            {showFormula ? 'Hide' : 'Show'} final score formula
          </button>
          {showFormula ? <pre className="mt-2 overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">{explainability.final_score_formula}</pre> : null}
        </div>
      ) : null}
    </SectionCard>
  )
}
