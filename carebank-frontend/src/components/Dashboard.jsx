import { KpiCard, SectionCard, SectionEyebrow, TimelineDot } from './Cards'
import StatusBadge from './ui/StatusBadge'
import EmptyState from './ui/EmptyState'
import RealtimeAlertCenter from './RealtimeAlertCenter'

function formatMoney(value) {
  return `Rs ${Number(value ?? 0).toLocaleString('en-IN')}`
}

function getTopValue(list, fallback = 'N/A') {
  if (!Array.isArray(list) || !list.length) return fallback
  return String(list[0])
}

function dispatchCopilotPrompt(prompt) {
  window.dispatchEvent(new CustomEvent('carebank:open-copilot', { detail: { prompt } }))
}

function SummaryRow({ label, value, tone = 'neutral', badgeLabel }) {
  return (
    <div className="rounded-[22px] border border-slate-200/80 bg-slate-50/80 p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <div className="mt-3 flex items-center justify-between gap-3">
        <p className="text-base font-semibold text-slate-950">{value}</p>
        <StatusBadge label={badgeLabel || label} tone={tone === 'neutral' ? 'neutral' : tone} />
      </div>
    </div>
  )
}

export default function Dashboard({
  analysis,
  financialScore,
  fraudCheck,
  riskSummary,
  guidanceSummary,
  realtimeConnectionStatus,
  realtimeAlerts,
  realtimeAlertCount,
  onDismissAlert,
  onNavigate,
}) {
  const flaggedTransactions = fraudCheck?.flagged_transactions || []
  const scoreValue = Number(financialScore?.score ?? 0)
  const riskValue = Number(riskSummary?.overall_risk_score ?? financialScore?.breakdown?.risk_score ?? 0)
  const monthlySpend = Number(analysis?.spending?.total ?? 0)
  const savingsRatio = Number(financialScore?.metrics?.savings_ratio ?? 0) * 100

  const topStrength = getTopValue(financialScore?.positive_signals, 'Stable spending discipline')
  const topRisk = getTopValue(financialScore?.major_issues, 'No major risks surfaced')
  const topRecommendation = getTopValue(analysis?.recommendations, 'Continue tracking spending patterns')
  const riskEvents = Array.isArray(riskSummary?.risk_events) ? riskSummary.risk_events.slice(0, 3) : []
  const guidanceItems = Array.isArray(guidanceSummary?.items || guidanceSummary?.guidance_items)
    ? (guidanceSummary?.items || guidanceSummary?.guidance_items).slice(0, 3)
    : []

  const copilotPrompts = [
    'Why is my risk high?',
    'How can I improve my score?',
    'What should I cut this month?',
  ]

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          item={{
            title: 'Financial Health Score',
            value: scoreValue,
            subtitle: financialScore?.status || 'Status unavailable',
            tone: scoreValue >= 80 ? 'good' : scoreValue >= 60 ? 'warning' : 'danger',
            icon: 'FH',
            trend: financialScore?.scoring_version || 'Deterministic',
          }}
        />
        <KpiCard
          item={{
            title: 'Risk Score',
            value: riskValue,
            subtitle: riskSummary?.risk_level || financialScore?.breakdown?.risk_score?.toFixed?.(0) || 'Review risk posture',
            tone: riskValue >= 75 ? 'danger' : riskValue >= 50 ? 'warning' : 'good',
            icon: 'RS',
            trend: `${riskEvents.length} visible events`,
          }}
        />
        <KpiCard
          item={{
            title: 'Monthly Spend',
            value: formatMoney(monthlySpend),
            subtitle: analysis?.insights?.current_month || 'Current month',
            tone: monthlySpend > 0 ? 'info' : 'neutral',
            icon: 'MS',
            trend: flaggedTransactions.length ? `${flaggedTransactions.length} flagged` : 'No flagged spend',
          }}
        />
        <KpiCard
          item={{
            title: 'Savings Ratio',
            value: `${savingsRatio.toFixed(0)}%`,
            subtitle: 'Share retained after spending',
            tone: savingsRatio >= 25 ? 'good' : savingsRatio >= 15 ? 'warning' : 'danger',
            icon: 'SR',
            trend: savingsRatio >= 25 ? 'Healthy buffer' : 'Watch savings',
          }}
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <SectionCard
          title="Financial Health Summary"
          subtitle="A single-glance read on score, status, strengths, risks, and the strongest recommendation."
          action={<StatusBadge label={financialScore?.status || 'Unknown'} tone={scoreValue >= 80 ? 'good' : scoreValue >= 60 ? 'warning' : 'danger'} />}
        >
          <div className="grid gap-4 md:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-[28px] border border-slate-200/80 bg-slate-950 p-6 text-white shadow-[0_20px_45px_rgba(15,23,42,0.16)]">
              <SectionEyebrow>Score</SectionEyebrow>
              <p className="mt-4 text-6xl font-semibold tracking-tight">{scoreValue}</p>
              <p className="mt-3 text-sm uppercase tracking-[0.22em] text-cyan-200">{financialScore?.status || 'Unknown'}</p>
              <p className="mt-4 text-sm leading-7 text-slate-200">{analysis?.financial_health?.summary || financialScore?.summary || 'Executive financial summary anchored to deterministic scoring.'}</p>
            </div>

            <div className="grid gap-3">
              <SummaryRow label="Top strength" value={topStrength} tone="good" badgeLabel="Positive" />
              <SummaryRow label="Top risk" value={topRisk} tone="danger" badgeLabel="Attention" />
              <SummaryRow label="Top recommendation" value={topRecommendation} tone="info" badgeLabel="Focus" />
              <div className="rounded-[22px] border border-slate-200/80 bg-slate-50/80 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">What this means</p>
                <p className="mt-3 text-sm leading-7 text-slate-700">
                  {scoreValue >= 80
                    ? 'The profile is healthy and consistent. Keep the current discipline and watch for outliers.'
                    : scoreValue >= 60
                      ? 'The profile is usable but mixed. A few focused changes can materially improve the score.'
                      : 'The profile needs attention. Small reductions in volatile spending will likely have the greatest impact.'}
                </p>
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          title="Risk Summary"
          subtitle="Only the executive-level risk posture is shown here. Deep analysis lives on the Risk page."
          action={<StatusBadge label={riskSummary?.risk_level || 'Low'} tone={riskValue >= 75 ? 'danger' : riskValue >= 50 ? 'warning' : 'good'} />}
        >
          <div className="space-y-4">
            <div className="rounded-[28px] border border-slate-200/80 bg-gradient-to-br from-slate-50 to-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Overall risk score</p>
                  <p className="mt-3 text-5xl font-semibold text-slate-950">{riskValue.toFixed(1)}</p>
                </div>
                <StatusBadge label={riskSummary?.risk_level || 'Low'} tone={riskValue >= 75 ? 'danger' : riskValue >= 50 ? 'warning' : 'good'} />
              </div>
            </div>

            <div className="space-y-3">
              {riskEvents.length ? (
                riskEvents.map((event, index) => (
                  <div key={event.risk_event_id || `${event.event_type}-${index}`} className="flex gap-3 rounded-[22px] border border-slate-200/80 bg-white p-4 shadow-sm">
                    <TimelineDot tone={index === 0 ? 'danger' : index === 1 ? 'warning' : 'info'} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-semibold text-slate-950">{event.event_type || event.risk_type || 'Risk event'}</p>
                        <StatusBadge label={event.severity || 'Low'} tone={event.severity?.toLowerCase?.().includes('high') ? 'danger' : event.severity?.toLowerCase?.().includes('medium') ? 'warning' : 'info'} />
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{event.recommendation || event.recommendation_text || 'No recommendation provided.'}</p>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState title="No risk events available" description="Risk intelligence will appear here once events are emitted." />
              )}
            </div>
          </div>
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <SectionCard
          title="Guidance Summary"
          subtitle="Only the top 3 recommendations are surfaced here. Open the Guidance page for the full inbox."
          action={
            <button
              type="button"
              onClick={() => onNavigate?.('guidance')}
              className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400 hover:bg-slate-50"
            >
              View All Guidance
            </button>
          }
        >
          <div className="space-y-3">
            {guidanceItems.length ? (
              guidanceItems.map((item, index) => (
                <div key={item.guidance_id || `${item.title}-${index}`} className="rounded-[22px] border border-slate-200/80 bg-slate-50/80 p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{item.priority || 'Low'} priority</p>
                      <p className="mt-2 font-semibold text-slate-950">{item.title || item.guidance_type || 'Guidance item'}</p>
                    </div>
                    <StatusBadge label={`TTL ${item.ttl_days ?? 'N/A'}d`} tone="neutral" />
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-600">{item.rationale || 'No rationale provided.'}</p>
                </div>
              ))
            ) : (
              <EmptyState title="No guidance items" description="Guidance will appear when behavior or risk signals are generated." />
            )}
          </div>
        </SectionCard>

        <RealtimeAlertCenter
          connectionStatus={realtimeConnectionStatus}
          liveEvents={realtimeAlerts || []}
          onDismiss={onDismissAlert}
        />
      </div>

      <SectionCard
        title="Copilot Quick Ask"
        subtitle="Fast prompts for executives who want a one-screen answer without leaving the dashboard."
        action={<StatusBadge label="Quick ask" tone="info" />}
      >
        <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-[28px] border border-slate-200/80 bg-slate-950 p-6 text-white shadow-[0_20px_45px_rgba(15,23,42,0.16)]">
            <SectionEyebrow>Ask copilot</SectionEyebrow>
            <p className="mt-4 text-2xl font-semibold">Open the assistant with a pre-framed question.</p>
            <p className="mt-3 text-sm leading-7 text-slate-200">Useful when you want a reasoned answer without jumping into deep analytics pages.</p>
            <div className="mt-6 flex flex-wrap gap-2">
              <StatusBadge label={realtimeConnectionStatus || 'connected'} tone={realtimeConnectionStatus === 'connected' ? 'good' : 'warning'} />
              <StatusBadge label={`${realtimeAlertCount || 0} alerts`} tone="info" />
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {copilotPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => dispatchCopilotPrompt(prompt)}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-blue-200 hover:bg-blue-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => dispatchCopilotPrompt('Explain my score and risk in plain language')}
              className="w-full rounded-[22px] bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-900/10 hover:bg-slate-900"
            >
              Open Copilot
            </button>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
