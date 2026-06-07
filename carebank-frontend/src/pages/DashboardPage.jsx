import { useEffect, useMemo, useState } from 'react'
import Dashboard from '../components/Dashboard'
import RealtimeAlertCenter from '../components/RealtimeAlertCenter'
import useRealtimeAlerts from '../hooks/useRealtimeAlerts'
import { fetchGuidance, fetchRiskAnalysis } from '../services/api'

export default function DashboardPage({ analysis, financialScore, fraudCheck, accessToken, userId, onNavigate }) {
  const realtime = useRealtimeAlerts({ userId, accessToken, enabled: Boolean(userId && accessToken) })
  const [riskSummary, setRiskSummary] = useState({ loading: true, data: null })
  const [guidanceSummary, setGuidanceSummary] = useState({ loading: true, data: null })

  useEffect(() => {
    if (!accessToken) return

    let cancelled = false

    async function loadSummaries() {
      setRiskSummary({ loading: true, data: null })
      setGuidanceSummary({ loading: true, data: null })

      const [riskResult, guidanceResult] = await Promise.allSettled([
        fetchRiskAnalysis(accessToken),
        fetchGuidance(accessToken),
      ])

      if (cancelled) return

      setRiskSummary({
        loading: false,
        data: riskResult.status === 'fulfilled' ? riskResult.value : null,
      })
      setGuidanceSummary({
        loading: false,
        data: guidanceResult.status === 'fulfilled' ? guidanceResult.value : null,
      })
    }

    loadSummaries()
    return () => {
      cancelled = true
    }
  }, [accessToken])

  const latestAlerts = useMemo(() => (realtime.liveEvents || []).slice(0, 3), [realtime.liveEvents])

  return (
    <Dashboard
      analysis={analysis}
      financialScore={financialScore}
      fraudCheck={fraudCheck}
      riskSummary={riskSummary.data}
      guidanceSummary={guidanceSummary.data}
      realtimeConnectionStatus={realtime.connectionStatus}
      realtimeAlerts={latestAlerts}
      realtimeAlertCount={realtime.liveEvents.length}
      onDismissAlert={realtime.dismissEvent}
      onNavigate={onNavigate}
    />
  )
}
