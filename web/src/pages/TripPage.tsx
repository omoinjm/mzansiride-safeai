import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { QRCodeSVG } from 'qrcode.react'
import {
  Bell, Car, CirclePause, Navigation, CirclePlay, Clock, Flag, MessageCircle, Route as RouteIcon, Share2, Shield, ShieldAlert,
  ShieldCheck, Siren, Sparkles, UserRound,
} from 'lucide-react'
import { api, save } from '../lib/api'
import { Sim, type SimSnapshot } from '../lib/sim'
import type { AppConfig, SafetyEvent, Trip } from '../lib/types'
import TripMap from '../components/TripMap'
import DriverCard from '../components/DriverCard'
import CheckInModal from '../components/CheckInModal'
import { Pill, Section, SimBadge, Spinner } from '../components/ui'
import { EVENT_LABEL, describe, fmtDuration, fmtZar, timeAgo } from '../lib/format'

type Active = { event: SafetyEvent; startedAt: number }

export default function TripPage() {
  const { id = '' } = useParams()
  const [trip, setTrip] = useState<Trip | null>(null)
  const [events, setEvents] = useState<SafetyEvent[]>([])
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [error, setError] = useState('')
  const [snap, setSnap] = useState<SimSnapshot | null>(null)
  const [running, setRunning] = useState(false)
  const [stepS, setStepS] = useState(15)
  const [active, setActive] = useState<Active | null>(null)
  const [toast, setToast] = useState('')
  const sim = useRef<Sim | null>(null)
  const inFlight = useRef(false)

  const refresh = useCallback(async () => {
    try {
      const t = await api.trip(id)
      setTrip(t)
      setEvents(t.events ?? [])
      return t
    } catch (e) {
      setError((e as Error).message)
    }
  }, [id])

  useEffect(() => {
    save('mz.trip', id.toUpperCase())
    api.config().then(setConfig).catch(() => {})
    refresh().then((t) => {
      if (t?.route && !sim.current) {
        sim.current = new Sim(t.route.points, t.route.duration_s, t.last_position)
        setSnap(sim.current.snapshot())
      }
    })
  }, [id, refresh])

  // Background refresh: picks up WhatsApp check-ins, links and escalations made elsewhere.
  useEffect(() => {
    const h = setInterval(refresh, 4000)
    return () => clearInterval(h)
  }, [refresh])

  // Close the prompt if it was answered elsewhere (e.g. "1" on WhatsApp).
  useEffect(() => {
    if (!active) return
    const latest = events.find((e) => e.event_id === active.event.event_id)
    if (latest && latest.status === 'resolved_ok') {
      setActive(null)
      sim.current?.resume()
      flash(`Answered on ${latest.response_channel === 'whatsapp' ? 'WhatsApp' : 'another device'}: passenger is OK`)
    } else if (latest && latest.status !== active.event.status) {
      setActive({ ...active, event: latest })
    }
  }, [events, active])

  function flash(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(''), 5000)
  }

  const tick = useCallback(async () => {
    const s = sim.current
    if (!s || inFlight.current || !trip) return
    inFlight.current = true
    try {
      const snapNow = s.step(stepS)
      setSnap(snapNow)
      const sentAt = performance.now()
      const res = await api.telemetry(trip.trip_id, { lat: snapNow.pos[0], lng: snapNow.pos[1], ts: snapNow.ts })
      if (res.new_events.length) {
        setActive({ event: res.new_events[0], startedAt: sentAt })
        setEvents((ev) => [...ev, ...res.new_events])
      }
      if (res.reminded?.length) flash('Reminder sent: please answer the check-in')
      if (res.escalated.length) {
        flash('No check-in response: trusted contact notified')
        refresh()
      }
      if (snapNow.mode === 'arrived') {
        setRunning(false)
        await api.complete(trip.trip_id)
        refresh()
      }
    } catch (e) {
      flash((e as Error).message)
      setRunning(false)
    } finally {
      inFlight.current = false
    }
  }, [trip, stepS, refresh])

  useEffect(() => {
    if (!running) return
    const h = setInterval(tick, 1000)
    return () => clearInterval(h)
  }, [running, tick])

  async function start() {
    if (!trip) return
    await api.start(trip.trip_id)
    await refresh()
    setRunning(true)
  }

  async function respond(response: 'ok' | 'help', promptMs: number) {
    if (!active || !trip) return
    const ev = await api.checkin(trip.trip_id, active.event.event_id, response, promptMs)
    setActive(null)
    if (response === 'ok') {
      sim.current?.resume()
      flash('Thanks. Alert closed and recorded.')
    } else {
      const n = ev.notifications.at(-1)
      flash(`Help requested: ${n?.to_name ?? 'trusted contact'} notified (${n?.status === 'simulated' ? 'simulated' : n?.status})`)
    }
    refresh()
  }

  async function toggleSafe(enabled: boolean) {
    if (!trip) return
    setTrip(await api.safeMode(trip.trip_id, enabled))
  }

  if (error) return <NotFound message={error} />
  if (!trip || !trip.route) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8 text-brand-600" /></div>

  const points = trip.route.points
  const openEvent = events.find((e) => e.status === 'awaiting_checkin')

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-extrabold sm:text-2xl">
          {trip.pickup_name} <span className="text-slate-400">→</span> {trip.destination_name}
        </h1>
        <Pill status={trip.status} />
        <SimBadge label="Simulated trip" />
        <span className="ml-auto rounded-lg bg-slate-900 px-2 py-1 font-mono text-sm font-bold tracking-widest text-white" title="Trip code (use on WhatsApp)">
          {trip.trip_id}
        </span>
      </div>

      {toast && (
        <div className="fixed top-24 left-1/2 z-[1500] -translate-x-1/2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-lg">{toast}</div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="space-y-4">
          <div className="relative">
            <TripMap points={points} alternatives={trip.route.alternatives} car={trip.status === 'in_progress' || snap?.ts ? snap?.pos : null} trail={snap?.trail} events={events} className="h-[46vh] min-h-72 lg:h-[520px]" />
            {trip.status === 'in_progress' && snap && <JourneyHud snap={snap} safe={trip.safe_mode} />}
          </div>

          {trip.status === 'driver_assigned' && (
            <Section title="Your driver" icon={<UserRound size={18} className="text-brand-600" />}>
              <DriverCard driver={trip.driver} check={trip.driver_check} />
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                <div>
                  <p className="text-sm text-slate-500">{trip.ride_type === 'shared' ? `Shared ride · ${trip.riders} riders` : 'Individual ride'}</p>
                  <p className="text-xl font-extrabold">{fmtZar(trip.fare_zar)}</p>
                </div>
                <button className="btn-primary px-6 py-3 text-base" onClick={start}>
                  <CirclePlay size={20} /> Start trip
                </button>
              </div>
            </Section>
          )}

          {trip.status === 'in_progress' && snap && (
            <DemoControls
              snap={snap}
              running={running}
              stepS={stepS}
              setStepS={setStepS}
              onPlay={() => setRunning((r) => !r)}
              onNormal={() => {
                sim.current?.resume()
                setSnap(sim.current!.snapshot())
                setRunning(true)
              }}
              onStop={() => {
                sim.current?.stop()
                setSnap(sim.current!.snapshot())
                setRunning(true)
              }}
              alternative={trip.route.alternatives?.[0]}
              onFollowAlternative={() => {
                sim.current?.followRoute(trip.route!.alternatives![0])
                setSnap(sim.current!.snapshot())
                setRunning(true)
                flash("Driver is following another road (like Waze would). Our rules know it: no alert.")
              }}
              onDeviate={() => {
                sim.current?.deviate()
                setSnap(sim.current!.snapshot())
                setRunning(true)
              }}
              safe={trip.safe_mode}
            />
          )}

          {trip.status === 'completed' && <Completed trip={trip} events={events} />}

          <EventsTimeline events={events} />
        </div>

        <div className="space-y-4">
          <SafePanel trip={trip} onToggle={toggleSafe} openEvent={openEvent} onShowPrompt={() => openEvent && setActive({ event: openEvent, startedAt: performance.now() })} />
          <TrustedContact trip={trip} onSaved={setTrip} onAction={(m) => { flash(m); refresh() }} />
          <WhatsAppLink trip={trip} config={config} />
          {trip.status !== 'driver_assigned' && (
            <Section title="Driver" icon={<UserRound size={18} className="text-brand-600" />}>
              <DriverCard driver={trip.driver} check={trip.driver_check} />
            </Section>
          )}
          <Link to="/assistant" className="card flex items-center gap-3 p-4 hover:border-brand-300">
            <Sparkles className="text-brand-600" />
            <div>
              <p className="font-bold">Ask the safety assistant</p>
              <p className="text-sm text-slate-500">Powered by Amazon Bedrock, and it knows about this trip.</p>
            </div>
          </Link>
        </div>
      </div>

      {active && snap && (
        <CheckInModal
          event={active.event}
          tripTs={snap.ts}
          timeoutS={config?.checkin_timeout_s ?? 120}
          promptStartedAt={active.startedAt}
          onRespond={respond}
          onReplied={(r) => {
            setActive(null)
            if (r.intent === 'ok') {
              sim.current?.resume()
              flash(`Understood: ${r.reason || "you're OK"}. Alert closed.`)
            } else {
              flash('Help requested: trusted contact and safety team alerted')
            }
            refresh()
          }}
        />
      )}
    </div>
  )
}

function JourneyHud({ snap, safe }: { snap: SimSnapshot; safe: boolean }) {
  const label = {
    driving: 'Driving',
    stopped: `Stopped ${fmtDuration(snap.stoppedFor)}`,
    detour: `Off route ${snap.offsetM} m`,
    returning: 'Returning to route',
    arrived: 'Arrived',
  }[snap.mode]
  return (
    <div className="pointer-events-none absolute top-3 left-3 z-[500] flex flex-wrap gap-2">
      <span className="rounded-xl bg-white/95 px-3 py-1.5 text-xs font-bold shadow">
        <Clock size={12} className="mr-1 inline" /> Trip time {fmtDuration(snap.ts)}
      </span>
      <span className={`rounded-xl px-3 py-1.5 text-xs font-bold shadow ${snap.mode === 'driving' || snap.mode === 'arrived' ? 'bg-white/95' : 'bg-amber-400 text-amber-950'}`}>{label}</span>
      <span className={`rounded-xl px-3 py-1.5 text-xs font-bold shadow ${safe ? 'bg-brand-600 text-white' : 'bg-slate-700 text-white'}`}>
        {safe ? 'Safe Journey ON' : 'Safe Journey OFF'}
      </span>
    </div>
  )
}

function DemoControls(props: {
  snap: SimSnapshot
  running: boolean
  stepS: number
  safe: boolean
  setStepS: (n: number) => void
  onPlay: () => void
  onStop: () => void
  onDeviate: () => void
  onNormal: () => void
  alternative?: [number, number][]
  onFollowAlternative: () => void
}) {
  const { snap, running, stepS, safe } = props
  return (
    <Section title="Simulator panel" icon={<Flag size={18} className="text-amber-600" />} right={<SimBadge label="Simulation" />}>
      <p className="mb-3 text-sm text-slate-600">
        There's no live GPS in the prototype: the car follows the planned route on a trip clock ({stepS} s of trip time per second) and sends its position and speed to the backend. Inject a scenario, and the backend rules decide whether to raise a check-in. Tip: go off-route, then stop, for "stopped off-route".
      </p>
      <div className="mb-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full bg-brand-500 transition-all" style={{ width: `${Math.round(snap.progress * 100)}%` }} />
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn-secondary" onClick={props.onPlay}>
          {running ? <CirclePause size={16} /> : <CirclePlay size={16} />} {running ? 'Pause' : 'Play'}
        </button>
        <button className="btn-secondary border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100" onClick={props.onNormal} disabled={snap.mode === 'driving' && running}>
          <Car size={16} /> Simulate normal drive
        </button>
        {props.alternative && (
          <button
            className="btn-secondary"
            onClick={props.onFollowAlternative}
            disabled={snap.mode !== 'driving' || snap.progress > 0.15}
            title="Available near the start of the trip, where the roads split"
          >
            <Navigation size={16} /> Simulate driver's own route (Waze)
          </button>
        )}
        <button className="btn-secondary border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100" onClick={props.onDeviate} disabled={snap.mode !== 'driving'}>
          <RouteIcon size={16} /> Simulate off-route
        </button>
        <button className="btn-secondary border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100" onClick={props.onStop} disabled={snap.mode !== 'driving' && snap.mode !== 'detour'}>
          <CirclePause size={16} /> Simulate prolonged stop
        </button>
        <select className="input w-auto py-2" value={stepS} onChange={(e) => props.setStepS(Number(e.target.value))} aria-label="Simulation speed">
          <option value={15}>15× speed</option>
          <option value={30}>30× speed</option>
          <option value={5}>5× speed</option>
        </select>
      </div>
      {!safe && <p className="mt-3 rounded-lg bg-slate-100 p-2 text-sm text-slate-700">Safe Journey Mode is off, so no alerts will be raised. Turn it on in the safety panel.</p>}
      {snap.mode === 'stopped' && safe && <p className="mt-3 text-sm text-amber-800">Rule: no movement for 3 min of trip time away from pickup or drop-off raises a check-in.</p>}
      {snap.mode === 'detour' && safe && <p className="mt-3 text-sm text-amber-800">Rule: more than 250 m from the planned route for 2 readings in a row raises a check-in.</p>}
    </Section>
  )
}

function SafePanel({ trip, onToggle, openEvent, onShowPrompt }: { trip: Trip; onToggle: (b: boolean) => void; openEvent?: SafetyEvent; onShowPrompt: () => void }) {
  return (
    <section className={`card overflow-hidden ${trip.safe_mode ? 'border-brand-300' : ''}`}>
      <div className={`flex items-center gap-3 p-4 ${trip.safe_mode ? 'bg-brand-600 text-white' : 'bg-slate-100'}`}>
        {trip.safe_mode ? <ShieldCheck size={28} /> : <Shield size={28} className="text-slate-500" />}
        <div className="flex-1">
          <p className="font-extrabold">Safe Journey Mode</p>
          <p className={`text-sm ${trip.safe_mode ? 'text-brand-50' : 'text-slate-600'}`}>
            {trip.safe_mode ? 'Watching for unusual stops and route changes' : 'Turn on to get check-ins during the trip'}
          </p>
        </div>
        <button
          role="switch"
          aria-checked={trip.safe_mode}
          aria-label="Safe Journey Mode"
          onClick={() => onToggle(!trip.safe_mode)}
          disabled={trip.status === 'completed'}
          className={`relative h-8 w-14 rounded-full transition ${trip.safe_mode ? 'bg-gold-400' : 'bg-slate-300'}`}
        >
          <span className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow transition-all ${trip.safe_mode ? 'left-7' : 'left-1'}`} />
        </button>
      </div>
      {openEvent && (
        <button onClick={onShowPrompt} className="flex w-full items-center gap-2 bg-amber-50 p-3 text-left text-sm font-semibold text-amber-900">
          <Bell size={16} /> Check-in waiting: {EVENT_LABEL[openEvent.type]}. Tap to answer.
        </button>
      )}
    </section>
  )
}

function TrustedContact({ trip, onSaved, onAction }: { trip: Trip; onSaved: (t: Trip) => void; onAction: (msg: string) => void }) {
  const [editing, setEditing] = useState(!trip.trusted_contact)
  const [name, setName] = useState(trip.trusted_contact?.name ?? '')
  const [phone, setPhone] = useState('')
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')

  async function saveContact() {
    setBusy('save')
    setErr('')
    try {
      onSaved(await api.trustedContact(trip.trip_id, { name, phone }))
      setEditing(false)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy('')
    }
  }

  async function act(share: boolean) {
    setBusy(share ? 'share' : 'sos')
    try {
      const ev = await api.sos(trip.trip_id, share)
      const n = ev.notifications[0]
      onAction(share ? `Trip shared with ${n.to_name} (${n.status === 'simulated' ? 'simulated' : n.status})` : `SOS sent to ${n.to_name} (${n.status === 'simulated' ? 'simulated' : n.status})`)
    } finally {
      setBusy('')
    }
  }

  return (
    <Section title="Trusted contact" icon={<UserRound size={18} className="text-brand-600" />}>
      {editing ? (
        <div className="space-y-2">
          <input className="input" placeholder="Name, e.g. Mom" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="input" placeholder="Phone, e.g. 082 123 4567" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
          {err && <p className="text-sm text-red-700">{err}</p>}
          <button className="btn-primary w-full" onClick={saveContact} disabled={!phone || busy === 'save'}>
            {busy === 'save' && <Spinner />} Save contact
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <div>
            <p className="font-semibold">{trip.trusted_contact?.name || 'Trusted contact'}</p>
            <p className="font-mono text-sm text-slate-500">{trip.trusted_contact?.phone}</p>
            {trip.trusted_contact?.delivery === 'whatsapp' ? (
              <p className="mt-1 text-xs font-semibold text-emerald-700">Gets real WhatsApp alerts</p>
            ) : (
              <p className="mt-1 text-xs font-semibold text-amber-700">Alerts simulated: WhatsApp isn't connected here</p>
            )}
          </div>
          <button className="btn-ghost py-1 text-xs" onClick={() => setEditing(true)}>
            Change
          </button>
        </div>
      )}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button className="btn-secondary" onClick={() => act(true)} disabled={!trip.trusted_contact || !!busy}>
          {busy === 'share' ? <Spinner /> : <Share2 size={16} />} Share trip
        </button>
        <button className="btn-danger" onClick={() => act(false)} disabled={!!busy}>
          {busy === 'sos' ? <Spinner /> : <Siren size={16} />} SOS
        </button>
      </div>
      <p className="mt-2 text-[11px] text-slate-500">Prototype: alerts go to this number on WhatsApp from our demo number.</p>
    </Section>
  )
}

function WhatsAppLink({ trip, config }: { trip: Trip; config: AppConfig | null }) {
  const digits = (config?.whatsapp.number ?? '').replace(/\D/g, '')
  const text = `TRIP ${trip.trip_id}`
  const link = digits ? `https://wa.me/${digits}?text=${encodeURIComponent(text)}` : ''
  return (
    <Section title="Check-ins on WhatsApp" icon={<MessageCircle size={18} className="text-emerald-600" />} right={trip.whatsapp_linked ? <Pill status="resolved_ok" /> : undefined}>
      {config?.whatsapp.paused ? (
        <p className="text-sm text-amber-800">WhatsApp check-ins are paused by the operator. You'll get check-ins here in the app.</p>
      ) : trip.whatsapp_linked ? (
        <p className="text-sm text-emerald-800">
          {trip.whatsapp_channel === 'whatsapp'
            ? `Linked to ${trip.passenger_phone ?? 'your WhatsApp'}. Check-ins arrive there automatically: reply 1 (safe) or 2 (help).`
            : 'Linked. Safety check-ins for this trip also arrive on WhatsApp. Reply 1 (safe) or 2 (help).'}
          {trip.whatsapp_channel === 'simulator' && (
            <>
              {' '}
              WhatsApp isn't connected in this environment, so they go to the{' '}
              <Link to="/whatsapp" className="font-semibold underline">
                WhatsApp simulator
              </Link>
              .
            </>
          )}
        </p>
      ) : (
        <>
          <p className="text-sm text-slate-600">
            No mobile data? Most people have WhatsApp bundles. Send <code className="rounded bg-slate-100 px-1 font-bold">{text}</code> to our WhatsApp number to get check-ins there.
          </p>
          {link ? (
            <div className="mt-3 flex items-center gap-3">
              <QRCodeSVG value={link} size={88} className="shrink-0 rounded-lg border border-slate-200 p-1" />
              <div className="space-y-2">
                <a href={link} target="_blank" rel="noreferrer" className="btn-primary bg-emerald-600 hover:bg-emerald-700">
                  <MessageCircle size={16} /> Open WhatsApp
                </a>
                <p className="text-xs text-slate-500">{config?.whatsapp.number}</p>
              </div>
            </div>
          ) : (
            <p className="mt-2 text-xs text-amber-700">The live WhatsApp number isn't connected in this environment, but you can use the simulator.</p>
          )}
          <Link to={`/whatsapp?trip=${trip.trip_id}`} className="mt-3 inline-block text-sm font-semibold text-brand-700 underline">
            Or try it in the WhatsApp simulator →
          </Link>
        </>
      )}
    </Section>
  )
}

function EventsTimeline({ events }: { events: SafetyEvent[] }) {
  const sorted = useMemo(() => [...events].sort((a, b) => b.event_id.localeCompare(a.event_id)), [events])
  return (
    <Section title="Safety log" icon={<ShieldAlert size={18} className="text-brand-600" />} right={<span className="text-xs text-slate-500">Stored in DynamoDB</span>}>
      {sorted.length === 0 ? (
        <p className="text-sm text-slate-500">No safety events yet.</p>
      ) : (
        <ol className="space-y-3">
          {sorted.map((e) => (
            <li key={e.event_id} className="rounded-xl border border-slate-200 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-bold">{EVENT_LABEL[e.type] ?? e.type}</span>
                <Pill status={e.status} />
                <span className="ml-auto text-xs text-slate-500">{timeAgo(e.created_at)}</span>
              </div>
              {(e.type === 'PROLONGED_STOP' || e.type === 'ROUTE_DEVIATION') && <p className="mt-1 text-sm text-slate-600">{describe(e)}</p>}
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                {e.reminded_at && <span>Reminder sent</span>}
                {e.response && (
                  <span>
                    Response: <strong>{e.response === 'ok' ? "I'm OK" : 'Need help'}</strong> via {e.response_channel}
                  </span>
                )}
                {e.escalation_reason && <span>Escalated: {e.escalation_reason.replaceAll('_', ' ')}</span>}
                {e.prompt_ms != null && <span>Prompt shown in {e.prompt_ms} ms</span>}
                {e.triage && <span>Operator safety team alerted{e.operator_ack ? ` · ${e.operator_ack.action.toLowerCase()}` : ''}</span>}
              </div>
              {e.response_text && (
                <p className="mt-2 rounded-lg bg-slate-50 p-2 text-xs">
                  “{e.response_text}” <span className="text-slate-500">· understood as {e.response === 'ok' ? 'OK' : 'needs help'}
                  {e.response_reason ? `: ${e.response_reason}` : ''} ({e.response_understood_by === 'rules' ? 'rules' : 'AI'})</span>
                </p>
              )}
              {e.notifications?.map((n, i) => (
                <div key={i} className="mt-2 flex items-center gap-2 rounded-lg bg-slate-50 p-2 text-xs">
                  <Bell size={14} className="text-slate-500" />
                  <span>
                    {n.to_name} {n.to} · {n.channel}
                  </span>
                  <span className="ml-auto flex gap-1">
                    <Pill status={n.status} />
                    {n.sms && <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold text-slate-700">SMS {n.sms.status.replaceAll('_', ' ')}</span>}
                  </span>
                </div>
              ))}
            </li>
          ))}
        </ol>
      )}
    </Section>
  )
}

function Completed({ trip, events }: { trip: Trip; events: SafetyEvent[] }) {
  const alerts = events.filter((e) => e.type === 'PROLONGED_STOP' || e.type === 'ROUTE_DEVIATION').length
  const sharedSaving = trip.ride_type === 'individual' ? Math.round(trip.individual_fare_zar - (trip.individual_fare_zar * 1.2) / 2) : 0
  return (
    <Section title="Trip completed" icon={<Flag size={18} className="text-brand-600" />}>
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-xl bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Fare</p>
          <p className="text-lg font-extrabold">{fmtZar(trip.fare_zar)}</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Distance</p>
          <p className="text-lg font-extrabold">{trip.distance_km} km</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <p className="text-xs text-slate-500">Safety alerts</p>
          <p className="text-lg font-extrabold">{alerts}</p>
        </div>
      </div>
      <p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
        📅 If you make this trip 10 times a week, that's about <strong>R{Math.round((trip.fare_zar * 10 * 52) / 12).toLocaleString('en-ZA')}</strong> a month
        {trip.ride_type === 'individual' && <> (about R{Math.round((trip.individual_fare_zar * 1.2 / 3) * 10 * 52 / 12).toLocaleString('en-ZA')} shared by 3)</>}.
      </p>
      {sharedSaving > 0 && (
        <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">
          💡 Sharing this ride with one other passenger would have saved you about <strong>R{sharedSaving}</strong>.
        </p>
      )}
      <Link to="/" className="btn-primary mt-3 w-full">
        Book another ride
      </Link>
    </Section>
  )
}

function NotFound({ message }: { message: string }) {
  return (
    <div className="card mx-auto max-w-md p-6 text-center">
      <p className="font-bold">Trip not available</p>
      <p className="text-sm text-slate-500">{message}</p>
      <Link to="/" className="btn-primary mt-4">
        Book a ride
      </Link>
    </div>
  )
}
