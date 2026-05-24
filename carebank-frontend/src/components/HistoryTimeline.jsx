import EmptyState from './ui/EmptyState'

function safeSummary(item, type) {
  if (type === 'score') return `Score ${item.score ?? '--'} (${item.status || 'N/A'})`
  if (type === 'risk') return `${item.event_type || item.risk_type || 'Risk event'} - ${item.severity || 'N/A'}`
  if (type === 'guidance') return `${item.title || item.guidance_type || 'Guidance item'} (${item.priority || 'N/A'})`
  if (type === 'behavior') return `Drift ${Number(item.drift_score ?? 0).toFixed(1)} (${item.drift_severity || 'N/A'})`
  if (type === 'audit') return `${item.audit_type || 'Audit event'} - ${item.severity || 'Info'}`
  return 'History entry'
}

export default function HistoryTimeline({ items, type }) {
  if (!items?.length) return <EmptyState title="No history available" description="Upload more transactions to build historical intelligence." />

  return (
    <div className="space-y-3">
      {items.map((item, idx) => (
        <div key={item.id || item.event_id || idx} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs text-slate-500">{new Date(item.created_at || item.generated_at || Date.now()).toLocaleString()}</p>
          <p className="mt-1 font-semibold text-slate-900">{safeSummary(item, type)}</p>
        </div>
      ))}
    </div>
  )
}
