import { useEffect, useMemo, useRef, useState } from 'react'
import { sendChat } from '../services/api'
import StatusBadge from './ui/StatusBadge'

const SUGGESTIONS = [
  'Why is my risk high?',
  'How can I improve my score?',
  'Explain my behavior drift',
  'What should I cut this month?',
]

export default function Chat({ accessToken }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! Ask why your spending increased, what your biggest risk is, or how to save more this month.',
      meta: null,
    },
  ])
  const [input, setInput] = useState('Why did I spend more this month?')
  const [loading, setLoading] = useState(false)
  const [showMetaIndex, setShowMetaIndex] = useState(-1)
  const inputRef = useRef(null)
  const panelRef = useRef(null)

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape') setIsOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  useEffect(() => {
    function onOpenCopilot(event) {
      const prompt = event?.detail?.prompt
      if (typeof prompt === 'string' && prompt.trim()) {
        setInput(prompt.trim())
      }
      setIsOpen(true)
    }

    window.addEventListener('carebank:open-copilot', onOpenCopilot)
    return () => window.removeEventListener('carebank:open-copilot', onOpenCopilot)
  }, [])

  useEffect(() => {
    if (isOpen) inputRef.current?.focus()
  }, [isOpen])

  const conversationSummary = useMemo(() => {
    const assistantReplies = messages.filter((message) => message.role === 'assistant').length
    return {
      total: messages.length,
      replies: assistantReplies,
      latestMeta: [...messages].reverse().find((message) => message.role === 'assistant' && message.meta)?.meta || null,
    }
  }, [messages])

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!input.trim() || loading) return

    const nextMessage = { role: 'user', content: input.trim() }
    setMessages((current) => [...current, nextMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await sendChat(nextMessage.content, accessToken)
      const safeCopilot = response.copilot
        ? {
            intent: response.copilot.intent || 'general_financial_question',
            confidence: Number(response.copilot.confidence ?? 0),
            evidence_keys: Array.isArray(response.copilot.evidence_keys) ? response.copilot.evidence_keys.slice(0, 8) : [],
            limitations: Array.isArray(response.copilot.limitations) ? response.copilot.limitations.slice(0, 5) : [],
            safety_status: response.copilot.safety_status || 'ok',
            fallback_used: Boolean(response.copilot.fallback_used),
          }
        : null
      setMessages((current) => [...current, { role: 'assistant', content: response.answer, meta: safeCopilot }])
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: error.message || 'The backend could not be reached. Please verify your API and Supabase settings.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const applySuggestion = (prompt) => {
    setInput(prompt)
    setIsOpen(true)
    queueMicrotask(() => inputRef.current?.focus())
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="fixed bottom-5 right-5 z-40 flex h-16 items-center gap-3 rounded-full border border-white/80 bg-slate-950 px-4 text-sm font-semibold text-white shadow-[0_22px_50px_rgba(15,23,42,0.28)] hover:bg-slate-900"
        aria-label="Open Copilot"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-lg shadow-blue-900/20">
          AI
        </span>
        <span className="hidden sm:block">Copilot</span>
      </button>

      {isOpen ? (
        <div
          ref={panelRef}
          className="fixed bottom-24 right-5 z-40 w-[calc(100vw-1.5rem)] max-w-[420px] overflow-hidden rounded-[30px] border border-slate-200/80 bg-white/95 shadow-[0_30px_80px_rgba(15,23,42,0.22)] backdrop-blur sm:w-[420px]"
        >
          <div className="bg-hero-gradient p-4 text-white">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200">Floating AI assistant</p>
                <p className="mt-2 text-lg font-semibold">CareBank Copilot</p>
              </div>
              <button type="button" onClick={() => setIsOpen(false)} className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold text-white hover:bg-white/20">
                Close
              </button>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
              <div className="rounded-[18px] border border-white/15 bg-white/10 p-3">
                <p className="text-white/70">Messages</p>
                <p className="mt-1 text-lg font-semibold">{conversationSummary.total}</p>
              </div>
              <div className="rounded-[18px] border border-white/15 bg-white/10 p-3">
                <p className="text-white/70">Replies</p>
                <p className="mt-1 text-lg font-semibold">{conversationSummary.replies}</p>
              </div>
              <div className="rounded-[18px] border border-white/15 bg-white/10 p-3">
                <p className="text-white/70">Safety</p>
                <p className="mt-1 text-lg font-semibold">{conversationSummary.latestMeta?.safety_status || 'ok'}</p>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <StatusBadge label={conversationSummary.latestMeta?.intent || 'general'} tone="info" />
              <StatusBadge label={conversationSummary.latestMeta?.fallback_used ? 'Fallback used' : 'Primary answer'} tone={conversationSummary.latestMeta?.fallback_used ? 'warning' : 'good'} />
            </div>
          </div>

          <div className="space-y-4 p-4">
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => applySuggestion(prompt)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-100"
                >
                  {prompt}
                </button>
              ))}
            </div>

            <div className="max-h-[24rem] space-y-3 overflow-y-auto rounded-[24px] bg-slate-50/80 p-4 scrollbar-thin">
              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[88%] rounded-[24px] px-4 py-3 text-sm leading-6 shadow-sm ${
                      message.role === 'user' ? 'bg-slate-950 text-white' : 'bg-white text-slate-700'
                    }`}
                  >
                    {message.content}
                    {message.meta ? (
                      <div className="mt-3">
                        <button
                          type="button"
                          className="text-xs font-semibold text-blue-700"
                          onClick={() => setShowMetaIndex((current) => (current === index ? -1 : index))}
                        >
                          Why this answer?
                        </button>
                        {showMetaIndex === index ? (
                          <div className="mt-2 space-y-1 rounded-[18px] border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                            <p>Intent: {message.meta.intent}</p>
                            <p>Confidence: {Number(message.meta.confidence ?? 0).toFixed(2)}</p>
                            <p>Safety: {message.meta.safety_status}</p>
                            <p>Fallback used: {message.meta.fallback_used ? 'Yes' : 'No'}</p>
                            {message.meta.evidence_keys?.length ? <p>Evidence keys: {message.meta.evidence_keys.join(', ')}</p> : null}
                            {message.meta.limitations?.length ? <p>Limitations: {message.meta.limitations.join('; ')}</p> : null}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>

            <form onSubmit={handleSubmit} className="space-y-3">
              <input
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Why did I spend more this month?"
                className="min-h-12 w-full rounded-[18px] border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none focus:border-blue-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-[18px] bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-900/10 hover:bg-slate-900 disabled:opacity-60"
              >
                {loading ? 'Sending...' : 'Send'}
              </button>
            </form>
          </div>
        </div>
      ) : null}
    </>
  )
}
