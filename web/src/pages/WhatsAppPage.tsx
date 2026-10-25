import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { QRCodeSVG } from 'qrcode.react'
import { CheckCheck, MessageCircle, Send, Smartphone, Wifi, WifiOff } from 'lucide-react'
import { api, save, store, waSession } from '../lib/api'
import type { AppConfig } from '../lib/types'
import { RichText, SimBadge, Spinner } from '../components/ui'

type Bubble = { from: 'me' | 'bot'; text: string; at: string }

const COMMANDS = [
  ['HELP', 'Menu'],
  ['CHECK CA 123-456', 'Look up a driver or number plate in the registry'],
  ['TRIP MZXXXX', 'Link this chat to your trip for check-ins'],
  ['1 / 2 or your own words', "Answer a check-in: I'm OK / I need help, or e.g. \"took a detour, still going to Sandton\""],
  ['SOS', 'Alert your trusted contact now'],
  ['Any question', 'Answered by the AI safety assistant'],
]

export default function WhatsAppPage() {
  const [params] = useSearchParams()
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [session] = useState(waSession)
  const [bubbles, setBubbles] = useState<Bubble[]>(() => store<Bubble[]>('mz.waChat', []))
  const [input, setInput] = useState(params.get('trip') ? `TRIP ${params.get('trip')}` : '')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.config().then(setConfig).catch(() => {})
  }, [])
  useEffect(() => {
    save('mz.waChat', bubbles.slice(-60))
    end.current?.scrollIntoView({ behavior: 'smooth' })
  }, [bubbles])

  // Pushed messages (check-in prompts, alerts) for this simulated chat.
  useEffect(() => {
    const h = setInterval(async () => {
      try {
        const { messages } = await api.waOutbox(session)
        if (messages.length) setBubbles((b) => [...b, ...messages.map((m) => ({ from: 'bot' as const, text: m.text, at: m.at }))])
      } catch {
        /* offline: ignore */
      }
    }, 3000)
    return () => clearInterval(h)
  }, [session])

  async function send(text: string) {
    if (!text.trim() || busy) return
    const now = new Date().toISOString()
    setBubbles((b) => [...b, { from: 'me', text, at: now }])
    setInput('')
    setBusy(true)
    try {
      const { replies } = await api.waSimulate(session, text)
      setBubbles((b) => [...b, ...replies.map((r) => ({ from: 'bot' as const, text: r, at: new Date().toISOString() }))])
    } catch (e) {
      setBubbles((b) => [...b, { from: 'bot', text: `⚠️ ${(e as Error).message}`, at: now }])
    } finally {
      setBusy(false)
    }
  }

  const digits = (config?.whatsapp.number ?? '').replace(/\D/g, '')
  const link = digits ? `https://wa.me/${digits}?text=HELP` : ''

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
      <div className="space-y-4">
        <div className="rounded-3xl bg-gradient-to-br from-emerald-600 to-emerald-800 p-6 text-white">
          <h1 className="flex items-center gap-2 text-2xl font-extrabold">
            <MessageCircle /> MzansiRide on WhatsApp
          </h1>
          <p className="mt-2 text-emerald-50">
            Many South Africans have WhatsApp bundles but no general mobile data. Every safety feature works in a WhatsApp chat: driver checks, trip check-ins, SOS and the AI safety assistant. There's no app to install.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-2 rounded-xl bg-white/10 p-2">
              <WifiOff size={16} /> Works on WhatsApp-only bundles
            </div>
            <div className="flex items-center gap-2 rounded-xl bg-white/10 p-2">
              <Smartphone size={16} /> Any phone with WhatsApp
            </div>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="mb-3 font-bold">Chat with the real number</h2>
          {link ? (
            <div className="flex flex-wrap items-center gap-5">
              <QRCodeSVG value={link} size={140} className="rounded-xl border border-slate-200 p-2" />
              <div>
                <p className="font-mono text-2xl font-bold">{config?.whatsapp.number}</p>
                <a href={link} target="_blank" rel="noreferrer" className="btn-primary mt-3 bg-emerald-600 hover:bg-emerald-700">
                  <MessageCircle size={16} /> Open WhatsApp
                </a>
                <p className="mt-2 flex items-center gap-1 text-xs text-emerald-700">
                  <Wifi size={12} /> Live via the OpenWA gateway → API Gateway → Lambda → Bedrock
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-amber-800">The live WhatsApp gateway isn't connected in this environment. Use the simulator: it runs exactly the same backend logic.</p>
          )}
        </div>

        <div className="card p-5">
          <h2 className="mb-3 font-bold">Commands</h2>
          <dl className="divide-y divide-slate-100">
            {COMMANDS.map(([c, d]) => (
              <div key={c} className="flex gap-3 py-2 text-sm">
                <dt className="w-40 shrink-0">
                  <button className="font-mono font-bold text-brand-700 hover:underline" onClick={() => setInput(c.startsWith('Any') ? '' : c.split(' / ')[0])}>
                    {c}
                  </button>
                </dt>
                <dd className="text-slate-600">{d}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <div className="mx-auto w-full max-w-sm">
        <div className="overflow-hidden rounded-[2rem] border-8 border-slate-900 bg-[#efeae2] shadow-2xl">
          <div className="flex items-center gap-2 bg-[#075e54] px-3 py-2.5 text-white">
            <img src="/logo.svg" className="h-8 w-8 rounded-full bg-white" alt="" />
            <div className="flex-1">
              <p className="text-sm font-bold">MzansiRide SafeAI</p>
              <p className="text-[11px] text-emerald-100">{busy ? 'typing…' : 'online'}</p>
            </div>
            <SimBadge label="Simulator" className="border-white/30 bg-white/15 text-white" />
          </div>
          <div className="h-[460px] space-y-2 overflow-y-auto p-3">
            {bubbles.length === 0 && <p className="rounded-lg bg-[#fff5c4] p-2 text-center text-xs text-slate-700">Same backend as the real WhatsApp number. Say "Hi" to start.</p>}
            {bubbles.map((b, i) => (
              <div key={i} className={`flex ${b.from === 'me' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-lg px-2.5 py-1.5 text-[13px] shadow-sm ${b.from === 'me' ? 'bg-[#d9fdd3]' : 'bg-white'}`}>
                  <RichText text={b.text} />
                  <p className="mt-0.5 flex items-center justify-end gap-1 text-[10px] text-slate-500">
                    {new Date(b.at).toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit' })}
                    {b.from === 'me' && <CheckCheck size={12} className="text-sky-500" />}
                  </p>
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex">
                <div className="rounded-lg bg-white px-3 py-2 shadow-sm">
                  <Spinner className="h-3 w-3 text-slate-400" />
                </div>
              </div>
            )}
            <div ref={end} />
          </div>
          <form
            className="flex gap-2 bg-[#f0f2f5] p-2"
            onSubmit={(e) => {
              e.preventDefault()
              send(input)
            }}
          >
            <input className="flex-1 rounded-full border-0 bg-white px-4 py-2 text-sm outline-none" placeholder="Message" value={input} onChange={(e) => setInput(e.target.value)} />
            <button className="flex h-10 w-10 items-center justify-center rounded-full bg-[#00a884] text-white disabled:opacity-50" disabled={busy || !input.trim()} aria-label="Send">
              <Send size={16} />
            </button>
          </form>
        </div>
        <button
          className="btn-ghost mt-2 w-full text-xs"
          onClick={() => {
            setBubbles([])
          }}
        >
          Clear chat
        </button>
      </div>
    </div>
  )
}
