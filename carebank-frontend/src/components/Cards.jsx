export const toneStyles = {
  good: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  danger: 'border-rose-200 bg-rose-50 text-rose-700',
  info: 'border-blue-200 bg-blue-50 text-blue-700',
  neutral: 'border-slate-200 bg-slate-50 text-slate-700',
}

function formatNumber(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return String(value ?? '--')
  return number.toLocaleString('en-IN')
}

function formatValue(value) {
  if (typeof value === 'number') return formatNumber(value)
  return String(value ?? '--')
}

export function KpiCard({ item }) {
  const tone = item.tone || 'neutral'
  const trend = item.trend
  const icon = item.icon || '◆'
  return (
    <div className="card-hover rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_20px_50px_rgba(15,23,42,0.08)] backdrop-blur">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-3">
          <div className={`flex h-11 w-11 items-center justify-center rounded-2xl border ${toneStyles[tone] || toneStyles.neutral}`}>
            <span className="text-sm font-bold">{icon}</span>
          </div>
          <div>
            <p className="text-sm font-medium tracking-wide text-slate-500">{item.title}</p>
            <p className="mt-2 text-3xl font-bold tracking-tight text-slate-950">{formatValue(item.value)}</p>
          </div>
        </div>
        <div className="text-right">
          <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${toneStyles[tone] || toneStyles.neutral}`}>
            {tone}
          </span>
          {trend ? <p className="mt-2 text-xs font-medium text-slate-500">{trend}</p> : null}
        </div>
      </div>
      <p className="mt-4 max-w-[32ch] text-sm leading-6 text-slate-500">{item.subtitle}</p>
    </div>
  )
}

export function SectionCard({ title, subtitle, children, action }) {
  return (
    <section className="card-hover rounded-[30px] border border-white/80 bg-white/90 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-[1.35rem] font-semibold tracking-tight text-slate-950">{title}</h2>
          {subtitle ? <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

export function ProgressMetric({ label, value, max = 100, tone = 'info', subtitle, suffix = '%' }) {
  const clamped = Math.max(0, Math.min(Number(value) || 0, max))
  const percentage = max ? (clamped / max) * 100 : 0
  const barTones = {
    good: 'from-emerald-500 to-emerald-400',
    warning: 'from-amber-500 to-amber-400',
    danger: 'from-rose-500 to-rose-400',
    info: 'from-blue-500 to-cyan-400',
    neutral: 'from-slate-500 to-slate-400',
  }

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/90 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-900">{label}</p>
        <p className="text-sm font-semibold text-slate-700">
          {Number.isFinite(Number(value)) ? Number(value).toFixed(suffix === '%' ? 0 : 1) : '--'}
          {suffix}
        </p>
      </div>
      <div className="mt-3 h-2 rounded-full bg-slate-200">
        <div className={`h-2 rounded-full bg-gradient-to-r ${barTones[tone] || barTones.neutral}`} style={{ width: `${percentage}%` }} />
      </div>
      {subtitle ? <p className="mt-2 text-xs leading-5 text-slate-500">{subtitle}</p> : null}
    </div>
  )
}

export function TimelineDot({ tone = 'info' }) {
  const tones = {
    good: 'bg-emerald-500 shadow-emerald-200',
    warning: 'bg-amber-500 shadow-amber-200',
    danger: 'bg-rose-500 shadow-rose-200',
    info: 'bg-blue-500 shadow-blue-200',
    neutral: 'bg-slate-400 shadow-slate-200',
  }

  return <span className={`mt-1 h-3 w-3 rounded-full ${tones[tone] || tones.neutral}`} />
}

export function SectionEyebrow({ children }) {
  return <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">{children}</p>
}
