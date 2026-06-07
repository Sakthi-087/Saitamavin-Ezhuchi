import { useMemo, useState } from 'react'
import { SectionCard, ProgressMetric, SectionEyebrow } from './Cards'
import EmptyState from './ui/EmptyState'
import StatusBadge from './ui/StatusBadge'

function pct(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '--'
  return `${(n * 100).toFixed(0)}%`
}

function scoreTone(score = 0) {
  if (score >= 80) return 'good'
  if (score >= 60) return 'warning'
  return 'danger'
}

export default function ScoreExplainabilityPanel({ score }) {
  const [showFormula, setShowFormula] = useState(false)

  if (!score) {
    return <EmptyState title="No scoring data" description="Financial score data is unavailable." />
  }

  const scoreValue = Number(score.score ?? 0)
  const confidence = score.confidence || {}
  const explainability = score.explainability || {}
  const contributions = explainability.contributions || []
  const penalties = explainability.penalties || []

  const progressBars = useMemo(() => {
    const positive = contributions.filter((item) => Number(item.weighted_points ?? 0) >= 0)
    const negative = penalties.map((item) => ({
      label: item.penalty_type,
      value: Number(item.points_deducted ?? 0),
      description: item.reason || 'Penalty applied to the score.',
    }))
    return { positive, negative }
  }, [contributions, penalties])

  return (
    <SectionCard
      title="Score Explainability"
      subtitle="Executive view of the score hero, contributions, penalties, confidence, and data quality."
      action={<StatusBadge label={score.status || 'Unknown'} tone={scoreTone(scoreValue)} />}
    >
      <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <div className="rounded-[30px] border border-slate-200/80 bg-slate-950 p-6 text-white shadow-[0_20px_45px_rgba(15,23,42,0.16)]">
          <SectionEyebrow>Score hero</SectionEyebrow>
          <p className="mt-4 text-6xl font-semibold tracking-tight">{scoreValue}</p>
          <p className="mt-3 text-sm uppercase tracking-[0.22em] text-cyan-200">{score.status || 'Unknown'}</p>
          <p className="mt-4 text-sm leading-7 text-slate-200">{score.summary || 'The score is a weighted summary of savings, stability, discipline, and risk.'}</p>
          <div className="mt-6 grid gap-3">
            <div className="rounded-[20px] border border-white/10 bg-white/5 px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-300">Confidence</p>
              <p className="mt-1 text-lg font-semibold">Confidence: {pct(confidence.confidence_score)}</p>
            </div>
            <div className="rounded-[20px] border border-white/10 bg-white/5 px-4 py-3">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-300">Data quality</p>
              <p className="mt-1 text-lg font-semibold">Data quality: {pct(confidence.data_quality_score)}</p>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <ProgressMetric label="Savings ratio" value={score.metrics?.savings_ratio ? score.metrics.savings_ratio * 100 : 0} max={100} tone="good" subtitle="Higher savings create more score upside." />
            <ProgressMetric label="Expense ratio" value={score.metrics?.expense_ratio ? score.metrics.expense_ratio * 100 : 0} max={100} tone="warning" subtitle="A higher ratio pushes the score down." />
            <ProgressMetric label="Valid transaction ratio" value={confidence.valid_transaction_ratio ? confidence.valid_transaction_ratio * 100 : 0} max={100} tone="info" subtitle="Better data quality improves reliability." />
            <ProgressMetric label="History depth" value={confidence.history_depth ?? 0} max={Math.max(Number(confidence.history_depth ?? 0), 1)} tone="neutral" suffix="" subtitle="More context increases confidence." />
          </div>

          <div className="rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold text-slate-950">Contributions</p>
            <div className="mt-4 space-y-3">
              {progressBars.positive.length ? (
                progressBars.positive.map((item, idx) => (
                  <div key={`${item.component}-${idx}`} className="rounded-[22px] border border-emerald-200/80 bg-emerald-50/70 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-emerald-900">{item.component}</p>
                      <StatusBadge label={`+${Number(item.weighted_points ?? 0).toFixed(1)}`} tone="good" />
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-emerald-100">
                      <div className="h-2 rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400" style={{ width: `${Math.max(8, Math.min(100, Number(item.raw_score ?? 0)))}%` }} />
                    </div>
                    <p className="mt-2 text-sm text-emerald-900/80">{item.explanation || 'No explanation provided.'}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">No contribution trace available.</p>
              )}
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold text-slate-950">Penalties</p>
            <div className="mt-4 space-y-3">
              {penalties.length ? (
                penalties.map((item, idx) => (
                  <div key={`${item.penalty_type}-${idx}`} className="rounded-[22px] border border-rose-200/80 bg-rose-50/80 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-rose-900">{item.penalty_type}</p>
                      <StatusBadge label={`-${Number(item.points_deducted ?? 0).toFixed(1)}`} tone="danger" />
                    </div>
                    <p className="mt-2 text-sm text-rose-900/80">{item.reason || 'No reason provided.'}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">No penalty deductions recorded.</p>
              )}
            </div>
          </div>

          {Array.isArray(confidence.limitations) && confidence.limitations.length ? (
            <div className="rounded-[28px] border border-amber-200/80 bg-amber-50 p-4 text-sm text-amber-900 shadow-sm">
              <p className="font-semibold">Limitations</p>
              <ul className="mt-2 list-disc pl-5 leading-7">
                {confidence.limitations.map((item, idx) => <li key={idx}>{item}</li>)}
              </ul>
            </div>
          ) : null}

          {explainability.final_score_formula ? (
            <div>
              <button type="button" onClick={() => setShowFormula((v) => !v)} className="text-sm font-semibold text-blue-700 hover:text-blue-900">
                {showFormula ? 'Hide' : 'Show'} final score formula
              </button>
              {showFormula ? <pre className="mt-3 overflow-x-auto rounded-[24px] bg-slate-950 p-4 text-xs text-slate-100 shadow-sm">{explainability.final_score_formula}</pre> : null}
            </div>
          ) : null}
        </div>
      </div>
    </SectionCard>
  )
}
