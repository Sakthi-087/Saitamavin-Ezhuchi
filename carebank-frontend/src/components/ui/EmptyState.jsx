export default function EmptyState({ title = 'No data available', description = 'Try again after more transactions are processed.' }) {
  return (
    <div className="rounded-[28px] border border-dashed border-slate-300 bg-white/70 p-6 text-sm text-slate-600 backdrop-blur">
      <p className="text-base font-semibold text-slate-900">{title}</p>
      <p className="mt-2 max-w-2xl leading-6">{description}</p>
    </div>
  )
}
