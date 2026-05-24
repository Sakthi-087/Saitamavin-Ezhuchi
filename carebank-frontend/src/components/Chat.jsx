import { useEffect, useRef, useState } from 'react'
import { sendChat } from '../services/api'
import StatusBadge from './ui/StatusBadge'

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

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape') setIsOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  useEffect(() => {
    if (isOpen) inputRef.current?.focus()
  }, [isOpen])

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

  const lastMessage = messages[messages.length - 1]
  const lastMeta = lastMessage?.role === 'assistant' ? lastMessage.meta : null

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="fixed bottom-5 right-5 z-40 h-14 w-14 rounded-full bg-slate-900 text-sm font-bold text-white shadow-2xl hover:bg-slate-800"
        aria-label="Open Copilot"
      >
        AI
      </button>

      {isOpen ? (
        <div className="fixed bottom-24 right-5 z-40 w-[calc(100vw-2rem)] max-w-[380px] rounded-2xl border border-slate-200 bg-white shadow-2xl sm:w-[380px]">
          <div className="flex items-center justify-between border-b border-slate-200 p-3">
            <p className="font-semibold text-slate-900">CareBank Copilot</p>
            <button type="button" onClick={() => setIsOpen(false)} className="rounded-lg px-2 py-1 text-xs text-slate-600 hover:bg-slate-100">Close</button>
          </div>

          <div className="space-y-3 p-3">
            <div className="max-h-[20rem] space-y-3 overflow-y-auto rounded-xl bg-slate-50 p-3">
              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-6 shadow-sm ${
                      message.role === 'user' ? 'bg-blue-600 text-white' : 'bg-white text-slate-700'
                    }`}
                  >
                    {message.content}
                    {message.meta ? (
                      <div className="mt-2">
                        <button
                          type="button"
                          className="text-xs font-semibold text-cyan-700"
                          onClick={() => setShowMetaIndex((current) => (current === index ? -1 : index))}
                        >
                          Why this answer?
                        </button>
                        {showMetaIndex === index ? (
                          <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
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

            {lastMeta ? (
              <div className="flex flex-wrap gap-2">
                <StatusBadge label={lastMeta.safety_status} tone={lastMeta.fallback_used ? 'warning' : 'good'} />
                <StatusBadge label={lastMeta.intent} tone="neutral" />
              </div>
            ) : null}

            <form onSubmit={handleSubmit} className="flex flex-col gap-2">
              <input
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Why did I spend more this month?"
                className="min-h-11 flex-1 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none focus:border-blue-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-60"
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
