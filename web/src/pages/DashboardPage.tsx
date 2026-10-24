import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Activity, Bell, Lock, RefreshCw, ShieldAlert, ShieldCheck, Timer } from 'lucide-react'
import { api, save, store } from '../lib/api'
import type { Dashboard } from '../lib/types'
import { Pill, SimBadge, Spinner } from '../components/ui'
import { EVENT_LABEL, timeAgo } from '../lib/format'

export default function DashboardPage() {
  const [code, setCode] = useState(store('mz.teamCode', ''))
  const [draft, setDraft] = useState('')
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
    const h = setInterval(load, 5000)
    return () => clearInterval(h)
  }, [load])

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
    { label: 'Trips', value: s.trips, sub: `${s.trips_safe_mode} with Safe Journey`, icon: Activity },
    { label: 'Safety events', value: s.events, sub: `${s.events_by_type.PROLONGED_STOP ?? 0} stops · ${s.events_by_type.ROUTE_DEVIATION ?? 0} deviations`, icon: ShieldAlert },
    { label: 'Check-in responses', value: s.responses.ok + s.responses.help, sub: `${s.responses.ok} OK · ${s.responses.help} help · ${s.responses.no_response} no reply`, icon: ShieldCheck },
    { label: 'Notifications', value: s.notifications, sub: 'trusted-contact alerts', icon: Bell },
    { label: 'Avg time to prompt', value: s.avg_prompt_ms != null ? `${s.avg_prompt_ms} ms` : '–', sub: 'event → check-in shown', icon: Timer },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-extrabold">Safety alert dashboard</h1>
        <SimBadge label="Simulated data" />
        <button className="btn-ghost ml-auto" onClick={load} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
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
        <h2 className="border-b border-slate-100 p-4 font-bold">Safety events</h2>
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
