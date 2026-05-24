const items = [
  { key: 'dashboard', label: 'Overview' },
  { key: 'behavior', label: 'Behavior' },
  { key: 'risk', label: 'Risk' },
  { key: 'guidance', label: 'Guidance' },
  { key: 'history', label: 'History' },
  { key: 'analytics', label: 'Scoring' },
  { key: 'assistant', label: 'Decision Lab' },
  { key: 'settings', label: 'Data Controls' },
]

export default function Sidebar({ activeRoute, onNavigate, session, onSignOut }) {
  return (
    <aside className="rounded-[28px] border border-slate-200/70 bg-white/95 p-6 shadow-2xl shadow-slate-900/5 backdrop-blur xl:sticky xl:top-6 xl:h-[calc(100vh-3rem)] xl:overflow-y-auto">
      <div className="flex items-center gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-600 to-slate-900 text-lg font-bold text-white shadow-lg shadow-blue-900/20">
          CB
        </div>
        <div>
          <p className="text-lg font-bold text-slate-900">CareBank</p>
          <p className="text-sm text-slate-500">Predict before you spend</p>
        </div>
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Active workspace</p>
        <p className="mt-2 truncate text-sm font-semibold text-slate-900">{session?.user?.email || 'Unknown user'}</p>
        <p className="mt-2 text-sm leading-6 text-slate-500">This session unlocks your imported statements, scoring history, alerts, and AI guidance.</p>
      </div>

      <nav className="mt-8 space-y-2">
        {items.map((item) => {
          const isActive = activeRoute === item.key
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onNavigate(item.key)}
              className={`w-full rounded-2xl px-4 py-3 text-left text-sm font-semibold transition ${
                isActive
                  ? 'bg-slate-900 text-white shadow-lg shadow-slate-900/10'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {item.label}
            </button>
          )
        })}
      </nav>

      <div className="mt-8 rounded-2xl bg-gradient-to-br from-emerald-50 to-cyan-50 p-4 text-sm text-slate-700">
        <p className="font-semibold text-slate-900">Live pipeline</p>
        <p className="mt-2 leading-6">CSV to anomaly checks to scoring to simulation to AI explanation.</p>
      </div>

      <button
        type="button"
        onClick={onSignOut}
        className="mt-8 w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
      >
        Sign Out of CareBank
      </button>
    </aside>
  )
}
