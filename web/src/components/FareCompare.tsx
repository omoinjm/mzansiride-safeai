import { Users, User } from 'lucide-react'
import type { Quote } from '../lib/types'
import { fmtZar } from '../lib/format'

export default function FareCompare({ quote, riders, onSelect }: { quote: Quote; riders?: number; onSelect?: (r: number) => void }) {
  const max = quote.options[0].fare_zar
  return (
    <div className="space-y-2">
      {quote.options.map((o) => {
        const active = riders === o.riders
        const Icon = o.riders === 1 ? User : Users
        return (
          <button
            type="button"
            key={o.riders}
            onClick={() => onSelect?.(o.riders)}
            disabled={!onSelect}
            className={`w-full rounded-xl border p-3 text-left transition ${active ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-100' : 'border-slate-200 bg-white hover:border-slate-300'} disabled:cursor-default`}
          >
            <div className="flex items-center gap-3">
              <Icon size={18} className="text-brand-700" />
              <div className="flex-1">
                <p className="text-sm font-semibold">{o.type === 'individual' ? 'Individual ride' : `Shared ride · ${o.riders} riders`}</p>
                <p className="text-xs text-slate-500">
                  {o.type === 'individual' ? `${quote.duration_min} min · ${quote.distance_km} km` : `≈ +${o.extra_minutes} min for other pickups`}
                </p>
              </div>
              <div className="text-right">
                <p className="text-base font-bold">{fmtZar(o.fare_zar)}</p>
                {o.saving_zar > 0 && <p className="text-xs font-semibold text-emerald-700">save {fmtZar(o.saving_zar)} ({o.saving_pct}%)</p>}
              </div>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${(o.fare_zar / max) * 100}%` }} />
            </div>
          </button>
        )
      })}
      <p className="text-[11px] text-slate-500">
        Illustrative fares: base R{quote.rules.base} + R{quote.rules.per_km}/km + R{quote.rules.per_min}/min (minimum R{quote.rules.minimum}). Shared = individual × {1 + quote.rules.shared_detour_factor} ÷ riders. Sample pricing, no payment is processed.
      </p>
    </div>
  )
}
