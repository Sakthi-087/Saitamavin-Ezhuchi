import { useState } from 'react'
import { SectionCard, SectionEyebrow, ProgressMetric } from '../components/Cards'
import StatusBadge from '../components/ui/StatusBadge'
import { simulateDecision } from '../services/api'

const prompts = [
  'Can I afford a bike worth Rs 80,000?',
  'Would a Rs 10,000 purchase still keep me safe this month?',
  'How much would my future balance change after a large expense?',
]

export default function AIAssistant({ analysis, financialScore, fraudCheck, accessToken }) {
  const [amount, setAmount] = useState('80000')
  const [windowDays, setWindowDays] = useState(30)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function handleSimulation(event) {
    event.preventDefault()
    if (!amount) return

    setLoading(true)
    setError('')

    try {
      const nextResult = await simulateDecision(
        {
          amount: Number(amount),
          window_days: Number(windowDays),
        },
        accessToken,
      )
      setResult(nextResult)
    } catch (nextError) {
      setError(nextError.message || 'Unable to run simulation.')
    } finally {
      setLoading(false)
    }
  }

  const safetyTone = result
    ? result.future_balance < 0
      ? 'danger'
      : result.future_balance < result.safety_threshold
        ? 'warning'
        : 'good'
    : 'neutral'

  return (
    <div className="space-y-6">
      <SectionCard
        title="Decision Lab"
        subtitle="Simulate a purchase before you spend and get a deterministic answer first, with AI explanation layered on top."
        action={<StatusBadge label="Scenario engine" tone="info" />}
      >
        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-4">
            <div className="rounded-[28px] border border-slate-200/80 bg-slate-950 p-6 text-white shadow-[0_20px_45px_rgba(15,23,42,0.16)]">
              <SectionEyebrow>Current context</SectionEyebrow>
              <p className="mt-4 text-4xl font-semibold">{financialScore.score}</p>
              <p className="mt-2 text-sm uppercase tracking-[0.22em] text-cyan-200">{financialScore.status}</p>
              <p className="mt-4 text-sm leading-7 text-slate-200">Current score, safety flags, and spend totals shape the scenario before a recommendation is shown.</p>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <ProgressMetric label="Monthly spend" value={analysis.spending.total} max={Math.max(analysis.spending.total, 1)} tone="warning" suffix="" subtitle={`Largest category: ${analysis.spending.largest_category}`} />
              <ProgressMetric label="Safety flags" value={fraudCheck.flagged_transactions.length} max={Math.max(fraudCheck.flagged_transactions.length, 1)} tone="danger" suffix="" subtitle="Suspicious transactions detected so far." />
            </div>

            <div className="rounded-[28px] border border-slate-200/80 bg-slate-50/80 p-5">
              <p className="text-sm font-semibold text-slate-950">Quick scenarios</p>
              <div className="mt-4 space-y-3">
                {prompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setAmount(prompt.includes('10,000') ? '10000' : '80000')}
                    className="w-full rounded-[22px] border border-slate-200 bg-white p-4 text-left text-sm font-medium text-slate-700 hover:border-blue-200 hover:bg-blue-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <form onSubmit={handleSimulation} className="space-y-4 rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-sm">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="text-sm font-semibold text-slate-700">Planned expense</span>
                  <input
                    type="number"
                    min="1"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                    className="mt-2 w-full rounded-[18px] border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500"
                    placeholder="80000"
                  />
                </label>

                <label className="block">
                  <span className="text-sm font-semibold text-slate-700">Projection window</span>
                  <select
                    value={windowDays}
                    onChange={(event) => setWindowDays(event.target.value)}
                    className="mt-2 w-full rounded-[18px] border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500"
                  >
                    <option value={30}>Next 30 days</option>
                    <option value={45}>Next 45 days</option>
                    <option value={60}>Next 60 days</option>
                  </select>
                </label>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-[18px] bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-900/10 hover:bg-slate-900 disabled:opacity-60"
              >
                {loading ? 'Running simulation...' : 'Run Simulation'}
              </button>

              {error ? <div className="rounded-[20px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div> : null}
            </form>

            {result ? (
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-[28px] bg-slate-950 p-5 text-white shadow-[0_20px_45px_rgba(15,23,42,0.16)]">
                    <p className="text-sm uppercase tracking-[0.18em] text-cyan-200">Decision</p>
                    <p className="mt-3 text-4xl font-semibold">{result.decision}</p>
                    <p className="mt-3 text-sm leading-7 text-slate-200">{result.reason}</p>
                  </div>
                  <div className={`rounded-[28px] p-5 shadow-sm ${result.future_balance < 0 ? 'bg-rose-50 text-rose-900' : result.future_balance < result.safety_threshold ? 'bg-amber-50 text-amber-900' : 'bg-emerald-50 text-emerald-900'}`}>
                    <p className="text-sm uppercase tracking-[0.18em]">Future balance</p>
                    <p className="mt-3 text-4xl font-semibold">Rs {Number(result.future_balance).toLocaleString('en-IN')}</p>
                    <p className="mt-3 text-sm">Threshold: Rs {Number(result.safety_threshold).toLocaleString('en-IN')}</p>
                    <div className="mt-4">
                      <StatusBadge label={result.decision} tone={safetyTone} />
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-4">
                  <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Current balance</p><p className="mt-2 text-xl font-semibold text-slate-950">Rs {Number(result.current_balance).toLocaleString('en-IN')}</p></div>
                  <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Projected income</p><p className="mt-2 text-xl font-semibold text-slate-950">Rs {Number(result.projected_income).toLocaleString('en-IN')}</p></div>
                  <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Projected expenses</p><p className="mt-2 text-xl font-semibold text-slate-950">Rs {Number(result.projected_expenses).toLocaleString('en-IN')}</p></div>
                  <div className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">Planned expense</p><p className="mt-2 text-xl font-semibold text-slate-950">Rs {Number(result.simulated_cost).toLocaleString('en-IN')}</p></div>
                </div>

                <div className="rounded-[28px] border border-blue-200/80 bg-blue-50 p-5 shadow-sm">
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-700">AI Explanation</p>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{result.ai_explanation}</p>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[320px] items-center justify-center rounded-[28px] border border-dashed border-slate-300 bg-white/70 p-8 text-center text-sm leading-7 text-slate-500">
                Run a scenario like Rs 80,000 or Rs 10,000 to see projected balance, decision safety, and an explanation built on top of deterministic financial modeling.
              </div>
            )}
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
