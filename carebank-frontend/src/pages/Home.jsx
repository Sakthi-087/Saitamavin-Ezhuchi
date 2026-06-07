import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import AuthScreen from '../components/AuthScreen'
import Sidebar from '../components/Sidebar'
import Chat from '../components/Chat'
import LoadingSkeleton from '../components/ui/LoadingSkeleton'
import ErrorCard from '../components/ui/ErrorCard'
import StatusBadge from '../components/ui/StatusBadge'
import {
  createManualTransaction,
  fetchAnalysis,
  fetchFinancialScore,
  fetchFraudCheck,
  fetchHealth,
  fetchPreferences,
  savePreferences,
  uploadTransactionsCsv,
} from '../services/api'
import { requestPasswordReset, restoreSession, signIn, signOut, signUp } from '../services/auth'

const DashboardPage = lazy(() => import('./DashboardPage'))
const Analytics = lazy(() => import('./Analytics'))
const AIAssistant = lazy(() => import('./AIAssistant'))
const Settings = lazy(() => import('./Settings'))
const History = lazy(() => import('./History'))
const BehaviorPage = lazy(() => import('./BehaviorPage'))
const RiskPage = lazy(() => import('./RiskPage'))
const GuidancePage = lazy(() => import('./GuidancePage'))

const routeMeta = {
  dashboard: {
    eyebrow: 'CareBank Command Center',
    title: 'Executive Overview',
    description: 'A single-screen summary of financial health, risk posture, guidance, and live alerts.',
  },
  behavior: {
    eyebrow: 'Behavior Intelligence',
    title: 'Behavior Drift & Recurrence',
    description: 'Monitor rolling spend windows, drift severity, anomalies, and recurring merchant behavior.',
  },
  risk: {
    eyebrow: 'Risk Intelligence',
    title: 'Risk Events & Recommendations',
    description: 'Review deterministic risk events, severity, confidence, and recommended next actions.',
  },
  guidance: {
    eyebrow: 'Guidance Inbox',
    title: 'Actionable Financial Recommendations',
    description: 'Prioritized steps mapped directly to score, behavior, and risk intelligence signals.',
  },
  history: {
    eyebrow: 'History Workspace',
    title: 'Snapshots & Event History',
    description: 'Trace score, risk, behavior, guidance, and sanitized audit history.',
  },
  analytics: {
    eyebrow: 'Score Intelligence',
    title: 'Explainable Scoring Deep Dive',
    description: 'Break down savings, stability, discipline, and risk components with deterministic evidence.',
  },
  assistant: {
    eyebrow: 'Decision Lab',
    title: 'Simulate Before You Spend',
    description: 'Run projected impact simulations before major spending decisions.',
  },
  settings: {
    eyebrow: 'Data Controls',
    title: 'Ingestion & Preferences',
    description: 'Upload transactions, manage manual entries, and control workspace preferences.',
  },
}

function getRouteFromHash() {
  const raw = window.location.hash.replace('#/', '').trim()
  return raw || 'dashboard'
}

export default function Home() {
  const [session, setSession] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [analysis, setAnalysis] = useState(null)
  const [financialScore, setFinancialScore] = useState(null)
  const [fraudCheck, setFraudCheck] = useState({ flagged_transactions: [] })
  const [moduleErrors, setModuleErrors] = useState({ analysis: '', score: '', fraud: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [authNotice, setAuthNotice] = useState('')
  const [route, setRoute] = useState(getRouteFromHash())
  const [uploading, setUploading] = useState(false)
  const [manualSaving, setManualSaving] = useState(false)
  const [uploadState, setUploadState] = useState(null)
  const [preferences, setPreferences] = useState({
    overspending_alerts: true,
    weekly_wellness_summary: true,
    ai_assistant_tips: false,
  })
  const [preferencesSaving, setPreferencesSaving] = useState(false)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    function syncRoute() {
      const nextRoute = getRouteFromHash()
      setRoute(routeMeta[nextRoute] ? nextRoute : 'dashboard')
    }

    syncRoute()
    window.addEventListener('hashchange', syncRoute)
    return () => window.removeEventListener('hashchange', syncRoute)
  }, [])

  useEffect(() => {
    async function bootstrapSession() {
      try {
        const { session: restored, notice } = await restoreSession()
        setSession(restored)
        setAuthNotice(notice || '')
      } catch (nextError) {
        setError(nextError.message || 'Unable to restore your session.')
      } finally {
        setAuthLoading(false)
      }
    }

    bootstrapSession()
  }, [])

  async function loadWorkspace(accessToken) {
    setLoading(true)
    setError('')

    const [analysisData, scoreData, fraudData] = await Promise.allSettled([
      fetchAnalysis(accessToken),
      fetchFinancialScore(accessToken),
      fetchFraudCheck(accessToken),
    ])

    const nextErrors = { analysis: '', score: '', fraud: '' }

    if (analysisData.status === 'fulfilled') {
      setAnalysis(analysisData.value)
    } else {
      setAnalysis(null)
      nextErrors.analysis = analysisData.reason?.message || 'Analysis is unavailable.'
    }

    if (scoreData.status === 'fulfilled') {
      setFinancialScore(scoreData.value)
    } else {
      setFinancialScore(null)
      nextErrors.score = scoreData.reason?.message || 'Financial score is unavailable.'
    }

    if (fraudData.status === 'fulfilled') {
      setFraudCheck(fraudData.value)
    } else {
      setFraudCheck({ flagged_transactions: [] })
      nextErrors.fraud = fraudData.reason?.message || 'Fraud checks are unavailable.'
    }

    const authError = [analysisData, scoreData, fraudData]
      .filter((item) => item.status === 'rejected')
      .map((item) => item.reason)
      .find((reason) => reason?.isAuthError)

    if (authError) {
      await signOut(session)
      setSession(null)
      setAuthNotice('Your session expired while loading the workspace. Please sign in again.')
      setLoading(false)
      return
    }

    setModuleErrors(nextErrors)
    if (nextErrors.analysis && nextErrors.score && nextErrors.fraud) {
      setError('Core workspace modules could not be loaded. Retry to continue.')
    }

    setLoading(false)
  }

  useEffect(() => {
    if (!session?.access_token) {
      setAnalysis(null)
      setFinancialScore(null)
      setFraudCheck({ flagged_transactions: [] })
      setModuleErrors({ analysis: '', score: '', fraud: '' })
      setLoading(false)
      return
    }

    loadWorkspace(session.access_token)
  }, [session?.access_token])

  useEffect(() => {
    async function loadHealth() {
      try {
        const payload = await fetchHealth()
        setHealth(payload)
      } catch {
        setHealth(null)
      }
    }

    loadHealth()
  }, [])

  useEffect(() => {
    if (!session?.access_token) {
      setPreferences({
        overspending_alerts: true,
        weekly_wellness_summary: true,
        ai_assistant_tips: false,
      })
      return
    }

    async function loadSavedPreferences() {
      try {
        const payload = await fetchPreferences(session.access_token)
        setPreferences(payload.preferences)
      } catch (nextError) {
        if (nextError.isAuthError) {
          await signOut(session)
          setSession(null)
          setAuthNotice('Your session expired while loading preferences. Please sign in again.')
        }
      }
    }

    loadSavedPreferences()
  }, [session?.access_token])

  const pageMeta = routeMeta[route] || routeMeta.dashboard
  const workspaceHealthTone = health?.status === 'ok' ? 'good' : health?.status ? 'warning' : 'neutral'

  const handleNavigate = (nextRoute) => {
    window.location.hash = `/${nextRoute}`
  }

  const moduleErrorCards = (
    <div className="grid gap-3 lg:grid-cols-3">
      {moduleErrors.analysis ? <ErrorCard title="Analysis module" message={moduleErrors.analysis} onRetry={() => loadWorkspace(session?.access_token)} compact /> : null}
      {moduleErrors.score ? <ErrorCard title="Financial score module" message={moduleErrors.score} onRetry={() => loadWorkspace(session?.access_token)} compact /> : null}
      {moduleErrors.fraud ? <ErrorCard title="Fraud module" message={moduleErrors.fraud} onRetry={() => loadWorkspace(session?.access_token)} compact /> : null}
    </div>
  )

  const pageContent = useMemo(() => {
    if (route === 'settings') {
      return (
        <Settings
          uploading={uploading}
          manualSaving={manualSaving}
          uploadState={uploadState}
          fraudCheck={fraudCheck}
          onUpload={handleUpload}
          onManualCreate={handleManualCreate}
          preferences={preferences}
          preferencesSaving={preferencesSaving}
          onTogglePreference={handleTogglePreference}
        />
      )
    }

    if (route === 'history') return <History accessToken={session.access_token} />
    if (route === 'behavior') return <BehaviorPage accessToken={session.access_token} />
    if (route === 'risk') return <RiskPage accessToken={session.access_token} />
    if (route === 'guidance') return <GuidancePage accessToken={session.access_token} />

    if (route === 'analytics') {
      if (!analysis || !financialScore) return moduleErrorCards
      return <Analytics analysis={analysis} financialScore={financialScore} fraudCheck={fraudCheck} />
    }

    if (route === 'assistant') {
      if (!analysis || !financialScore) return moduleErrorCards
      return <AIAssistant analysis={analysis} financialScore={financialScore} fraudCheck={fraudCheck} accessToken={session.access_token} />
    }

    if (!analysis || !financialScore) return moduleErrorCards

    return (
      <DashboardPage
        analysis={analysis}
        financialScore={financialScore}
        fraudCheck={fraudCheck}
        accessToken={session.access_token}
        userId={session.user?.id}
        onNavigate={handleNavigate}
      />
    )
  }, [analysis, financialScore, fraudCheck, preferences, preferencesSaving, route, session, uploading, uploadState, moduleErrors])

  async function handleSignIn(email, password) {
    const nextSession = await signIn(email, password)
    setSession(nextSession)
    setAuthNotice('')
    return nextSession
  }

  async function handleSignUp(email, password) {
    const result = await signUp(email, password)
    if (result.session) {
      setSession(result.session)
      setAuthNotice('')
    }
    return result
  }

  async function handleSignOut() {
    await signOut(session)
    setSession(null)
    setAnalysis(null)
    setFinancialScore(null)
    setFraudCheck({ flagged_transactions: [] })
    setUploadState(null)
    setAuthNotice('')
  }

  async function handlePasswordReset(email) {
    return requestPasswordReset(email)
  }

  async function handleUpload(file) {
    if (!file || !session?.access_token) return

    setUploading(true)
    setUploadState(null)

    try {
      const result = await uploadTransactionsCsv(file, session.access_token)
      setUploadState({
        tone: 'success',
        message: `Imported ${result.inserted_count} rows. Skipped ${result.skipped_count}.`,
        errors: result.errors,
        fraudSummary: result.fraud_summary || [],
      })
      await loadWorkspace(session.access_token)
    } catch (nextError) {
      setUploadState({
        tone: 'error',
        message: nextError.message || 'CSV upload failed.',
        errors: [],
        fraudSummary: [],
      })
    } finally {
      setUploading(false)
    }
  }

  async function handleManualCreate(payload) {
    if (!session?.access_token) return

    setManualSaving(true)
    setUploadState(null)

    try {
      const result = await createManualTransaction(payload, session.access_token)
      setUploadState({
        tone: 'success',
        message: 'Manual transaction saved successfully.',
        errors: [],
        fraudSummary: result.fraud_summary || [],
      })
      await loadWorkspace(session.access_token)
    } catch (nextError) {
      setUploadState({
        tone: 'error',
        message: nextError.message || 'Unable to save the transaction.',
        errors: [],
        fraudSummary: [],
      })
    } finally {
      setManualSaving(false)
    }
  }

  async function handleTogglePreference(key) {
    if (!session?.access_token || preferencesSaving) return

    const currentPreferences = preferences
    const nextPreferences = {
      ...currentPreferences,
      [key]: !currentPreferences[key],
    }

    setPreferences(nextPreferences)
    setPreferencesSaving(true)

    try {
      const payload = await savePreferences(nextPreferences, session.access_token)
      setPreferences(payload.preferences)
    } catch (nextError) {
      if (nextError.isAuthError) {
        await signOut(session)
        setSession(null)
        setAuthNotice('Your session expired while saving preferences. Please sign in again.')
      }
      setPreferences(currentPreferences)
      setError(nextError.message || 'Unable to save your notification preferences.')
    } finally {
      setPreferencesSaving(false)
    }
  }

  if (authLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 text-slate-600">
        Restoring your CareBank session...
      </main>
    )
  }

  if (!session) {
    return <AuthScreen onSignIn={handleSignIn} onSignUp={handleSignUp} onResetPassword={handlePasswordReset} notice={authNotice} />
  }

  return (
    <main className="min-h-screen bg-app-shell px-4 py-6 text-slate-900 sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-[1520px] gap-6 xl:grid-cols-[296px_1fr]">
        <Sidebar activeRoute={route} onNavigate={handleNavigate} session={session} onSignOut={handleSignOut} />

        <section className="space-y-6">
          <header className="overflow-hidden rounded-[32px] border border-white/70 bg-hero-gradient p-6 text-white shadow-[0_24px_70px_rgba(15,23,42,0.16)]">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm font-semibold uppercase tracking-[0.24em] text-cyan-100">{pageMeta.eyebrow}</p>
                  <StatusBadge label={health?.status || 'checking'} tone={workspaceHealthTone} />
                </div>
                <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight lg:text-[2.75rem]">{pageMeta.title}</h1>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-blue-50">{pageMeta.description}</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-[24px] border border-white/20 bg-white/10 px-4 py-4 backdrop-blur">
                  <p className="text-xs uppercase tracking-[0.22em] text-cyan-100">Score</p>
                  <p className="mt-2 text-2xl font-semibold">{financialScore?.score ?? '--'}</p>
                </div>
                <div className="rounded-[24px] border border-white/20 bg-white/10 px-4 py-4 backdrop-blur">
                  <p className="text-xs uppercase tracking-[0.22em] text-cyan-100">Status</p>
                  <p className="mt-2 text-2xl font-semibold">{financialScore?.status || '--'}</p>
                </div>
                <div className="rounded-[24px] border border-white/20 bg-white/10 px-4 py-4 backdrop-blur">
                  <p className="text-xs uppercase tracking-[0.22em] text-cyan-100">Fraud flags</p>
                  <p className="mt-2 text-2xl font-semibold">{fraudCheck?.flagged_transactions?.length ?? 0}</p>
                </div>
              </div>
            </div>
          </header>

          {loading ? (
            <LoadingSkeleton lines={8} />
          ) : error ? (
            <ErrorCard title="Workspace unavailable" message={error} onRetry={() => loadWorkspace(session?.access_token)} />
          ) : (
            <Suspense fallback={<LoadingSkeleton lines={8} />}>
              {pageContent}
            </Suspense>
          )}
        </section>
      </div>

      <Chat accessToken={session.access_token} />
    </main>
  )
}
