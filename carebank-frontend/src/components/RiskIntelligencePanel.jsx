import { useCallback, useEffect, useState } from 'react'
import { fetchRiskAnalysis } from '../services/api'
import { SectionCard } from './Cards'
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

  if (state.loading) return <LoadingSkeleton lines={6} />
  if (state.error) return <ErrorCard title="Risk intelligence unavailable" message={state.error} onRetry={load} />
  if (!state.data) return <EmptyState title="No risk result" />

  const d = state.data
  const topEvents = (d.risk_events || []).slice(0, 5)

  return (
    <SectionCard title="Risk Intelligence" subtitle="Deterministic risk events and recommendations">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">Overall risk score</p><p className="text-2xl font-bold">{Number(d.overall_risk_score ?? 0).toFixed(1)}</p></div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">Risk level</p><StatusBadge label={d.risk_level || 'Low'} tone={tone(d.risk_level)} /></div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">Confidence</p><p className="font-semibold">{Number(d.confidence ?? 0).toFixed(2)}</p></div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 p-3">
        <p className="font-semibold text-slate-900">Top risk events</p>
        {topEvents.length ? topEvents.map((event) => (
          <div key={event.risk_event_id || event.event_type} className="mt-2 rounded-lg bg-slate-50 p-3 text-sm">
            <p className="font-medium">{event.event_type || event.risk_type} <StatusBadge label={event.severity || 'Low'} tone={tone(event.severity)} /></p>
            <p className="text-slate-700">{event.recommendation || 'No recommendation provided.'}</p>
            {Array.isArray(event.source_signals) && event.source_signals.length ? <p className="mt-1 text-xs text-slate-500">Signals: {event.source_signals.join(', ')}</p> : null}
          </div>
        )) : <p className="mt-2 text-sm text-slate-600">No risk events available.</p>}
      </div>

      {Array.isArray(d.risk_signals) && d.risk_signals.length ? (
        <div className="mt-3 rounded-xl border border-slate-200 p-3 text-sm">
          <p className="font-semibold text-slate-900">Risk signals</p>
          <p className="mt-1 text-slate-700">{d.risk_signals.join(', ')}</p>
        </div>
      ) : null}

      <div className="mt-3 rounded-xl border border-slate-200 p-3 text-sm">
        <p className="font-semibold text-slate-900">Evidence summary</p>
        <p className="mt-1 text-slate-700">{d.evidence_summary || 'No evidence summary available.'}</p>
      </div>

      <div className="mt-3 rounded-xl border border-cyan-200 bg-cyan-50 p-3 text-sm text-cyan-900">
        <p className="font-semibold">Recommendation</p>
        <p className="mt-1">{d.recommendation_text || 'No recommendation provided.'}</p>
      </div>
    </SectionCard>
  )
}
