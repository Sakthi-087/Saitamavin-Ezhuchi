import Dashboard from '../components/Dashboard'
import ScoreExplainabilityPanel from '../components/ScoreExplainabilityPanel'
import BehaviorDriftPanel from '../components/BehaviorDriftPanel'
import RiskIntelligencePanel from '../components/RiskIntelligencePanel'
import GuidanceInbox from '../components/GuidanceInbox'
import RealtimeAlertCenter from '../components/RealtimeAlertCenter'
import useRealtimeAlerts from '../hooks/useRealtimeAlerts'

export default function DashboardPage({ analysis, financialScore, fraudCheck, accessToken, userId }) {
  const realtime = useRealtimeAlerts({ userId, accessToken, enabled: Boolean(userId && accessToken) })

  return (
    <div className="space-y-6">
      <Dashboard analysis={analysis} financialScore={financialScore} fraudCheck={fraudCheck} />
      <ScoreExplainabilityPanel score={financialScore} />
      <BehaviorDriftPanel accessToken={accessToken} />
      <RiskIntelligencePanel accessToken={accessToken} />
      <GuidanceInbox accessToken={accessToken} />
      <RealtimeAlertCenter
        connectionStatus={realtime.connectionStatus}
        liveEvents={realtime.liveEvents}
        onDismiss={realtime.dismissEvent}
      />
    </div>
  )
}
