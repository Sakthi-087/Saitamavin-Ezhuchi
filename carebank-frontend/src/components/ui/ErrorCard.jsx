export default function ErrorCard({ title = 'Unable to load module', message = 'Please try again.', onRetry, compact = false }) {
  return (
    <div className={`rounded-[28px] border border-rose-200/80 bg-gradient-to-br from-rose-50 to-white text-rose-700 shadow-[0_20px_50px_rgba(239,68,68,0.08)] ${compact ? 'p-4' : 'p-5'}`}>
      <p className="text-sm font-semibold uppercase tracking-[0.18em]">{title}</p>
      <p className="mt-2 text-sm leading-6">{message}</p>
      {typeof onRetry === 'function' ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-full bg-rose-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-rose-200 hover:bg-rose-700"
        >
          Retry
        </button>
      ) : null}
    </div>
  )
}
