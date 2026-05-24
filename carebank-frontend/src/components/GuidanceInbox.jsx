import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchGuidance } from '../services/api'
import { SectionCard } from './Cards'
import LoadingSkeleton from './ui/LoadingSkeleton'
import ErrorCard from './ui/ErrorCard'
import EmptyState from './ui/EmptyState'
import StatusBadge from './ui/StatusBadge'

const PRIORITY_WEIGHT = {
  Critical: 5,
  High: 4,
  Medium: 3,
  Low: 2,
  Positive: 1,
}

function tone(priority = '') {
  if (priority === 'Critical' || priority === 'High') return 'danger'
  if (priority === 'Medium') return 'warning'
  if (priority === 'Positive') return 'good'
  return 'neutral'
}

export default function GuidanceInbox({ accessToken }) {
  const [state, setState] = useState({ loading: true, error: '', data: null })

  const load = useCallback(async () => {
    setState({ loading: true, error: '', data: null })
    try {
      const data = await fetchGuidance(accessToken)
      setState({ loading: false, error: '', data })
    } catch (error) {
      setState({ loading: false, error: error.message || 'Unable to load guidance.', data: null })
    }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    load()
  }, [accessToken, load])

  const items = useMemo(() => {
    const list = state.data?.items || state.data?.guidance_items || []
    return [...list].sort((a, b) => (PRIORITY_WEIGHT[b.priority] || 0) - (PRIORITY_WEIGHT[a.priority] || 0))
  }, [state.data])

  if (state.loading) return <LoadingSkeleton lines={6} />
  if (state.error) return <ErrorCard title="Guidance unavailable" message={state.error} onRetry={load} />
  if (!state.data || !items.length) return <EmptyState title="No guidance items" description="Guidance will appear as risk and behavior signals are generated." />

  return (
    <SectionCard title="Guidance Inbox" subtitle="Prioritized actions to improve financial outcomes">
      <div className="space-y-3">
        {items.slice(0, 8).map((item, idx) => (
          <div key={item.guidance_id || `${item.title}-${idx}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge label={item.priority || 'Low'} tone={tone(item.priority)} />
              <p className="font-semibold text-slate-900">{item.title || item.guidance_type}</p>
            </div>
            <p className="mt-2 text-sm text-slate-700">{item.rationale || 'No rationale provided.'}</p>
            <p className="mt-2 text-xs text-slate-600">Confidence {Number(item.confidence ?? 0).toFixed(2)} | Actionability {Number(item.actionability_score ?? 0).toFixed(2)} | TTL {item.ttl_days ?? 'N/A'} days</p>
            {item.expected_impact ? <p className="mt-2 text-sm text-cyan-900">Impact: {item.expected_impact}</p> : null}
            {Array.isArray(item.action_steps) && item.action_steps.length ? (
              <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
                {item.action_steps.slice(0, 4).map((step, stepIdx) => <li key={stepIdx}>{step}</li>)}
              </ul>
            ) : null}
            {Array.isArray(item.source_signals) && item.source_signals.length ? <p className="mt-2 text-xs text-slate-500">Signals: {item.source_signals.join(', ')}</p> : null}
            {Array.isArray(item.related_risk_events) && item.related_risk_events.length ? <p className="mt-1 text-xs text-slate-500">Related risk events: {item.related_risk_events.join(', ')}</p> : null}
          </div>
        ))}
      </div>
    </SectionCard>
  )
}
