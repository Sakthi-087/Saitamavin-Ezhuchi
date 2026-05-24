import { useCallback, useEffect, useState } from 'react'
import { fetchBehaviorAnalysis } from '../services/api'
import { SectionCard } from './Cards'
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

  if (state.loading) return <LoadingSkeleton lines={6} />
  if (state.error) return <ErrorCard title="Behavior drift unavailable" message={state.error} onRetry={load} />
  if (!state.data) return <EmptyState title="No behavior analysis" />

  const d = state.data
  const driftEntries = Array.isArray(d.category_drift) ? d.category_drift.slice(0, 3) : []

  return (
    <SectionCard title="Behavior Drift" subtitle="Recent spending pattern shifts and anomalies">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">Drift score</p><p className="text-xl font-bold">{Number(d.drift_score ?? 0).toFixed(1)}</p></div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">Drift severity</p><StatusBadge label={d.drift_severity || 'Stable'} tone={toneBySeverity(d.drift_severity)} /></div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">7d spend</p><p className="text-xl font-bold">Rs {Number(d.last_7_days_spend ?? 0).toLocaleString('en-IN')}</p></div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">30d spend</p><p className="text-xl font-bold">Rs {Number(d.last_30_days_spend ?? 0).toLocaleString('en-IN')}</p></div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 p-3 text-sm"><p className="text-slate-500">90d spend</p><p className="font-semibold">Rs {Number(d.last_90_days_spend ?? 0).toLocaleString('en-IN')}</p></div>
        <div className="rounded-xl border border-slate-200 p-3 text-sm"><p className="text-slate-500">Previous 30d spend</p><p className="font-semibold">Rs {Number(d.previous_30_days_spend ?? 0).toLocaleString('en-IN')}</p></div>
        <div className="rounded-xl border border-slate-200 p-3 text-sm"><p className="text-slate-500">Spend velocity 7d vs 30d</p><p className="font-semibold">{Number(d.spend_velocity_7d_vs_30d ?? 0).toFixed(2)}</p></div>
      </div>

      <div className="mt-3 rounded-xl border border-slate-200 p-3 text-sm">
        <p className="text-slate-500">Month over month change</p>
        <p className="font-semibold">{Number(d.month_over_month_change ?? 0).toFixed(2)}%</p>
      </div>

      {driftEntries.length ? (
        <div className="mt-4 rounded-xl border border-slate-200 p-3">
          <p className="font-semibold text-slate-900">Top category drift</p>
          {driftEntries.map((item, idx) => (
            <p key={idx} className="mt-2 text-sm text-slate-700">{item.category}: {Number(item.drift_percentage ?? 0).toFixed(2)}% ({item.severity})</p>
          ))}
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 p-3">
          <p className="font-semibold text-slate-900">Anomaly events</p>
          {(d.anomaly_events || []).slice(0, 4).map((event, idx) => (
            <p key={idx} className="mt-2 text-sm text-slate-700">{event.event_type} - {event.severity}</p>
          ))}
          {!d.anomaly_events?.length ? <p className="mt-2 text-sm text-slate-600">No anomaly events.</p> : null}
        </div>

        <div className="rounded-xl border border-slate-200 p-3">
          <p className="font-semibold text-slate-900">Merchant recurrence</p>
          {(d.merchant_recurrence || []).slice(0, 4).map((item, idx) => (
            <p key={idx} className="mt-2 text-sm text-slate-700">{item.merchant} (confidence {Number(item.recurrence_confidence ?? 0).toFixed(2)})</p>
          ))}
          {!d.merchant_recurrence?.length ? <p className="mt-2 text-sm text-slate-600">No recurring merchants detected.</p> : null}
        </div>
      </div>

      {Array.isArray(d.parse_errors) && d.parse_errors.length ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Parse warnings: {d.parse_errors.slice(0, 3).join('; ')}
        </div>
      ) : null}
    </SectionCard>
  )
}
