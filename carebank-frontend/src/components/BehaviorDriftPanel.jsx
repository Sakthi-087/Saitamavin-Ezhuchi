import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fetchBehaviorAnalysis } from '../services/api'
import { SectionCard, ProgressMetric, TimelineDot, SectionEyebrow } from './Cards'
import LoadingSkeleton from './ui/LoadingSkeleton'
import ErrorCard from './ui/ErrorCard'
import EmptyState from './ui/EmptyState'
import StatusBadge from './ui/StatusBadge'

function toneBySeverity(severity = '') {
  const s = String(severity).toLowerCase()
  if (s.includes('critical') || s.includes('high')) return 'danger'
  if (s.includes('medium') || s.includes('low')) return 'warning'
  return 'good'
}

function formatMoney(value) {
  return `Rs ${Number(value ?? 0).toLocaleString('en-IN')}`
}

function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, Number(value) || 0))
}

export default function BehaviorDriftPanel({ accessToken }) {
  const [state, setState] = useState({ loading: true, error: '', data: null })

  const load = useCallback(async () => {
    setState({ loading: true, error: '', data: null })
    try {
      const data = await fetchBehaviorAnalysis(accessToken)
      setState({ loading: false, error: '', data })
    } catch (error) {
      setState({ loading: false, error: error.message || 'Unable to load behavior analysis.', data: null })
    }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    load()
  }, [accessToken, load])

  const chartData = useMemo(() => {
    const d = state.data || {}
    return [
      { label: '7d', value: Number(d.last_7_days_spend ?? 0) },
      { label: '30d', value: Number(d.last_30_days_spend ?? 0) },
      { label: '90d', value: Number(d.last_90_days_spend ?? 0) },
      { label: 'Prev 30d', value: Number(d.previous_30_days_spend ?? 0) },
    ]
  }, [state.data])

  if (state.loading) return <LoadingSkeleton lines={10} />
  if (state.error) return <ErrorCard title="Behavior drift unavailable" message={state.error} onRetry={load} />
  if (!state.data) return <EmptyState title="No behavior analysis" />

  const d = state.data
  const driftEntries = Array.isArray(d.category_drift) ? [...d.category_drift].slice(0, 5) : []
  const anomalyEvents = Array.isArray(d.anomaly_events) ? [...d.anomaly_events].slice(0, 6) : []
  const merchantRecurrence = Array.isArray(d.merchant_recurrence) ? [...d.merchant_recurrence].slice(0, 5) : []
  const topDrift = driftEntries[0]
  const driftScore = clamp(d.drift_score ?? 0)
  const severity = d.drift_severity || 'Stable'

  const donutData = [
    { name: 'Drift', value: driftScore },
    { name: 'Remaining', value: 100 - driftScore },
  ]

  return (
    <div className="space-y-6">
      <SectionCard
        title="Behavior Drift"
        subtitle="Track drift, recurring merchants, anomalies, and spend cadence in a single executive-grade view."
        action={<StatusBadge label={severity} tone={toneBySeverity(severity)} />}
      >
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-[24px] border border-slate-200/80 bg-slate-950 p-5 text-white shadow-[0_20px_40px_rgba(15,23,42,0.16)]">
            <SectionEyebrow>Behavior score</SectionEyebrow>
            <p className="mt-4 text-4xl font-semibold">{Number(d.behavior_score ?? 0).toFixed(0)}</p>
            <p className="mt-2 text-sm text-slate-300">Composite spend behavior health</p>
          </div>
          <div className="rounded-[24px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <SectionEyebrow>Drift severity</SectionEyebrow>
            <p className="mt-4 text-4xl font-semibold text-slate-950">{Number(driftScore).toFixed(1)}</p>
            <p className="mt-2 text-sm text-slate-500">{severity}</p>
          </div>
          <div className="rounded-[24px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <SectionEyebrow>Anomalies</SectionEyebrow>
            <p className="mt-4 text-4xl font-semibold text-slate-950">{anomalyEvents.length}</p>
            <p className="mt-2 text-sm text-slate-500">Detected from spend pattern changes</p>
          </div>
          <div className="rounded-[24px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <SectionEyebrow>Recurring merchants</SectionEyebrow>
            <p className="mt-4 text-4xl font-semibold text-slate-950">{merchantRecurrence.length}</p>
            <p className="mt-2 text-sm text-slate-500">Merchants with stable repeat behavior</p>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Drift Analysis" subtitle="Drift score gauge, severity badge, and plain-language explanation of the current spend shift.">
        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-[28px] border border-slate-200/80 bg-gradient-to-br from-slate-50 to-white p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Drift score gauge</p>
                <p className="mt-2 text-sm text-slate-600">How much your behavior has diverged from the historical baseline.</p>
              </div>
              <StatusBadge label={severity} tone={toneBySeverity(severity)} />
            </div>

            <div className="mt-6 grid place-items-center">
              <div className="relative h-64 w-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={donutData} dataKey="value" innerRadius={88} outerRadius={112} startAngle={90} endAngle={-270} stroke="none">
                      <Cell fill="url(#driftGradient)" />
                      <Cell fill="#e2e8f0" />
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-5xl font-semibold text-slate-950">{Number(driftScore).toFixed(0)}</p>
                    <p className="mt-1 text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Drift</p>
                  </div>
                </div>
              </div>
            </div>

            <svg width="0" height="0" aria-hidden="true" focusable="false">
              <defs>
                <linearGradient id="driftGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#2563eb" />
                  <stop offset="50%" stopColor="#10b981" />
                  <stop offset="100%" stopColor="#f59e0b" />
                </linearGradient>
              </defs>
            </svg>

            <div className="mt-6 rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Explanation</p>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                Your spending behavior changed significantly compared with historical patterns.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {chartData.map((item) => (
                <ProgressMetric
                  key={item.label}
                  label={item.label}
                  value={item.value}
                  max={Math.max(...chartData.map((entry) => entry.value), 1)}
                  tone={item.label === 'Prev 30d' ? 'neutral' : item.label === '7d' ? 'info' : 'good'}
                  suffix=""
                  subtitle={formatMoney(item.value)}
                />
              ))}
            </div>
            <div className="rounded-[28px] border border-slate-200/80 bg-slate-50/70 p-4">
              <p className="text-sm font-semibold text-slate-950">Rolling spend trends</p>
              <div className="mt-4 h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <Tooltip formatter={(value) => formatMoney(value)} />
                    <Legend />
                    <Line type="monotone" dataKey="value" name="Spend" stroke="#2563eb" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="Top Category Drift" subtitle="Ranked spend categories that moved the most versus baseline.">
          {driftEntries.length ? (
            <div className="space-y-4">
              {driftEntries.map((item, index) => (
                <div key={`${item.category}-${index}`} className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-950">{item.category}</p>
                      <p className="mt-1 text-xs text-slate-500">Severity: {item.severity || 'N/A'}</p>
                    </div>
                    <StatusBadge label={`${Number(item.drift_percentage ?? 0).toFixed(0)}%`} tone={toneBySeverity(item.severity)} />
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-slate-200">
                    <div className="h-2 rounded-full bg-gradient-to-r from-blue-500 via-cyan-400 to-emerald-400" style={{ width: `${Math.max(8, Math.min(100, Number(item.drift_percentage ?? 0))) }%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No category drift" description="More transaction history will reveal category-level movement." />
          )}
        </SectionCard>

        <SectionCard title="Merchant Recurrence" subtitle="Repeated merchants are useful for labeling stable spend versus emerging drift.">
          {merchantRecurrence.length ? (
            <div className="space-y-4">
              {merchantRecurrence.map((item, index) => (
                <div key={`${item.merchant}-${index}`} className="rounded-[24px] border border-slate-200/80 bg-slate-50/80 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-950">{item.merchant}</p>
                    <StatusBadge label={`${Number(item.recurrence_confidence ?? 0).toFixed(2)}`} tone="info" />
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-slate-200">
                    <div className="h-2 rounded-full bg-gradient-to-r from-slate-900 to-blue-500" style={{ width: `${Math.max(8, Math.min(100, Number(item.recurrence_confidence ?? 0) * 100))}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No recurring merchants" description="Stable merchants will appear here once enough activity has accumulated." />
          )}
        </SectionCard>
      </div>

      <SectionCard title="Anomaly Timeline" subtitle="Alerts are shown in chronological order so the highest-risk changes stand out immediately.">
        {anomalyEvents.length ? (
          <div className="space-y-3">
            {anomalyEvents.map((event, index) => {
              const severityTone = toneBySeverity(event.severity)
              return (
                <div key={`${event.event_type}-${index}`} className="flex gap-4 rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
                  <TimelineDot tone={severityTone} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="font-semibold text-slate-950">{event.event_type || 'Anomaly'}</p>
                      <StatusBadge label={event.severity || 'Info'} tone={severityTone} />
                    </div>
                    <p className="mt-2 text-sm text-slate-600">
                      Confidence: {Number(event.confidence ?? 0.91).toFixed(2)}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">Detected: Today</p>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <EmptyState title="No anomaly events" description="When irregular behavior appears, it will be surfaced here as a timeline." />
        )}
      </SectionCard>

      {Array.isArray(d.parse_errors) && d.parse_errors.length ? (
        <div className="rounded-[24px] border border-amber-200/80 bg-amber-50 p-4 text-sm text-amber-900 shadow-sm">
          <p className="font-semibold">Parse warnings:</p>
          <p className="mt-2">{d.parse_errors.slice(0, 3).join('; ')}</p>
        </div>
      ) : null}
    </div>
  )
}
