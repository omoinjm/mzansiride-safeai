import type {
  AiResult, AppConfig, Dashboard, DriverLookup, Place, Quote, SafetyEvent, TelemetryResult, Trip,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function req<T>(method: string, path: string, body?: unknown, headers: Record<string, string> = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { 'content-type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(res.status, data.error || `Request failed (${res.status})`)
  return data as T
}

export type BookRequest = {
  pickup: string
  destination: string
  passenger_name: string
  riders: number
  safe_mode: boolean
  trusted_contact?: { name: string; phone: string }
}

export const api = {
  config: () => req<AppConfig>('GET', '/config'),
  places: () => req<{ places: Place[] }>('GET', '/places').then((r) => r.places),
  quote: (pickup: string, destination: string) => req<Quote>('POST', '/quote', { pickup, destination }),
  book: (b: BookRequest) => req<Trip>('POST', '/trips', b),
  trip: (id: string) => req<Trip & { events: SafetyEvent[] }>('GET', `/trips/${id}`),
  start: (id: string) => req<Trip>('POST', `/trips/${id}/start`, {}),
  complete: (id: string) => req<Trip>('POST', `/trips/${id}/complete`, {}),
  safeMode: (id: string, enabled: boolean) => req<Trip>('POST', `/trips/${id}/safe-mode`, { enabled }),
  trustedContact: (id: string, c: { name: string; phone: string }) => req<Trip>('PUT', `/trips/${id}/trusted-contact`, c),
  telemetry: (id: string, t: { lat: number; lng: number; ts: number }) => req<TelemetryResult>('POST', `/trips/${id}/telemetry`, t),
  checkin: (id: string, ev: string, response: 'ok' | 'help', prompt_ms?: number) =>
    req<SafetyEvent>('POST', `/trips/${id}/events/${ev}/checkin`, { response, prompt_ms }),
  explain: (id: string, ev: string) => req<AiResult>('POST', `/trips/${id}/events/${ev}/explain`, {}),
  sos: (id: string, share = false) => req<SafetyEvent>('POST', `/trips/${id}/sos`, { share }),
  lookup: (q: string) => req<DriverLookup>('GET', `/drivers/lookup?q=${encodeURIComponent(q)}`),
  assistant: (message: string, trip_id?: string, history?: { role: string; text: string }[]) =>
    req<AiResult>('POST', '/assistant', { message, trip_id, history }),
  waSimulate: (session: string, text: string) => req<{ replies: string[] }>('POST', '/whatsapp/simulate', { session, text }),
  waOutbox: (session: string) => req<{ messages: { text: string; at: string }[] }>('GET', `/whatsapp/outbox?session=${session}`),
  dashboard: (code: string) => req<Dashboard>('GET', '/dashboard', undefined, { 'x-team-code': code }),
}

export function store<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : (JSON.parse(v) as T)
  } catch {
    return fallback
  }
}

export function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* private mode: ignore */
  }
}
