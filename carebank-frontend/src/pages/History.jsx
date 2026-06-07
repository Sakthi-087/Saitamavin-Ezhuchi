import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchAuditEventHistory,
  fetchBehaviorSnapshotHistory,
  fetchFinancialScoreHistory,
  fetchGuidanceHistory,
  fetchRiskEventHistory,
} from '../services/api'
import { SectionCard } from '../components/Cards'
import LoadingSkeleton from '../components/ui/LoadingSkeleton'
import ErrorCard from '../components/ui/ErrorCard'
import HistoryTimeline from '../components/HistoryTimeline'
import StatusBadge from '../components/ui/StatusBadge'

const tabs = [
  { key: 'score', label: 'Score History' },
  { key: 'risk', label: 'Risk Events' },
  { key: 'guidance', label: 'Guidance History' },
  { key: 'behavior', label: 'Behavior Snapshots' },
  { key: 'audit', label: 'Audit Events' },
]

export default function History({ accessToken }) {
  const [activeTab, setActiveTab] = useState('score')
  const [state, setState] = useState({ loading: true, error: '', data: {} })

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: '' }))

    try {
      const [score, risk, guidance, behavior, audit] = await Promise.allSettled([
        fetchFinancialScoreHistory(accessToken, 25),
        fetchRiskEventHistory(accessToken, 25),
        fetchGuidanceHistory(accessToken, 25),
        fetchBehaviorSnapshotHistory(accessToken, 25),
        fetchAuditEventHistory(accessToken, 25),
      ])

      const nextData = {
        score: score.status === 'fulfilled' ? (score.value.items || score.value.data || score.value || []) : [],
        risk: risk.status === 'fulfilled' ? (risk.value.items || risk.value.data || risk.value || []) : [],
        guidance: guidance.status === 'fulfilled' ? (guidance.value.items || guidance.value.data || guidance.value || []) : [],
        behavior: behavior.status === 'fulfilled' ? (behavior.value.items || behavior.value.data || behavior.value || []) : [],
        audit: audit.status === 'fulfilled' ? (audit.value.items || audit.value.data || audit.value || []) : [],
      }

      const errors = [score, risk, guidance, behavior, audit]
        .filter((x) => x.status === 'rejected')
        .map((x) => x.reason?.message)
        .filter(Boolean)

      setState({ loading: false, error: errors[0] || '', data: nextData })
    } catch (error) {
      setState({ loading: false, error: error.message || 'Unable to load history.', data: {} })
    }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    load()
  }, [accessToken, load])

  const activeData = useMemo(() => {
    const list = state.data?.[activeTab]
    return Array.isArray(list) ? list : []
  }, [activeTab, state.data])

  if (state.loading) return <LoadingSkeleton lines={7} />

  return (
    <SectionCard
      title="History Workspace"
      subtitle="Snapshot and event history across score, risk, guidance, behavior, and audit trails"
      action={<StatusBadge label="Auditable timeline" tone="info" />}
    >
      <div className="mb-4 flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${activeTab === tab.key ? 'bg-slate-950 text-white shadow-sm' : 'border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {state.error ? <ErrorCard title="Some history sources failed" message={state.error} onRetry={load} compact /> : null}

      <div className="mt-4">
        <HistoryTimeline items={activeData} type={activeTab} />
      </div>
    </SectionCard>
  )
}
