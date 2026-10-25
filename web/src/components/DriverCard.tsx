import { useRef, useState } from 'react'
import { BadgeCheck, Camera, Fingerprint, Search, ShieldAlert, Star } from 'lucide-react'
import { api } from '../lib/api'
import type { Driver, DriverCheck, DriverLookup } from '../lib/types'
import { SimBadge, Spinner } from './ui'

/** Shrinks a photo to at most 1024 px (JPEG) before upload, and returns it as base64 without the data: prefix. */
async function shrink(file: File): Promise<string> {
  const img = await createImageBitmap(file)
  const scale = Math.min(1, 1024 / Math.max(img.width, img.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(img.width * scale)
  canvas.height = Math.round(img.height * scale)
  canvas.getContext('2d')!.drawImage(img, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
}

export default function DriverCard({ driver, check: faceId }: { driver: Driver; check?: DriverCheck }) {
  const [check, setCheck] = useState<DriverLookup | null>(null)
  const [busy, setBusy] = useState(false)
  const [photo, setPhoto] = useState<{ busy: boolean; plate?: string | null; note?: string }>({ busy: false })
  const fileInput = useRef<HTMLInputElement>(null)

  async function photoCheck(file?: File) {
    if (!file) return
    setPhoto({ busy: true })
    setCheck(null)
    try {
      const r = await api.photoCheck(await shrink(file), 'image/jpeg')
      setPhoto({ busy: false, plate: r.plate, note: r.plate ? undefined : r.advice })
      if (r.lookup) setCheck(r.lookup)
    } catch (e) {
      setPhoto({ busy: false, note: (e as Error).message })
    } finally {
      if (fileInput.current) fileInput.current.value = ''
    }
  }
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
            {driver.safety_score != null && <> · safety score {driver.safety_score}/100</>}
          </p>
          <p className="mt-1 text-sm text-slate-700">
            {driver.colour} {driver.vehicle}
          </p>
        </div>
        <div className="rounded-lg border-2 border-slate-800 bg-yellow-300 px-2 py-1 font-mono text-sm font-bold tracking-wider text-slate-900 shadow-sm">{driver.plate}</div>
      </div>
      <div
        className={`mt-3 flex items-start gap-2 rounded-xl p-3 text-sm ${
          !faceId ? 'bg-slate-50 text-slate-600' : faceId.status === 'verified' ? 'bg-emerald-50 text-emerald-900' : 'bg-amber-50 text-amber-900'
        }`}
      >
        <Fingerprint size={18} className="mt-0.5 shrink-0" />
        <p className="flex-1">
          {!faceId
            ? 'The driver unlocks the app with Face ID when the ride starts. The result shows here.'
            : faceId.status === 'verified'
              ? 'Driver verified with Face ID at the start of this ride.'
              : 'Driver not verified with Face ID for this ride. You decide: go ahead, ask for another ride, or share your trip first.'}
        </p>
        <SimBadge label="Simulated" />
      </div>
      <div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm">
        <p className="font-semibold">Before you get in</p>
        <p className="text-slate-600">Check that the number plate, car and driver match. Sit in the back and keep your trip shared.</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="btn-secondary py-1.5" onClick={verify} disabled={busy}>
            {busy ? <Spinner /> : <Search size={14} />} Check plate in MzansiRide registry
          </button>
          <button className="btn-secondary py-1.5" onClick={() => fileInput.current?.click()} disabled={photo.busy}>
            {photo.busy ? <Spinner /> : <Camera size={14} />} Check plate from a photo
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            aria-label="Number plate photo"
            onChange={(e) => photoCheck(e.target.files?.[0])}
          />
        </div>
        {photo.plate && (
          <p className="mt-2 text-xs text-slate-600">
            AI read the plate as <strong className="font-mono">{photo.plate}</strong>. The photo isn't stored.
          </p>
        )}
        {photo.note && <p className="mt-2 text-xs font-semibold text-amber-800">{photo.note}</p>}
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
