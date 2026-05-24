const tones = {
  good: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  danger: 'border-rose-200 bg-rose-50 text-rose-700',
  neutral: 'border-slate-200 bg-slate-100 text-slate-700',
}

export default function StatusBadge({ label, tone = 'neutral' }) {
  return <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${tones[tone] || tones.neutral}`}>{label}</span>
}
