import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Activity, Bell, Car, CirclePlay, CircleStop, Lock, MessageCircle, Phone, RefreshCw, ShieldAlert, ShieldCheck, Siren, Sparkles, Timer } from 'lucide-react'
import { api, save, store } from '../lib/api'
import { FleetDemo } from '../lib/fleet'
import type { Dashboard, FleetRow, Risk } from '../lib/types'
import FleetMap from '../components/FleetMap'
import { Pill, Section, SimBadge, Spinner } from '../components/ui'
import { EVENT_LABEL, RISK_COLOUR, timeAgo } from '../lib/format'

const RISK_LABEL: Record<Risk, string> = { red: 'Needs action', amber: 'Awaiting check-in', handled: 'Operator handling', green: 'Normal' }

export default function DashboardPage() {
  const [code, setCode] = useState(store('mz.teamCode', ''))
  const [draft, setDraft] = useState('')
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const demo = useRef(new FleetDemo())
  const [demoRunning, setDemoRunning] = useState(false)
  const [demoLog, setDemoLog] = useState<string[]>([])

  const load = useCallback(async () => {
    if (!code) return
    setLoading(true)
    try {
      setData(await api.dashboard(code))
      setError('')
    } catch (e) {
      setError((e as Error).message)
      if ((e as { status?: number }).status === 401) {
        setCode('')
        save('mz.teamCode', '')
      }
    } finally {
      setLoading(false)
    }
  }, [code])

  useEffect(() => {
    load()
    const h = setInterval(load, demoRunning ? 2000 : 5000)
    return () => clearInterval(h)
  }, [load, demoRunning])

  useEffect(() => {
    const d = demo.current
    return () => {
      if (d.running) d.stop()
    }
  }, [])

  async function toggleDemo() {
    if (demo.current.running) {
      await demo.current.stop()
      setDemoRunning(false)
      setDemoLog((l) => ['Demo fleet stopped', ...l])
    } else {
      setDemoRunning(true)
      setDemoLog([])
      try {
        await demo.current.start((m) => setDemoLog((l) => [m, ...l].slice(0, 8)))
      } catch (e) {
        setDemoRunning(false)
        setError((e as Error).message)
      }
    }
    load()
  }

  async function ack(f: FleetRow, action: string) {
    if (!f.triage) return
    await api.ack(code, f.trip_id, f.triage.event_id, action)
    load()
  }

  if (!code)
    return (
      <form
        className="card mx-auto mt-10 max-w-sm space-y-3 p-6"
        onSubmit={(e) => {
          e.preventDefault()
          save('mz.teamCode', draft)
          setCode(draft)
        }}
      >
        <h1 className="flex items-center gap-2 text-lg font-extrabold">
          <Lock size={18} /> Operator dashboard
        </h1>
        <p className="text-sm text-slate-600">For transport operators and the team. Enter the team code.</p>
        <input className="input" type="password" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Team code" autoFocus />
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button className="btn-primary w-full" disabled={!draft}>
          Open dashboard
        </button>
      </form>
    )

  if (!data) return <div className="flex justify-center py-20">{error ? <p className="text-red-700">{error}</p> : <Spinner className="h-8 w-8 text-brand-600" />}</div>
  const s = data.summary
  const tiles = [
    { label: 'Live trips', value: s.active, sub: `${s.at_risk} need attention · ${s.trips} total`, icon: Car },
    { label: 'Safe Journey', value: s.trips_safe_mode, sub: 'trips monitored', icon: Activity },
    { label: 'Safety events', value: s.events, sub: `${s.events_by_type.PROLONGED_STOP ?? 0} stops · ${s.events_by_type.ROUTE_DEVIATION ?? 0} deviations`, icon: ShieldAlert },
    { label: 'Check-in responses', value: s.responses.ok + s.responses.help, sub: `${s.responses.ok} OK · ${s.responses.help} help · ${s.responses.no_response} no reply`, icon: ShieldCheck },
    { label: 'Notifications', value: s.notifications, sub: 'trusted-contact alerts', icon: Bell },
    { label: 'Avg time to prompt', value: s.avg_prompt_ms != null ? `${s.avg_prompt_ms} ms` : '–', sub: 'event → check-in shown', icon: Timer },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-extrabold">Fleet safety dashboard</h1>
        <SimBadge label="Simulated data" />
        <button className={`ml-auto ${demoRunning ? 'btn-secondary' : 'btn-primary'}`} onClick={toggleDemo}>
          {demoRunning ? <CircleStop size={16} /> : <CirclePlay size={16} />} {demoRunning ? 'Stop demo fleet' : 'Run demo fleet'}
        </button>
        <button className="btn-ghost" onClick={load} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      <p className="-mt-3 text-sm text-slate-600">
        For the e-hailing operator's safety team: every live trip is monitored from its telemetry. Trips that need action are flagged red with an AI triage suggestion.
      </p>

      <Fleet fleet={data.fleet} onAck={ack} log={demoLog} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        {tiles.map(({ label, value, sub, icon: I }) => (
          <div key={label} className="card p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <I size={14} /> {label}
            </p>
            <p className="mt-1 text-2xl font-extrabold">{value}</p>
            <p className="text-xs text-slate-500">{sub}</p>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden">
        <h2 className="border-b border-slate-100 p-4 font-bold">All safety events</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">When</th>
                <th className="px-4 py-2">Trip</th>
                <th className="px-4 py-2">Event</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Response</th>
                <th className="px-4 py-2">Notifications</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.events.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                    No events yet. Start a trip and simulate a stop.
                  </td>
                </tr>
              )}
              {data.events.map((e) => (
                <tr key={e.trip_id + e.event_id}>
                  <td className="px-4 py-2 whitespace-nowrap text-slate-500">{timeAgo(e.created_at)}</td>
                  <td className="px-4 py-2 font-mono">
                    <Link to={`/trip/${e.trip_id}`} className="text-brand-700 hover:underline">
                      {e.trip_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    {EVENT_LABEL[e.type] ?? e.type}
                    <span className="block text-xs text-slate-500">
                      {e.details.stationary_s ? `${Math.round(e.details.stationary_s / 60)} min stationary` : e.details.deviation_m ? `${e.details.deviation_m} m off route` : e.details.channel ? `via ${e.details.channel}` : ''}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <Pill status={e.status} />
                  </td>
                  <td className="px-4 py-2 text-xs">
                    {e.response ? `${e.response === 'ok' ? "I'm OK" : 'Need help'} (${e.response_channel})` : e.escalation_reason === 'no_response' ? 'No response' : '–'}
                  </td>
                  <td className="px-4 py-2">
                    {e.notifications?.map((n, i) => (
                      <span key={i} className="mr-1">
                        <Pill status={n.status} />
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card overflow-hidden">
        <h2 className="border-b border-slate-100 p-4 font-bold">Recent trips</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Trip</th>
                <th className="px-4 py-2">Route</th>
                <th className="px-4 py-2">Driver</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Safe mode</th>
                <th className="px-4 py-2">WhatsApp</th>
                <th className="px-4 py-2">Events</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.trips.map((t) => (
                <tr key={t.trip_id}>
                  <td className="px-4 py-2 font-mono">
                    <Link to={`/trip/${t.trip_id}`} className="text-brand-700 hover:underline">
                      {t.trip_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    {t.pickup_name} → {t.destination_name}
                  </td>
                  <td className="px-4 py-2">
                    {t.driver.name} <span className="font-mono text-xs text-slate-500">{t.driver.plate}</span>
                  </td>
                  <td className="px-4 py-2">
                    <Pill status={t.status} />
                  </td>
                  <td className="px-4 py-2">{t.safe_mode ? 'On' : 'Off'}</td>
                  <td className="px-4 py-2">{t.whatsapp_linked ? 'Linked' : '–'}</td>
                  <td className="px-4 py-2">{t.events_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Fleet({ fleet, onAck, log }: { fleet: FleetRow[]; onAck: (f: FleetRow, action: string) => Promise<void>; log: string[] }) {
  return (
    <Section title="Live fleet" icon={<Car size={18} className="text-brand-600" />} right={<Legend />}>
      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <div className="space-y-3">
          <FleetMap fleet={fleet} className="h-72 lg:h-96" />
          {log.length > 0 && (
            <ul className="space-y-0.5 rounded-xl bg-slate-900 p-3 font-mono text-[11px] text-slate-200">
              {log.map((l, i) => (
                <li key={i} className={i === 0 ? 'text-white' : 'opacity-70'}>
                  {l}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="space-y-2">
          {fleet.length === 0 && (
            <p className="rounded-xl bg-slate-50 p-6 text-center text-sm text-slate-500">
              No live trips. Press <strong>Run demo fleet</strong>, or start a trip from the Ride page.
            </p>
          )}
          {fleet.map((f) => (
            <FleetCard key={f.trip_id} f={f} onAck={onAck} />
          ))}
        </div>
      </div>
    </Section>
  )
}

function Legend() {
  return (
    <div className="hidden flex-wrap gap-3 text-xs text-slate-600 sm:flex">
      {(Object.keys(RISK_LABEL) as Risk[]).map((r) => (
        <span key={r} className="flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: RISK_COLOUR[r] }} /> {RISK_LABEL[r]}
        </span>
      ))}
    </div>
  )
}

function FleetCard({ f, onAck }: { f: FleetRow; onAck: (f: FleetRow, action: string) => Promise<void> }) {
  const [busy, setBusy] = useState('')
  const red = f.risk === 'red'
  const ev = f.latest_event
  async function act(action: string) {
    setBusy(action)
    try {
      await onAck(f, action)
    } finally {
      setBusy('')
    }
  }
  return (
    <div
      data-risk={f.risk}
      className={`rounded-xl border-2 p-3 ${red ? 'animate-[pulse_1.6s_ease-in-out_infinite] border-red-500 bg-red-50' : f.risk === 'amber' ? 'border-amber-300 bg-amber-50' : 'border-slate-200'}`}
    >
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: RISK_COLOUR[f.risk] }} />
        <Link to={`/trip/${f.trip_id}`} className="font-mono font-bold text-brand-700 hover:underline">
          {f.trip_id}
        </Link>
        <span className="font-semibold">{f.passenger_name}</span>
        <span className="text-slate-500">
          {f.pickup_name} → {f.destination_name}
        </span>
        <span className="ml-auto text-xs font-bold uppercase" style={{ color: RISK_COLOUR[f.risk] }}>
          {RISK_LABEL[f.risk]}
        </span>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-600">
        <span>
          {f.driver.name} · <span className="font-mono">{f.driver.plate}</span>
          {f.driver.safety_score != null && <> · score {f.driver.safety_score}</>}
        </span>
        <span>{f.position.speed_kmh ?? 0} km/h</span>
        <span>updated {timeAgo(f.position.at)}</span>
        {f.whatsapp_channel && (
          <span className="flex items-center gap-1 text-emerald-700">
            <MessageCircle size={12} /> {f.whatsapp_channel === 'whatsapp' ? 'WhatsApp' : 'WhatsApp (simulated)'}
          </span>
        )}
        {ev && (
          <span>
            {EVENT_LABEL[ev.type] ?? ev.type}: <Pill status={ev.status} />
          </span>
        )}
      </div>
      {f.triage && (
        <div className="mt-2 rounded-lg bg-white p-2 text-sm shadow-sm">
          <p className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            <Sparkles size={12} /> {f.triage.source === 'fallback' ? 'Rules-based triage (AI unavailable)' : `AI triage · ${f.triage.model ?? 'Bedrock'}`}
          </p>
          <p className="font-semibold text-slate-900">{f.triage.text}</p>
          {f.triage.operator_ack ? (
            <p className="mt-1 text-xs text-blue-700">
              ✔ {f.triage.operator_ack.action} · {timeAgo(f.triage.operator_ack.at)}
            </p>
          ) : (
            <div className="mt-2 flex flex-wrap gap-2">
              {[
                { a: 'Called driver', I: Phone },
                { a: 'Called passenger', I: Phone },
                { a: 'Escalated to SAPS (simulated)', I: Siren },
              ].map(({ a, I }) => (
                <button key={a} className="btn-secondary px-2 py-1 text-xs" onClick={() => act(a)} disabled={!!busy}>
                  {busy === a ? <Spinner /> : <I size={12} />} {a}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
