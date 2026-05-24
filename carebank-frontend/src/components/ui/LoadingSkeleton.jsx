export default function LoadingSkeleton({ lines = 3 }) {
  return (
    <div className="animate-pulse space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      {Array.from({ length: lines }).map((_, idx) => (
        <div key={idx} className="h-4 rounded bg-slate-200" />
      ))}
    </div>
  )
}
