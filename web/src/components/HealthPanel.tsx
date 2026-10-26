import { useEffect, useState } from 'react'
import { Activity, Bot, ExternalLink, MessageCircle, Send } from 'lucide-react'
import { api } from '../lib/api'
import type { Health } from '../lib/types'
import { timeAgo } from '../lib/format'

const DOT = { ok: 'bg-emerald-500', degraded: 'bg-amber-500', down: 'bg-red-500', not_configured: 'bg-slate-400', paused: 'bg-slate-400' } as const
const LABEL = { ok: 'OK', degraded: 'Degraded', down: 'Down', not_configured: 'Not connected', paused: 'Paused by operator' } as const

/** System health for the operator: WhatsApp, AI, today's messages, recent errors. Counts only, no raw logs. */
export default function HealthPanel({ code }: { code: string }) {
  const [h, setH] = useState<Health | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    let live = true
    const load = () =>
      api
        .health(code)
        .then((r) => live && (setH(r), setErr('')))
        .catch((e) => live && setErr((e as Error).message))
    load()
    const t = setInterval(load, 15_000)
    return () => {
      live = false
      clearInterval(t)
    }
  }, [code])

  if (!h) return err ? <p className="text-sm text-red-700">System health unavailable: {err}</p> : null
  const wa = h.whatsapp
  const m = h.messages_today
  const errors = h.errors_last_hour
  const errorCount = errors ? (errors.api ?? 0) + (errors.whatsapp ?? 0) : null
  const tiles = [
    {
      icon: MessageCircle,
      title: 'WhatsApp',
      status: wa.status,
      main: LABEL[wa.status],
      sub: [
        wa.gateway ? (wa.gateway.ok ? `gateway ${wa.gateway.ms} ms` : 'gateway not answering') : null,
        wa.last_sent_at ? `last sent ${timeAgo(wa.last_sent_at)}` : null,
        wa.last_received_at ? `last received ${timeAgo(wa.last_received_at)}` : null,
      ].filter(Boolean).join(' · '),
      note: wa.status === 'ok' ? '' : wa.advice,
    },
    {
      icon: Bot,
      title: 'AI (Amazon Bedrock)',
      status: h.ai.status,
      main: h.ai.last_model ? h.ai.last_model.replace(/^(eu|global)\./, '') : 'No calls yet today',
      sub: `${h.ai.calls_today} calls today · ${h.ai.via_fallback_model} via fallback model · ${h.ai.rules_fallback} rules-only`,
      note: h.ai.via_fallback_model > 0 && h.ai.last_model === h.ai.fallback_model ? 'Primary model refused: the fallback model is answering.' : '',
    },
    {
      icon: Send,
      title: 'Messages today',
      status: m.whatsapp_failed > 0 ? 'degraded' : 'ok',
      main: `${m.whatsapp_sent} sent · ${m.whatsapp_received} received`,
      sub: `contact alerts: ${m.contact_alerts_whatsapp} WhatsApp, ${m.contact_alerts_simulated} simulated, ${m.contact_alerts_rate_limited} over limit`,
      note: [m.whatsapp_failed ? `${m.whatsapp_failed} failed sends` : '', m.whatsapp_undeliverable ? `${m.whatsapp_undeliverable} to numbers not on WhatsApp` : '']
        .filter(Boolean)
        .join(' · '),
    },
    {
      icon: Activity,
      title: 'Errors, last hour',
      status: errorCount === null ? 'not_configured' : errorCount === 0 ? 'ok' : 'degraded',
      main: errorCount === null ? 'Metrics unavailable here' : `${errorCount} Lambda error${errorCount === 1 ? '' : 's'}`,
      sub: errors ? `api ${errors.api ?? 0} · whatsapp ${errors.whatsapp ?? 0}` : '',
      note: '',
    },
  ] as const

  return (
    <section className="card p-4" aria-label="System health">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="font-bold">System health</h2>
        <span className="text-xs text-slate-500">checked {timeAgo(h.checked_at)} · refreshes every 15 s</span>
        {h.dashboard_url && (
          <a href={h.dashboard_url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline">
            Logs and alarms in CloudWatch <ExternalLink size={12} />
          </a>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map(({ icon: I, title, status, main, sub, note }) => (
          <div key={title} className="rounded-xl border border-slate-200 p-3" data-health={status}>
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <I size={14} /> {title}
              <span className={`ml-auto h-2.5 w-2.5 rounded-full ${DOT[status]}`} title={LABEL[status]} />
            </p>
            <p className="mt-1 font-bold">{main}</p>
            <p className="text-xs text-slate-500">{sub}</p>
            {note && <p className="mt-1 text-xs font-semibold text-amber-800">{note}</p>}
          </div>
        ))}
      </div>
    </section>
  )
}
