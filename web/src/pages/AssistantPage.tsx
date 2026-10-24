import { useEffect, useRef, useState } from 'react'
import { Send, Sparkles } from 'lucide-react'
import { api, store } from '../lib/api'
import type { AiResult } from '../lib/types'
import { AiSource, RichText, Spinner } from '../components/ui'

type Msg = { role: 'user' | 'assistant'; text: string; meta?: AiResult }

const SUGGESTIONS = [
  'My driver stopped and nobody is moving. What should I do?',
  'The driver took a different road than the map. Is that normal?',
  'How do I check that the car is the right one?',
  'What happens when I press "I need help"?',
  'The driver is asking me to pay extra cash.',
]

export default function AssistantPage() {
  const tripId = store<string | null>('mz.trip', null)
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      role: 'assistant',
      text: "Hi, I'm the MzansiRide safety assistant. Ask me about your trip, our safety alerts, or what to do if something feels wrong.\n\nIf you're in danger right now, call **10111** or **112**.",
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth' }), [msgs])

  async function send(text: string) {
    if (!text.trim() || busy) return
    const history = msgs.slice(1).map((m) => ({ role: m.role, text: m.text }))
    setMsgs((m) => [...m, { role: 'user', text }])
    setInput('')
    setBusy(true)
    try {
      const r = await api.assistant(text, tripId ?? undefined, history)
      setMsgs((m) => [...m, { role: 'assistant', text: r.text, meta: r }])
    } catch (e) {
      setMsgs((m) => [...m, { role: 'assistant', text: `Sorry, something went wrong (${(e as Error).message}). If you're in danger call 10111 or 112.` }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col" style={{ minHeight: 'calc(100vh - 11rem)' }}>
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="text-brand-600" />
        <h1 className="text-xl font-extrabold">Safety assistant</h1>
        <span className="ml-auto text-xs text-slate-500">Amazon Bedrock · grounded in approved guidance{tripId ? ` · trip ${tripId}` : ''}</span>
      </div>
      <div className="card flex-1 space-y-3 overflow-y-auto p-4">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${m.role === 'user' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-900'}`}>
              <RichText text={m.text} />
              {m.meta && <AiSource source={m.meta.source} model={m.meta.model} />}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner /> Thinking…
          </div>
        )}
        <div ref={end} />
      </div>
      {msgs.length < 3 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium hover:border-brand-400" onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <input className="input" placeholder="Describe your situation…" value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000} />
        <button className="btn-primary" disabled={busy || !input.trim()} aria-label="Send">
          <Send size={18} />
        </button>
      </form>
      <p className="mt-2 text-center text-[11px] text-slate-500">The assistant gives guidance only. It can't see you, call anyone, or know whether you're safe.</p>
    </div>
  )
}
