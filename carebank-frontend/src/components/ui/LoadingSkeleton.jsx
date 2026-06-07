export default function LoadingSkeleton({ lines = 3 }) {
  return (
    <div className="space-y-3 rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur">
      {Array.from({ length: lines }).map((_, idx) => (
        <div key={idx} className="skeleton-shimmer h-4 rounded-full" />
      ))}
    </div>
  )
}
