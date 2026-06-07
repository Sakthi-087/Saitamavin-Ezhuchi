import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchGuidance } from '../services/api'
import { SectionCard, TimelineDot } from './Cards'
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

const TABS = ['Critical', 'High', 'Medium', 'Positive']

function tone(priority = '') {
  if (priority === 'Critical' || priority === 'High') return 'danger'
  if (priority === 'Medium') return 'warning'
  if (priority === 'Positive') return 'good'
  return 'neutral'
}

export default function GuidanceInbox({ accessToken }) {
  const [state, setState] = useState({ loading: true, error: '', data: null })
  const [activeTab, setActiveTab] = useState('Critical')
  const [completed, setCompleted] = useState({})

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

  const visibleItems = useMemo(() => {
    return items.filter((item) => item.priority === activeTab)
  }, [activeTab, items])

  const summaryCounts = useMemo(() => {
    return TABS.reduce((acc, tab) => {
      acc[tab] = items.filter((item) => item.priority === tab).length
      return acc
    }, {})
  }, [items])

  useEffect(() => {
    if (!items.length) return
    if (!items.some((item) => item.priority === activeTab)) {
      const nextTab = TABS.find((tab) => items.some((item) => item.priority === tab)) || 'Critical'
      setActiveTab(nextTab)
    }
  }, [activeTab, items])

  if (state.loading) return <LoadingSkeleton lines={8} />
  if (state.error) return <ErrorCard title="Guidance unavailable" message={state.error} onRetry={load} />
  if (!state.data || !items.length) return <EmptyState title="No guidance items" description="Guidance will appear as risk and behavior signals are generated." />

  return (
    <SectionCard title="Guidance Inbox" subtitle="Prioritized actions to improve financial outcomes">
      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
              activeTab === tab
                ? 'border-slate-900 bg-slate-900 text-white'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
            }`}
          >
            {tab} <span className="ml-1 text-xs opacity-70">{summaryCounts[tab] || 0}</span>
          </button>
        ))}
      </div>

      <div className="mt-6 grid gap-4">
        {visibleItems.length ? (
          visibleItems.slice(0, 8).map((item, idx) => {
            const done = Boolean(completed[item.guidance_id || `${item.title}-${idx}`])
            const key = item.guidance_id || `${item.title}-${idx}`
            return (
              <div key={key} className={`rounded-[28px] border p-5 shadow-sm ${done ? 'border-emerald-200 bg-emerald-50/70' : 'border-slate-200/80 bg-white'}`}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-3">
                      <TimelineDot tone={tone(item.priority)} />
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{item.priority || 'Low'} priority</p>
                        <p className="mt-1 text-lg font-semibold text-slate-950">{item.title || item.guidance_type}</p>
                      </div>
                    </div>
                    <p className="mt-4 text-sm leading-7 text-slate-700">{item.rationale || 'No rationale provided.'}</p>
                    {item.expected_impact ? (
                      <div className="mt-4 rounded-[20px] border border-blue-200/80 bg-blue-50 p-4 text-blue-900">
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-blue-700">Impact</p>
                        <p className="mt-2 text-sm font-semibold">{item.expected_impact}</p>
                      </div>
                    ) : null}
                    {Array.isArray(item.action_steps) && item.action_steps.length ? (
                      <div className="mt-4 space-y-2">
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Actions</p>
                        {item.action_steps.slice(0, 4).map((step) => (
                          <label key={step} className="flex cursor-pointer items-start gap-3 rounded-[18px] bg-slate-50 px-3 py-2 text-sm text-slate-700">
                            <input
                              type="checkbox"
                              checked={done}
                              onChange={() => setCompleted((current) => ({ ...current, [key]: !current[key] }))}
                              className="mt-1 h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                            />
                            <span className={done ? 'line-through decoration-emerald-400/70' : ''}>{step}</span>
                          </label>
                        ))}
                      </div>
                    ) : null}
                    <div className="mt-4 flex flex-wrap gap-2">
                      <StatusBadge label={`Confidence ${Number(item.confidence ?? 0).toFixed(2)}`} tone="info" />
                      <StatusBadge label={`Actionability ${Number(item.actionability_score ?? 0).toFixed(2)}`} tone="neutral" />
                      <StatusBadge label={`TTL ${item.ttl_days ?? 'N/A'} days`} tone="neutral" />
                    </div>
                    {Array.isArray(item.source_signals) && item.source_signals.length ? (
                      <p className="mt-3 text-xs text-slate-500">Signals: {item.source_signals.join(', ')}</p>
                    ) : null}
                    {Array.isArray(item.related_risk_events) && item.related_risk_events.length ? (
                      <p className="mt-1 text-xs text-slate-500">Related risk events: {item.related_risk_events.join(', ')}</p>
                    ) : null}
                  </div>

                  <button
                    type="button"
                    onClick={() => setCompleted((current) => ({ ...current, [key]: !current[key] }))}
                    className={`rounded-full px-4 py-2 text-sm font-semibold shadow-sm ${
                      done
                        ? 'border border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border border-slate-200 bg-slate-900 text-white'
                    }`}
                  >
                    {done ? 'Completed' : 'Mark done'}
                  </button>
                </div>
              </div>
            )
          })
        ) : (
          <EmptyState title={`No ${activeTab.toLowerCase()} guidance yet`} description="Switch tabs or wait for new signals to generate fresh guidance." />
        )}
      </div>
    </SectionCard>
  )
}
