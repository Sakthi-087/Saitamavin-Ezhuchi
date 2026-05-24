import { useState } from 'react'
import { SectionCard } from '../components/Cards'
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

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <SectionCard title="Decision Prompts" subtitle="Use these to guide the live demo or user exploration">
          <div className="space-y-3">
            {prompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setAmount(prompt.includes('10,000') ? '10000' : '80000')}
                className="w-full rounded-2xl border border-cyan-200 bg-cyan-50 p-4 text-left text-sm font-medium text-cyan-900 transition hover:bg-cyan-100"
              >
                {prompt}
              </button>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Decision Context" subtitle="Signals currently shaping simulation and guidance">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="font-semibold text-slate-900">Score status</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">{financialScore.status}</p>
              <p className="mt-2 text-sm text-slate-600">Current score: {financialScore.score}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="font-semibold text-slate-900">Safety flags</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">{fraudCheck.flagged_transactions.length}</p>
              <p className="mt-2 text-sm text-slate-600">Suspicious transactions detected so far.</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="font-semibold text-slate-900">Monthly spend</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">Rs {analysis.spending.total.toLocaleString('en-IN')}</p>
              <p className="mt-2 text-sm text-slate-600">Largest category: {analysis.spending.largest_category}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="font-semibold text-slate-900">Assistant mode</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">Deterministic + AI</p>
              <p className="mt-2 text-sm text-slate-600">Numbers are calculated first, then explained.</p>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Simulation Engine" subtitle="Project future balance before making a real purchase">
        <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
          <form onSubmit={handleSimulation} className="space-y-4 rounded-3xl border border-slate-200 bg-slate-50 p-5">
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">Planned expense</span>
              <input
                type="number"
                min="1"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-cyan-500"
                placeholder="80000"
              />
            </label>

            <label className="block">
              <span className="text-sm font-semibold text-slate-700">Projection window</span>
              <select
                value={windowDays}
                onChange={(event) => setWindowDays(event.target.value)}
                className="mt-2 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-cyan-500"
              >
                <option value={30}>Next 30 days</option>
                <option value={45}>Next 45 days</option>
                <option value={60}>Next 60 days</option>
              </select>
            </label>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60"
            >
              {loading ? 'Running simulation...' : 'Run Simulation'}
            </button>

            {error ? <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div> : null}
          </form>

          <div className="space-y-4">
            {result ? (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-3xl bg-slate-900 p-5 text-white">
                    <p className="text-sm uppercase tracking-[0.18em] text-cyan-200">Decision</p>
                    <p className="mt-3 text-4xl font-bold">{result.decision}</p>
                    <p className="mt-3 text-sm text-slate-200">{result.reason}</p>
                  </div>
                  <div className={`rounded-3xl p-5 ${result.future_balance < 0 ? 'bg-rose-50 text-rose-900' : result.future_balance < result.safety_threshold ? 'bg-amber-50 text-amber-900' : 'bg-emerald-50 text-emerald-900'}`}>
                    <p className="text-sm uppercase tracking-[0.18em]">Future balance</p>
                    <p className="mt-3 text-4xl font-bold">Rs {Number(result.future_balance).toLocaleString('en-IN')}</p>
                    <p className="mt-3 text-sm">Threshold: Rs {Number(result.safety_threshold).toLocaleString('en-IN')}</p>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-4">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">Current balance</p><p className="mt-2 text-xl font-bold text-slate-900">Rs {Number(result.current_balance).toLocaleString('en-IN')}</p></div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">Projected income</p><p className="mt-2 text-xl font-bold text-slate-900">Rs {Number(result.projected_income).toLocaleString('en-IN')}</p></div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">Projected expenses</p><p className="mt-2 text-xl font-bold text-slate-900">Rs {Number(result.projected_expenses).toLocaleString('en-IN')}</p></div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">Planned expense</p><p className="mt-2 text-xl font-bold text-slate-900">Rs {Number(result.simulated_cost).toLocaleString('en-IN')}</p></div>
                </div>

                <div className="rounded-3xl border border-cyan-200 bg-cyan-50 p-5">
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-cyan-700">AI Explanation</p>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{result.ai_explanation}</p>
                </div>
              </>
            ) : (
              <div className="flex h-full min-h-[320px] items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm leading-7 text-slate-500">
                Run a scenario like Rs 80,000 or Rs 10,000 to see projected balance, decision safety, and an explanation built on top of deterministic financial modeling.
              </div>
            )}
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
