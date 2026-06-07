import { useMemo } from 'react'
import { SectionCard, TimelineDot } from './Cards'
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
  return 'info'
}

function bucketByDate(events) {
  const today = new Date()
  const buckets = { Today: [], Yesterday: [], Older: [] }

  events.forEach((event) => {
    const created = new Date(event.createdAt || Date.now())
    const diffDays = Math.floor((Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) - Date.UTC(created.getFullYear(), created.getMonth(), created.getDate())) / 86400000)
    if (diffDays <= 0) buckets.Today.push(event)
    else if (diffDays === 1) buckets.Yesterday.push(event)
    else buckets.Older.push(event)
  })

  return buckets
}

export default function RealtimeAlertCenter({ connectionStatus, liveEvents, onDismiss }) {
  const grouped = useMemo(() => bucketByDate(liveEvents || []), [liveEvents])
  const unreadCount = liveEvents?.length || 0

  return (
    <SectionCard
      title="Realtime Alert Center"
      subtitle="Live alerts streamed from event processing"
      action={
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm" aria-hidden="true">
            <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-2">
              <path d="M15 17H5a2 2 0 0 1-2-2v-1a1 1 0 0 1 1-1h1V9a7 7 0 0 1 14 0v4h1a1 1 0 0 1 1 1v1a2 2 0 0 1-2 2h-2" />
              <path d="M10 17a2 2 0 0 0 4 0" />
            </svg>
          </span>
          <span className="flex h-3 w-3 rounded-full bg-blue-500 pulse-soft" />
          <StatusBadge label={`${unreadCount} unread`} tone={toneForStatus(connectionStatus)} />
          <StatusBadge label={connectionStatus} tone={toneForStatus(connectionStatus)} />
        </div>
      }
    >
      {connectionStatus === 'reconnecting' ? <p className="mb-3 text-xs text-amber-700">Reconnecting to realtime stream...</p> : null}
      {!liveEvents.length ? (
        <EmptyState title="No live alerts yet" description="Once analysis events trigger alerts, they will appear here." />
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([label, events]) =>
            events.length ? (
              <div key={label}>
                <p className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">{label}</p>
                <div className="space-y-3">
                  {events.map((event) => (
                    <div key={event.eventId} className="flex gap-4 rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm">
                      <TimelineDot tone={toneForSeverity(event.severity)} />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <StatusBadge label={event.severity} tone={toneForSeverity(event.severity)} />
                              <p className="font-semibold text-slate-950">{event.title}</p>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-slate-700">{event.message}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => onDismiss(event.eventId)}
                            className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-slate-400 hover:bg-slate-100"
                          >
                            Dismiss
                          </button>
                        </div>
                        <p className="mt-3 text-xs uppercase tracking-[0.22em] text-slate-500">{new Date(event.createdAt).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null,
          )}
        </div>
      )}
    </SectionCard>
  )
}
