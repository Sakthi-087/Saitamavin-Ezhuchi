export default function ErrorCard({ title = 'Unable to load module', message = 'Please try again.', onRetry, compact = false }) {
  return (
    <div className={`rounded-2xl border border-rose-200 bg-rose-50 text-rose-700 ${compact ? 'p-4' : 'p-5'}`}>
      <p className="font-semibold">{title}</p>
      <p className="mt-2 text-sm">{message}</p>
      {typeof onRetry === 'function' ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-xl bg-rose-600 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-700"
        >
          Retry
        </button>
      ) : null}
    </div>
  )
}
