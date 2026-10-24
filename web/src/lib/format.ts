import type { SafetyEvent } from './types'

export const EVENT_LABEL: Record<string, string> = {
  PROLONGED_STOP: 'Prolonged stop',
  ROUTE_DEVIATION: 'Route deviation',
  SOS: 'SOS',
  TRIP_SHARED: 'Trip shared',
}

export function describe(e: SafetyEvent) {
  if (e.type === 'PROLONGED_STOP') {
    const m = Math.max(1, Math.round((e.details.stationary_s ?? 0) / 60))
    return `Your vehicle hasn't moved for about ${m} minute${m === 1 ? '' : 's'}.`
  }
  if (e.type === 'ROUTE_DEVIATION') return `Your vehicle is about ${e.details.deviation_m} m away from the planned route.`
  return 'Something unusual happened on this trip.'
}

export function fmtDuration(s: number) {
  const m = Math.floor(s / 60)
  const r = Math.max(0, Math.round(s % 60))
  return `${m}:${String(r).padStart(2, '0')}`
}

export function fmtZar(n: number) {
  return `R${n.toFixed(2)}`
}

export function timeAgo(iso: string) {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return new Date(iso).toLocaleDateString('en-ZA')
}
