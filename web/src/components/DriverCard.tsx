import { useState } from 'react'
import { BadgeCheck, Search, ShieldAlert, Star } from 'lucide-react'
import { api } from '../lib/api'
import type { Driver, DriverLookup } from '../lib/types'
import { SimBadge, Spinner } from './ui'

export default function DriverCard({ driver }: { driver: Driver }) {
  const [check, setCheck] = useState<DriverLookup | null>(null)
  const [busy, setBusy] = useState(false)
  const initials = driver.name.split(' ').map((w) => w[0]).slice(0, 2).join('')

  async function verify() {
    setBusy(true)
    try {
      setCheck(await api.lookup(driver.plate))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="flex items-start gap-4">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-lg font-extrabold text-brand-800">{initials}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-lg font-bold">{driver.name}</p>
            <SimBadge label="Demo driver, not verified" />
          </div>
          <p className="flex items-center gap-1 text-sm text-slate-600">
            <Star size={14} className="fill-gold-400 text-gold-400" /> {driver.rating.toFixed(1)} · {driver.trips_completed.toLocaleString('en-ZA')} trips · since {driver.registered_since}
          </p>
          <p className="mt-1 text-sm text-slate-700">
            {driver.colour} {driver.vehicle}
          </p>
        </div>
        <div className="rounded-lg border-2 border-slate-800 bg-yellow-300 px-2 py-1 font-mono text-sm font-bold tracking-wider text-slate-900 shadow-sm">{driver.plate}</div>
      </div>
      <div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm">
        <p className="font-semibold">Before you get in</p>
        <p className="text-slate-600">Check that the number plate, car and driver match. Sit in the back and keep your trip shared.</p>
        <button className="btn-secondary mt-2 py-1.5" onClick={verify} disabled={busy}>
          {busy ? <Spinner /> : <Search size={14} />} Check plate in MzansiRide registry
        </button>
        {check && (
          <div className={`mt-2 flex gap-2 rounded-lg p-2 ${check.verdict === 'registered' ? 'bg-emerald-50 text-emerald-900' : 'bg-red-50 text-red-900'}`}>
            {check.verdict === 'registered' ? <BadgeCheck size={18} className="shrink-0" /> : <ShieldAlert size={18} className="shrink-0" />}
            <p>
              {check.advice} <span className="text-xs opacity-70">(Demo registry, not an official police check.)</span>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
