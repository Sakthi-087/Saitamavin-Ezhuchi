const sections = [
  {
    title: 'Intelligence',
    items: [
      { key: 'dashboard', label: 'Overview', icon: 'OV' },
      { key: 'behavior', label: 'Behavior', icon: 'BH' },
      { key: 'risk', label: 'Risk', icon: 'RK' },
      { key: 'guidance', label: 'Guidance', icon: 'GD' },
    ],
  },
  {
    title: 'Analytics',
    items: [
      { key: 'analytics', label: 'Scoring', icon: 'SC' },
      { key: 'history', label: 'History', icon: 'HT' },
    ],
  },
  {
    title: 'Tools',
    items: [
      { key: 'assistant', label: 'Decision Lab', icon: 'DL' },
      { key: 'settings', label: 'Settings', icon: 'ST' },
    ],
  },
]

export default function Sidebar({ activeRoute, onNavigate, session, onSignOut }) {
  return (
    <aside className="glass-surface rounded-[32px] border border-white/80 p-6 xl:sticky xl:top-6 xl:h-[calc(100vh-3rem)] xl:overflow-y-auto">
      <div className="flex items-center gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-[18px] bg-gradient-to-br from-slate-900 via-blue-700 to-blue-500 text-lg font-bold text-white shadow-[0_18px_35px_rgba(37,99,235,0.25)]">
          CB
        </div>
        <div>
          <p className="text-lg font-semibold tracking-tight text-slate-950">CareBank</p>
          <p className="text-sm text-slate-500">AI-powered financial intelligence</p>
        </div>
      </div>

      <div className="mt-6 rounded-[24px] border border-slate-200/80 bg-slate-50/90 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Active workspace</p>
        <p className="mt-2 truncate text-sm font-semibold text-slate-950">{session?.user?.email || 'Unknown user'}</p>
        <p className="mt-2 text-sm leading-6 text-slate-500">Imported statements, score history, alerts, and guided actions all live here.</p>
      </div>

      <nav className="mt-8 space-y-6">
        {sections.map((section) => (
          <div key={section.title}>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{section.title}</p>
            <div className="space-y-2">
              {section.items.map((item) => {
                const isActive = activeRoute === item.key
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => onNavigate(item.key)}
                    className={`group flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-semibold transition ${
                      isActive
                        ? 'bg-slate-950 text-white shadow-[0_16px_30px_rgba(15,23,42,0.16)]'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <span
                      className={`flex h-9 w-9 items-center justify-center rounded-2xl border text-xs font-bold ${
                        isActive ? 'border-white/10 bg-white/10 text-white' : 'border-slate-200 bg-white text-slate-500'
                      }`}
                    >
                      {item.icon}
                    </span>
                    <span className="flex-1">{item.label}</span>
                    {isActive ? <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 shadow-[0_0_0_6px_rgba(34,211,238,0.12)]" /> : null}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-8 rounded-[24px] border border-slate-200/80 bg-gradient-to-br from-slate-950 via-slate-900 to-blue-900 p-4 text-sm text-slate-100 shadow-[0_20px_40px_rgba(15,23,42,0.18)]">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200">Live pipeline</p>
        <p className="mt-3 text-sm leading-6 text-slate-200">CSV to anomaly checks to scoring to simulation to AI explanation.</p>
        <div className="mt-4 flex items-center gap-2 text-xs text-cyan-200">
          <span className="h-2 w-2 rounded-full bg-emerald-400 pulse-soft" />
          Deterministic first. AI second.
        </div>
      </div>

      <button
        type="button"
        onClick={onSignOut}
        className="mt-8 w-full rounded-2xl border border-slate-300/80 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
      >
        Sign Out of CareBank
      </button>
    </aside>
  )
}
