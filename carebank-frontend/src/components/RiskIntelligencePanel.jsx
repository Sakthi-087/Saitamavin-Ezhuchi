import { useCallback, useEffect, useMemo, useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { fetchRiskAnalysis } from '../services/api'
import { SectionCard, TimelineDot, SectionEyebrow } from './Cards'
import LoadingSkeleton from './ui/LoadingSkeleton'
import ErrorCard from './ui/ErrorCard'
import EmptyState from './ui/EmptyState'
import StatusBadge from './ui/StatusBadge'

function tone(level = '') {
  const l = String(level).toLowerCase()
  if (l.includes('critical') || l.includes('high')) return 'danger'
  if (l.includes('moderate') || l.includes('medium')) return 'warning'
  return 'good'
}

function gaugeTone(score) {
  if (score >= 75) return 'danger'
  if (score >= 50) return 'warning'
  return 'good'
}

function formatPercent(value) {
  return `${Number(value ?? 0).toFixed(2)}`
}

export default function RiskIntelligencePanel({ accessToken }) {
  const [state, setState] = useState({ loading: true, error: '', data: null })

  const load = useCallback(async () => {
    setState({ loading: true, error: '', data: null })
    try {
      const data = await fetchRiskAnalysis(accessToken)
      setState({ loading: false, error: '', data })
    } catch (error) {
      setState({ loading: false, error: error.message || 'Unable to load risk intelligence.', data: null })
    }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    load()
  }, [accessToken, load])

  const checklist = useMemo(() => {
    const d = state.data || {}
    return [
      d.recommendation_text,
      ...(Array.isArray(d.risk_signals) ? d.risk_signals.slice(0, 4) : []),
    ].filter(Boolean)
  }, [state.data])

  if (state.loading) return <LoadingSkeleton lines={8} />
  if (state.error) return <ErrorCard title="Risk intelligence unavailable" message={state.error} onRetry={load} />
  if (!state.data) return <EmptyState title="No risk result" />

  const d = state.data
  const riskScore = Number(d.overall_risk_score ?? 0)
  const scoreData = [
    { name: 'Risk', value: riskScore },
    { name: 'Remaining', value: Math.max(0, 100 - riskScore) },
  ]
  const topEvents = (d.risk_events || []).slice(0, 5)

  return (
    <div className="space-y-6">
      <SectionCard
        title="Risk Intelligence"
        subtitle="Executive risk dashboard showing score, evidence, recommendations, and action readiness."
        action={<StatusBadge label={d.risk_level || 'Low'} tone={gaugeTone(riskScore)} />}
      >
        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr_0.9fr]">
          <div className="rounded-[30px] border border-slate-200/80 bg-slate-950 p-6 text-white shadow-[0_20px_45px_rgba(15,23,42,0.16)]">
            <SectionEyebrow>Overall risk score</SectionEyebrow>
            <div className="mt-6 grid place-items-center">
              <div className="relative h-64 w-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={scoreData} dataKey="value" innerRadius={88} outerRadius={112} startAngle={90} endAngle={-270} stroke="none">
                      <Cell fill="url(#riskGradient)" />
                      <Cell fill="#334155" />
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-5xl font-semibold">{riskScore.toFixed(1)}</p>
                    <p className="mt-1 text-xs font-semibold uppercase tracking-[0.24em] text-slate-300">{d.risk_level || 'LOW RISK'}</p>
                  </div>
                </div>
              </div>
            </div>
            <svg width="0" height="0" aria-hidden="true" focusable="false">
              <defs>
                <linearGradient id="riskGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#10b981" />
                  <stop offset="55%" stopColor="#f59e0b" />
                  <stop offset="100%" stopColor="#ef4444" />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Risk level</p>
                <p className="mt-3 text-2xl font-semibold text-slate-950">{d.risk_level || 'Low'}</p>
              </div>
              <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Confidence</p>
                <p className="mt-3 text-2xl font-semibold text-slate-950">{formatPercent(d.confidence)}</p>
              </div>
              <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
                <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Evidence</p>
                <p className="mt-3 text-2xl font-semibold text-slate-950">{Array.isArray(d.risk_signals) ? d.risk_signals.length : 0}</p>
              </div>
            </div>

            <div className="rounded-[28px] border border-slate-200/80 bg-slate-50/80 p-5">
              <p className="text-sm font-semibold text-slate-950">Risk signals</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {Array.isArray(d.risk_signals) && d.risk_signals.length ? (
                  d.risk_signals.map((signal) => <StatusBadge key={signal} label={signal} tone="info" />)
                ) : (
                  <span className="text-sm text-slate-500">No standalone risk signals were returned.</span>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold text-slate-950">Recommendations</p>
            <div className="mt-4 space-y-3">
              {(checklist.length ? checklist : ['No recommendation provided.']).slice(0, 5).map((item, index) => (
                <div key={`${item}-${index}`} className="flex gap-3 rounded-[20px] border border-slate-200/80 bg-slate-50 p-3">
                  <TimelineDot tone={index === 0 ? 'danger' : index === 1 ? 'warning' : 'info'} />
                  <p className="text-sm leading-6 text-slate-700">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <SectionCard title="Risk Signals" subtitle="Evidence-backed signals that triggered the current risk posture.">
          {topEvents.length ? (
            <div className="space-y-3">
              {topEvents.map((event) => (
                <div key={event.risk_event_id || event.event_type} className="rounded-[24px] border border-slate-200/80 bg-slate-50/80 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-950">{event.event_type || event.risk_type}</p>
                      <p className="mt-1 text-sm text-slate-500">{event.recommendation || 'No recommendation provided.'}</p>
                    </div>
                    <StatusBadge label={event.severity || 'Low'} tone={tone(event.severity)} />
                  </div>
                  {Array.isArray(event.source_signals) && event.source_signals.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {event.source_signals.map((signal) => (
                        <StatusBadge key={signal} label={signal} tone="neutral" />
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No risk events available" description="New signals will appear here as they are generated by the backend." />
          )}
        </SectionCard>

        <SectionCard title="Evidence & Summary" subtitle="What the model used to justify the current risk assessment.">
          <div className="space-y-4">
            <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Evidence summary</p>
              <p className="mt-3 text-sm leading-7 text-slate-700">{d.evidence_summary || 'No evidence summary available.'}</p>
            </div>
            <div className="rounded-[24px] border border-blue-200/80 bg-blue-50 p-4 text-blue-900 shadow-sm">
              <p className="text-xs uppercase tracking-[0.22em] text-blue-700">Recommendation</p>
              <p className="mt-3 text-sm leading-7">{d.recommendation_text || 'No recommendation provided.'}</p>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
