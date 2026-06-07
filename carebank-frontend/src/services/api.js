const ENV_API_URL = import.meta.env.VITE_API_URL?.trim()

function isLocalHostname(hostname = '') {
  return hostname === 'localhost' || hostname === '127.0.0.1'
}

function resolveLocalBackendUrl() {
  if (typeof window === 'undefined') {
    return 'http://127.0.0.1:8000'
  }

  const { protocol, hostname } = window.location
  const localProtocol = protocol === 'https:' ? 'https:' : 'http:'

  if (isLocalHostname(hostname)) {
    return `${localProtocol}//${hostname}:8000`
  }

  return 'http://127.0.0.1:8000'
}

function resolveApiBaseUrl() {
  if (import.meta.env.DEV) {
    return resolveLocalBackendUrl()
  }

  if (ENV_API_URL) {
    return ENV_API_URL
  }

  return typeof window !== 'undefined' && isLocalHostname(window.location.hostname)
    ? resolveLocalBackendUrl()
    : 'http://localhost:8000'
}

const API_BASE_URL = resolveApiBaseUrl()
const DEFAULT_TIMEOUT_MS = 60000

function mapSafeErrorMessage(status) {
  if (status === 401 || status === 403) return 'Your session has expired. Please sign in again.'
  if (status === 404) return 'The requested resource is not available right now.'
  if (status === 429) return 'Too many requests. Please wait a moment and try again.'
  if (status >= 500) return 'The server is temporarily unavailable. Please try again.'
  return 'We could not complete this request. Please try again.'
}

function toRealtimeUrl(baseUrl, userId, ticket) {
  const url = new URL(baseUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `/ws/${encodeURIComponent(userId)}`
  url.searchParams.set('ticket', ticket)
  return url.toString()
}

async function apiRequest(path, { accessToken, timeoutMs = DEFAULT_TIMEOUT_MS, ...options } = {}) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  const headers = new Headers(options.headers || {})
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    })
  } catch (error) {
    clearTimeout(timeoutId)
    if (error?.name === 'AbortError') {
      const timeoutError = new Error('The request took too long to complete. Please try again.')
      timeoutError.isTimeoutError = true
      throw timeoutError
    }

    const networkError = new Error('Network connection failed. Please check your connection and try again.')
    networkError.isNetworkError = true
    throw networkError
  } finally {
    clearTimeout(timeoutId)
  }

  if (!response.ok) {
    let detail = mapSafeErrorMessage(response.status)
    try {
      const payload = await response.json()
      if (typeof payload?.detail === 'string' && payload.detail.length < 180) {
        detail = payload.detail
      }
    } catch {
      // Keep sanitized message when parsing fails.
    }
    const error = new Error(detail)
    error.status = response.status
    error.isAuthError = response.status === 401 || response.status === 403
    throw error
  }

  return response.json()
}

export function fetchAnalysis(accessToken) {
  return apiRequest('/analyze', { accessToken })
}

export function fetchFinancialScore(accessToken) {
  return apiRequest('/financial-score', { accessToken })
}

export function fetchBehaviorAnalysis(accessToken) {
  return apiRequest('/behavior-analysis', { accessToken })
}

export function fetchRiskAnalysis(accessToken) {
  return apiRequest('/risk-analysis', { accessToken })
}

export function fetchGuidance(accessToken) {
  return apiRequest('/guidance', { accessToken })
}

export function fetchFraudCheck(accessToken) {
  return apiRequest('/fraud-check', { accessToken })
}

export function sendChat(message, accessToken) {
  return apiRequest('/chat', {
    method: 'POST',
    accessToken,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
  })
}

export function simulateDecision(payload, accessToken) {
  return apiRequest('/simulate', {
    method: 'POST',
    accessToken,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
}

export function fetchHealth() {
  return apiRequest('/health')
}

function withLimit(path, limit) {
  const bounded = Math.max(1, Math.min(Number(limit) || 25, 200))
  return `${path}?limit=${bounded}`
}

export function fetchFinancialScoreHistory(accessToken, limit = 25) {
  return apiRequest(withLimit('/history/financial-scores', limit), { accessToken })
}

export function fetchRiskEventHistory(accessToken, limit = 25) {
  return apiRequest(withLimit('/history/risk-events', limit), { accessToken })
}

export function fetchGuidanceHistory(accessToken, limit = 25) {
  return apiRequest(withLimit('/history/guidance-items', limit), { accessToken })
}

export function fetchBehaviorSnapshotHistory(accessToken, limit = 25) {
  return apiRequest(withLimit('/history/behavior-snapshots', limit), { accessToken })
}

export function fetchAuditEventHistory(accessToken, limit = 25) {
  return apiRequest(withLimit('/history/audit-events', limit), { accessToken })
}

export function fetchPreferences(accessToken) {
  return apiRequest('/preferences', { accessToken })
}

export function savePreferences(preferences, accessToken) {
  return apiRequest('/preferences', {
    method: 'PUT',
    accessToken,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(preferences),
  })
}

export function uploadTransactionsCsv(file, accessToken) {
  const formData = new FormData()
  formData.append('file', file)

  return apiRequest('/transactions/upload-csv', {
    method: 'POST',
    accessToken,
    body: formData,
  })
}

export function createManualTransaction(payload, accessToken) {
  return apiRequest('/transactions/manual', {
    method: 'POST',
    accessToken,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
}

export function requestRealtimeTicket(accessToken) {
  return apiRequest('/realtime/ws-ticket', {
    method: 'POST',
    accessToken,
  })
}

export function connectRealtime(userId, ticket, handlers = {}) {
  const ws = new WebSocket(toRealtimeUrl(API_BASE_URL, userId, ticket))
  const { onOpen, onClose, onError, onMessage } = handlers

  ws.onopen = (event) => {
    if (typeof onOpen === 'function') onOpen(event)
  }
  ws.onclose = (event) => {
    if (typeof onClose === 'function') onClose(event)
  }
  ws.onerror = (event) => {
    if (typeof onError === 'function') onError(event)
  }
  ws.onmessage = (event) => {
    if (typeof onMessage === 'function') onMessage(event)
  }

  return ws
}
