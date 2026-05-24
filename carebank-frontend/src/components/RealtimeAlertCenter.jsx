import { SectionCard } from './Cards'
import StatusBadge from './ui/StatusBadge'
import EmptyState from './ui/EmptyState'

function toneForStatus(status) {
  if (status === 'connected') return 'good'
  if (status === 'reconnecting' || status === 'connecting') return 'warning'
  if (status === 'error') return 'danger'
  return 'neutral'
}

function toneForSeverity(level = '') {
  const normalized = String(level).toLowerCase()
  if (normalized.includes('critical') || normalized.includes('high')) return 'danger'
  if (normalized.includes('medium') || normalized.includes('warning')) return 'warning'
  return 'good'
}

export default function RealtimeAlertCenter({ connectionStatus, liveEvents, onDismiss }) {
  return (
    <SectionCard
      title="Realtime Alert Center"
      subtitle="Live alerts streamed from event processing"
      action={<StatusBadge label={connectionStatus} tone={toneForStatus(connectionStatus)} />}
    >
      {connectionStatus === 'reconnecting' ? <p className="mb-3 text-xs text-amber-700">Reconnecting to realtime stream...</p> : null}
      {!liveEvents.length ? (
        <EmptyState title="No live alerts yet" description="Once analysis events trigger alerts, they will appear here." />
      ) : (
        <div className="space-y-3">
          {liveEvents.map((event) => (
            <div key={event.eventId} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <StatusBadge label={event.severity} tone={toneForSeverity(event.severity)} />
                  <p className="font-semibold text-slate-900">{event.title}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onDismiss(event.eventId)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
                >
                  Dismiss
                </button>
              </div>
              <p className="mt-2 text-sm text-slate-700">{event.message}</p>
              <p className="mt-2 text-xs text-slate-500">{new Date(event.createdAt).toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  )
}
