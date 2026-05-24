export default function EmptyState({ title = 'No data available', description = 'Try again after more transactions are processed.' }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
      <p className="font-semibold text-slate-900">{title}</p>
      <p className="mt-2">{description}</p>
    </div>
  )
}
