import { Pie, PieChart, ResponsiveContainer, Tooltip, Cell } from 'recharts'
import { SectionCard, ProgressMetric, SectionEyebrow } from '../components/Cards'
import StatusBadge from '../components/ui/StatusBadge'

const donutColors = ['#2563eb', '#10b981', '#f59e0b', '#ef4444']

function gaugeTone(score = 0) {
  if (score >= 80) return 'good'
  if (score >= 60) return 'warning'
  return 'danger'
}

export default function Analytics({ analysis, financialScore, fraudCheck }) {
  const metrics = financialScore.metrics
  const flaggedTransactions = fraudCheck?.flagged_transactions || []
  const scoreValue = Number(financialScore?.score ?? 0)
  const scoreLabel = financialScore?.status || 'Unknown'
  const totalContribution = Object.values(financialScore.breakdown || {}).reduce((sum, value) => sum + Number(value || 0), 0) || 100
  const scoreRingData = [
    { name: 'Score', value: scoreValue },
    { name: 'Remaining', value: Math.max(0, 100 - scoreValue) },
  ]

  return (
    <div className="space-y-6">
      <SectionCard
        title="Scoring Intelligence"
        subtitle="The score is the hero, with contributions, penalties, confidence, and data quality shown as an executive-grade story."
        action={<StatusBadge label={scoreLabel} tone={gaugeTone(scoreValue)} />}
      >
        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-[30px] border border-slate-200/80 bg-slate-950 p-6 text-white shadow-[0_22px_50px_rgba(15,23,42,0.16)]">
            <SectionEyebrow>Score hero</SectionEyebrow>
            <div className="mt-6 grid place-items-center">
              <div className="relative h-64 w-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={scoreRingData} dataKey="value" innerRadius={90} outerRadius={112} startAngle={90} endAngle={-270} stroke="none">
                      <Cell fill="url(#scoreGradient)" />
                      <Cell fill="#334155" />
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-5xl font-semibold">{scoreValue}</p>
                    <p className="mt-1 text-xs font-semibold uppercase tracking-[0.22em] text-slate-300">{scoreLabel}</p>
                  </div>
                </div>
              </div>
            </div>
            <svg width="0" height="0" aria-hidden="true" focusable="false">
              <defs>
                <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#2563eb" />
                  <stop offset="50%" stopColor="#10b981" />
                  <stop offset="100%" stopColor="#f59e0b" />
                </linearGradient>
              </defs>
            </svg>
            <p className="mt-6 text-sm leading-7 text-slate-200">{financialScore.summary || 'The score combines deterministic signals with explainable contribution and penalty traces.'}</p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <ProgressMetric label="Savings ratio" value={metrics.savings_ratio * 100} max={100} tone="good" subtitle="Higher savings drive the score upward." />
            <ProgressMetric label="Stability score" value={financialScore.breakdown.stability_score} max={100} tone="info" subtitle="Cashflow steadiness and balance consistency." />
            <ProgressMetric label="Discipline score" value={financialScore.breakdown.discipline_score} max={100} tone="good" subtitle="Spending consistency and controllable behavior." />
            <ProgressMetric label="Risk score" value={financialScore.breakdown.risk_score} max={100} tone="danger" subtitle="Direct downside pressure on the score." />
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <SectionCard title="Contributions" subtitle="Positive drivers shown as upward bars in the waterfall-style breakdown.">
          <div className="space-y-3">
            {financialScore.explainability.contributions?.length ? (
              financialScore.explainability.contributions.map((item, idx) => (
                <div key={`${item.component}-${idx}`} className="rounded-[24px] border border-emerald-200/80 bg-emerald-50/70 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-emerald-900">{item.component}</p>
                    <StatusBadge label={`+${Number(item.weighted_points ?? 0).toFixed(1)}`} tone="good" />
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-emerald-100">
                    <div className="h-2 rounded-full bg-gradient-to-r from-emerald-500 to-cyan-400" style={{ width: `${Math.max(8, Math.min(100, Number(item.raw_score ?? 0)))}%` }} />
                  </div>
                  <p className="mt-2 text-sm text-emerald-900/80">{item.explanation || 'No explanation provided.'}</p>
                </div>
              ))
            ) : (
              <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 text-sm text-slate-500">No contribution trace available.</div>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Penalties" subtitle="Negative drivers visualized as a controlled reduction stack.">
          <div className="space-y-3">
            {financialScore.explainability.penalties?.length ? (
              financialScore.explainability.penalties.map((item, idx) => (
                <div key={`${item.penalty_type}-${idx}`} className="rounded-[24px] border border-rose-200/80 bg-rose-50/80 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-rose-900">{item.penalty_type}</p>
                    <StatusBadge label={`-${Number(item.points_deducted ?? 0).toFixed(1)}`} tone="danger" />
                  </div>
                  <p className="mt-2 text-sm text-rose-900/80">{item.reason || 'No reason provided.'}</p>
                </div>
              ))
            ) : (
              <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 text-sm text-slate-500">No penalty deductions recorded.</div>
            )}
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <SectionCard title="Data Quality" subtitle="Confidence and completeness indicators determine how much trust to place in the score.">
          <div className="grid gap-4 md:grid-cols-2">
            <ProgressMetric label="Confidence" value={financialScore.confidence.confidence_score * 100} max={100} tone="info" subtitle="Model certainty after data validation." />
            <ProgressMetric label="Data quality" value={financialScore.confidence.data_quality_score * 100} max={100} tone="good" subtitle="Freshness and completeness of transaction data." />
            <ProgressMetric label="Transaction ratio" value={financialScore.confidence.valid_transaction_ratio * 100} max={100} tone="warning" subtitle="Valid rows after parsing and normalization." />
            <ProgressMetric label="History depth" value={financialScore.confidence.history_depth} max={Math.max(Number(financialScore.confidence.history_depth ?? 0), 1)} tone="neutral" suffix="" subtitle="More history improves explainability." />
          </div>
          {Array.isArray(financialScore.confidence.limitations) && financialScore.confidence.limitations.length ? (
            <div className="mt-4 rounded-[24px] border border-amber-200/80 bg-amber-50 p-4 text-sm text-amber-900">
              <p className="font-semibold">Limitations</p>
              <ul className="mt-2 list-disc pl-5 leading-7">
                {financialScore.confidence.limitations.map((item, idx) => <li key={idx}>{item}</li>)}
              </ul>
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="Metric Snapshot" subtitle="The deterministic values the backend uses for explainable reasoning.">
          <div className="space-y-3">
            <div className="rounded-[24px] border border-slate-200/80 bg-slate-50/80 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Current month</p>
              <p className="mt-2 text-lg font-semibold text-slate-950">{analysis.insights.current_month || 'N/A'}</p>
            </div>
            <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><p className="text-slate-500">Income</p><p className="mt-1 font-semibold text-slate-950">Rs {metrics.income.toLocaleString('en-IN')}</p></div>
                <div><p className="text-slate-500">Expenses</p><p className="mt-1 font-semibold text-slate-950">Rs {metrics.expenses.toLocaleString('en-IN')}</p></div>
                <div><p className="text-slate-500">Volatility</p><p className="mt-1 font-semibold text-slate-950">Rs {metrics.expense_volatility.toLocaleString('en-IN')}</p></div>
                <div><p className="text-slate-500">Net trend</p><p className="mt-1 font-semibold text-slate-950">Rs {metrics.net_balance_trend.toLocaleString('en-IN')}</p></div>
              </div>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Fraud Review" subtitle="Anomaly detections that add a protective safety layer to the score story.">
        {flaggedTransactions.length ? (
          <div className="space-y-3">
            {flaggedTransactions.map((item) => (
              <div key={`${item.description}-${item.amount}`} className="rounded-[24px] border border-slate-200/80 bg-slate-50/90 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-950">{item.description}</p>
                    <p className="mt-1 text-sm text-slate-500">Rs {Number(item.amount).toLocaleString('en-IN')}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${item.risk === 'High' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'}`}>
                    {item.risk}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.flags.map((flag) => (
                    <StatusBadge key={flag} label={flag} tone="neutral" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-[24px] border border-emerald-200/80 bg-emerald-50 p-6 text-sm text-emerald-800">
            No suspicious transactions were detected in the current transaction history.
          </div>
        )}
      </SectionCard>
    </div>
  )
}
