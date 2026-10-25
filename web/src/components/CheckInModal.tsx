import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Phone, Send, ShieldAlert, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import type { AiResult, CheckinReply, SafetyEvent } from '../lib/types'
import { AiSource, RichText, SimBadge, Spinner } from './ui'
import { EVENT_LABEL, describe, fmtDuration } from '../lib/format'

export default function CheckInModal({
  event,
  tripTs,
  timeoutS,
  promptStartedAt,
  onRespond,
  onReplied,
}: {
  event: SafetyEvent
  tripTs: number
  timeoutS: number
  promptStartedAt: number
  onRespond: (response: 'ok' | 'help', promptMs: number) => Promise<void>
  onReplied: (r: CheckinReply) => void
}) {
  const [ai, setAi] = useState<AiResult | null>(null)
  const [busy, setBusy] = useState<'ok' | 'help' | 'text' | null>(null)
  const [text, setText] = useState('')
  const [unclear, setUnclear] = useState('')
  const promptMs = useRef<number>(0)

  useEffect(() => {
    // "time taken to display a safety prompt" (proposal section 9): tick sent -> modal on screen
    promptMs.current = Math.round(performance.now() - promptStartedAt)
  }, [promptStartedAt])

  useEffect(() => {
    let live = true
    api.explain(event.trip_id, event.event_id).then((r) => live && setAi(r)).catch(() => live && setAi({ text: '', source: 'fallback', model: null }))
    return () => {
      live = false
    }
  }, [event.trip_id, event.event_id])

  const left = timeoutS - (tripTs - (event.trip_ts ?? tripTs))
  const escalated = event.status === 'escalated'

  async function respond(r: 'ok' | 'help') {
    setBusy(r)
    try {
      await onRespond(r, promptMs.current)
    } finally {
      setBusy(null)
    }
  }

  async function sendText(e: React.FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    setBusy('text')
    try {
      const r = await api.reply(event.trip_id, event.event_id, text)
      if (r.intent === 'unclear') {
        setUnclear("Sorry, I wasn't sure what you meant. Tap I'm OK or I need help, so we don't guess.")
        setText('')
      } else onReplied(r)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fixed inset-0 z-[2000] flex items-end justify-center bg-slate-900/60 p-0 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-labelledby="checkin-title">
      <div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-3xl bg-white p-5 shadow-2xl sm:rounded-3xl">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
            <AlertTriangle />
          </div>
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="checkin-title" className="text-lg font-extrabold">Are you OK?</h2>
              <SimBadge label="Simulated alert" />
            </div>
            <p className="text-sm font-semibold text-slate-700">
              {EVENT_LABEL[event.type]}: {describe(event)}
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-brand-100 bg-brand-50/60 p-4 text-sm leading-relaxed text-slate-800">
          <p className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-brand-700">
            <Sparkles size={14} /> Safety assistant
          </p>
          {ai ? (
            <>
              <RichText text={ai.text || "This alert asks you to confirm you're OK. There may be a normal reason, like traffic. Choose an option below."} />
              <AiSource source={ai.source} model={ai.model} />
            </>
          ) : (
            <div className="space-y-2 py-1">
              <div className="h-3 w-11/12 animate-pulse rounded bg-brand-100" />
              <div className="h-3 w-9/12 animate-pulse rounded bg-brand-100" />
              <div className="h-3 w-10/12 animate-pulse rounded bg-brand-100" />
            </div>
          )}
        </div>

        {escalated ? (
          <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm font-semibold text-red-800">
            No response received, so your trusted contact has been notified. You can still tell us you're OK.
          </p>
        ) : (
          <p className="mt-3 text-center text-xs text-slate-500">
            If you don't answer, your trusted contact is alerted automatically in <strong>{fmtDuration(Math.max(0, left))}</strong> (trip time).
          </p>
        )}

        <div className="mt-4 grid grid-cols-2 gap-3">
          <button className="btn-primary py-3.5 text-base" onClick={() => respond('ok')} disabled={!!busy}>
            {busy === 'ok' ? <Spinner /> : <CheckCircle2 size={20} />} I'm OK
          </button>
          <button className="btn-danger py-3.5 text-base" onClick={() => respond('help')} disabled={!!busy || escalated}>
            {busy === 'help' ? <Spinner /> : <ShieldAlert size={20} />} I need help
          </button>
        </div>
        <form onSubmit={sendText} className="mt-3">
          <label className="text-xs font-semibold text-slate-600" htmlFor="checkin-text">
            Or tell us what's happening
          </label>
          <div className="mt-1 flex gap-2">
            <input
              id="checkin-text"
              className="input"
              placeholder="e.g. We took a detour, still going to Sandton"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={300}
            />
            <button className="btn-secondary shrink-0" disabled={!text.trim() || !!busy} aria-label="Send reply">
              {busy === 'text' ? <Spinner /> : <Send size={16} />}
            </button>
          </div>
          {unclear && <p className="mt-1 text-xs font-semibold text-amber-800">{unclear}</p>}
          <p className="mt-1 text-[11px] text-slate-500">AI reads your words. If it isn't sure, it asks again: it never assumes you're OK.</p>
        </form>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <a className="btn-secondary" href="tel:10111">
            <Phone size={16} /> SAPS 10111
          </a>
          <a className="btn-secondary" href="tel:112">
            <Phone size={16} /> Emergency 112
          </a>
        </div>
        <p className="mt-3 text-center text-[11px] text-slate-500">This is a check-in, not an accusation: stops and detours often have normal reasons.</p>
      </div>
    </div>
  )
}
