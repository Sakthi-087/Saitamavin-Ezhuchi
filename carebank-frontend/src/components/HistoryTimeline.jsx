import EmptyState from './ui/EmptyState'
import { TimelineDot } from './Cards'

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
        <div key={item.id || item.event_id || idx} className="flex gap-4 rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
          <TimelineDot tone={type === 'risk' ? 'danger' : type === 'guidance' ? 'info' : 'neutral'} />
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{new Date(item.created_at || item.generated_at || Date.now()).toLocaleString()}</p>
            <p className="mt-2 font-semibold text-slate-950">{safeSummary(item, type)}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
