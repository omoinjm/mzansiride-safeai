import { useState } from 'react'
import { CalendarDays, Users, User } from 'lucide-react'
import type { Quote } from '../lib/types'
import { fmtZar } from '../lib/format'

const PERIODS = { week: 1, month: 52 / 12, year: 52 } as const
type Period = keyof typeof PERIODS

const rand = (n: number) => `R${Math.round(n).toLocaleString('en-ZA')}`

/** Regular-trip budget: the same trip N times a week, alone vs shared (illustrative fares). */
export function CommuteBudget({ quote }: { quote: Quote }) {
  const [perWeek, setPerWeek] = useState(10)
  const [period, setPeriod] = useState<Period>('month')
  const trips = perWeek * PERIODS[period]
  const alone = quote.options[0].fare_zar * trips
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3">
      <p className="flex items-center gap-1.5 text-sm font-semibold text-emerald-900">
        <CalendarDays size={15} /> Regular trip? Plan your budget
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="trips-per-week">Trips a week</label>
        <input
          id="trips-per-week"
          type="number"
          min={1}
          max={28}
          value={perWeek}
          onChange={(e) => setPerWeek(Math.max(1, Math.min(28, Number(e.target.value) || 1)))}
          className="input w-20 py-1"
        />
        <select aria-label="Budget period" className="input w-auto py-1" value={period} onChange={(e) => setPeriod(e.target.value as Period)}>
          <option value="week">per week</option>
          <option value="month">per month</option>
          <option value="year">per year</option>
        </select>
      </div>
      <table className="mt-2 w-full text-sm" aria-label="Regular trip cost">
        <tbody>
          {quote.options.map((o) => {
            const cost = o.fare_zar * trips
            return (
              <tr key={o.riders} className="border-t border-emerald-100 first:border-0">
                <td className="py-1">{o.riders === 1 ? 'Alone' : `Shared by ${o.riders}`}</td>
                <td className="py-1 text-right font-bold">{rand(cost)}</td>
                <td className="w-28 py-1 text-right text-xs font-semibold text-emerald-700">{o.riders > 1 ? `save ${rand(alone - cost)}` : ''}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="mt-1 text-[11px] text-slate-500">10 a week = to work or class and back, 5 days. Illustrative fares.</p>
    </div>
  )
}

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
      <CommuteBudget quote={quote} />
      <p className="text-[11px] text-slate-500">
        Illustrative fares: base R{quote.rules.base} + R{quote.rules.per_km}/km + R{quote.rules.per_min}/min (minimum R{quote.rules.minimum}). Shared = individual × {1 + quote.rules.shared_detour_factor} ÷ riders. Sample pricing, no payment is processed.
      </p>
    </div>
  )
}
