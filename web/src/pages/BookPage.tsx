import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowDownUp, Car, MapPin, MessageCircle, ShieldCheck, Sparkles, UsersRound } from 'lucide-react'
import { api, save, store, waSession } from '../lib/api'
import type { Place, Quote } from '../lib/types'
import FareCompare from '../components/FareCompare'
import TripMap from '../components/TripMap'
import { SimBadge, Spinner } from '../components/ui'

export default function BookPage() {
  const nav = useNavigate()
  const [places, setPlaces] = useState<Place[]>([])
  const [pickup, setPickup] = useState('rosebank')
  const [destination, setDestination] = useState('sandton')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [points, setPoints] = useState<[number, number][]>([])
  const [riders, setRiders] = useState(1)
  const [name, setName] = useState(store('mz.name', ''))
  const [contactName, setContactName] = useState(store('mz.contactName', ''))
  const [contactPhone, setContactPhone] = useState(store('mz.contactPhone', ''))
  const [waPhone, setWaPhone] = useState(store('mz.waPhone', ''))
  const [safe, setSafe] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.places().then(setPlaces).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    setQuote(null)
    if (!pickup || !destination || pickup === destination) return
    api.quote(pickup, destination).then(setQuote).catch((e) => setError(e.message))
  }, [pickup, destination])

  useEffect(() => {
    setPoints(quote?.points ?? [])
  }, [quote])

  async function book(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    save('mz.name', name)
    save('mz.contactName', contactName)
    save('mz.contactPhone', contactPhone)
    save('mz.waPhone', waPhone)
    try {
      const trip = await api.book({
        pickup,
        destination,
        passenger_name: name || 'Passenger',
        riders,
        safe_mode: safe,
        trusted_contact: contactPhone ? { name: contactName, phone: contactPhone } : undefined,
        passenger_phone: waPhone || undefined,
        wa_session: waPhone ? waSession() : undefined,
      })
      save('mz.trip', trip.trip_id)
      nav(`/trip/${trip.trip_id}`)
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
      <div className="space-y-5">
        <div className="rounded-3xl bg-gradient-to-br from-brand-700 via-brand-600 to-brand-800 p-6 text-white shadow-lg sm:p-8">
          <p className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold">
            <ShieldCheck size={14} /> Safety-first ride sharing for South Africa
          </p>
          <h1 className="text-3xl font-extrabold leading-tight sm:text-4xl">
            Get there safely.
            <br />
            <span className="text-gold-400">Someone's always checking in.</span>
          </h1>
          <p className="mt-3 max-w-xl text-brand-50">
            You shouldn't have to press a panic button in a crisis. Safe Journey Mode watches the trip data for unexpected stops and route changes, checks in with you on WhatsApp (no mobile data needed), and alerts your trusted contact and the operator's safety team if you need help or don't answer.
          </p>
          <Link
            to="/assistant"
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gold-400 px-4 py-3 text-sm font-bold text-brand-900 shadow hover:bg-gold-500"
          >
            <Sparkles size={18} /> Ask the AI safety assistant
          </Link>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs sm:max-w-md">
            {[
              { icon: ShieldCheck, t: 'Check-ins' },
              { icon: Sparkles, t: 'AI guidance' },
              { icon: MessageCircle, t: 'WhatsApp' },
            ].map(({ icon: I, t }) => (
              <div key={t} className="rounded-xl bg-white/10 p-2">
                <I className="mx-auto mb-1" size={18} />
                {t}
              </div>
            ))}
          </div>
        </div>
        <TripMap points={points} className="hidden h-80 lg:block" />
      </div>

      <form onSubmit={book} className="card space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-extrabold">
            <Car className="text-brand-600" /> Request a ride
          </h2>
          <SimBadge />
        </div>

        <div className="relative space-y-2">
          <label className="block">
            <span className="label">Pickup</span>
            <div className="relative">
              <MapPin size={16} className="absolute top-3 left-3 text-teal-700" />
              <select className="input pl-9" value={pickup} onChange={(e) => setPickup(e.target.value)}>
                {places.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.area})
                  </option>
                ))}
              </select>
            </div>
          </label>
          <button
            type="button"
            aria-label="Swap pickup and destination"
            onClick={() => {
              setPickup(destination)
              setDestination(pickup)
            }}
            className="absolute top-[52px] right-10 z-10 rounded-full border border-slate-200 bg-white p-1.5 shadow-sm hover:bg-slate-50"
          >
            <ArrowDownUp size={14} />
          </button>
          <label className="block">
            <span className="label">Destination</span>
            <div className="relative">
              <MapPin size={16} className="absolute top-3 left-3 text-amber-700" />
              <select className="input pl-9" value={destination} onChange={(e) => setDestination(e.target.value)}>
                {places.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.area})
                  </option>
                ))}
              </select>
            </div>
          </label>
          <p className="text-[11px] text-slate-500">Prototype: choose from predefined Johannesburg locations on real road routes.</p>
        </div>

        <div>
          <span className="label flex items-center gap-1">
            <UsersRound size={14} /> Ride type and fare
          </span>
          {pickup === destination ? (
            <p className="text-sm text-red-700">Pickup and destination must be different.</p>
          ) : quote ? (
            <FareCompare quote={quote} riders={riders} onSelect={setRiders} />
          ) : (
            <div className="flex justify-center py-6">
              <Spinner className="text-brand-600" />
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="label">Your name</span>
            <input className="input" placeholder="e.g. Thandi" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="block">
            <span className="label flex items-center gap-1">
              <MessageCircle size={13} className="text-emerald-600" /> Your WhatsApp
            </span>
            <input className="input" placeholder="WhatsApp number" inputMode="tel" value={waPhone} onChange={(e) => setWaPhone(e.target.value)} />
          </label>
        </div>
        <p className="-mt-2 text-[11px] text-slate-500">
          Optional: we'll check in on WhatsApp if the trip looks unusual. Messages come from our prototype number.
        </p>

        <div className="rounded-xl border border-slate-200 p-3">
          <p className="label">Trusted contact (optional)</p>
          <div className="grid grid-cols-2 gap-2">
            <input className="input" placeholder="Name" value={contactName} onChange={(e) => setContactName(e.target.value)} />
            <input className="input" placeholder="082 123 4567" inputMode="tel" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} />
          </div>
          <p className="mt-1 text-[11px] text-slate-500">They're only contacted if you ask for help, send SOS or miss a check-in.</p>
        </div>

        <label className="flex cursor-pointer items-center gap-3 rounded-xl bg-brand-50 p-3">
          <input type="checkbox" className="h-5 w-5 accent-brand-600" checked={safe} onChange={(e) => setSafe(e.target.checked)} />
          <span className="text-sm">
            <strong>Safe Journey Mode</strong>
            <br />
            <span className="text-slate-600">Check-ins if the trip stops unexpectedly or leaves the route.</span>
          </span>
        </label>

        {error && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-800">{error}</p>}
        <button className="btn-primary w-full py-3 text-base" disabled={busy || !quote}>
          {busy ? <Spinner /> : <Car size={18} />} Request simulated ride
        </button>
        <p className="text-center text-[11px] text-slate-500">No real booking or payment is made.</p>
      </form>
    </div>
  )
}
