export type Place = { id: string; name: string; area: string; lat: number; lng: number }

export type FareOption = {
  type: 'individual' | 'shared'
  riders: number
  fare_zar: number
  saving_zar: number
  saving_pct: number
  extra_minutes?: number
}

export type Quote = {
  distance_km: number
  duration_min: number
  currency: string
  options: FareOption[]
  rules: Record<string, number>
  simulated: boolean
  points?: [number, number][]
}

export type Driver = {
  driver_id: string
  name: string
  plate: string
  vehicle: string
  colour: string
  rating: number
  trips_completed: number
  registered_since: string
  status: string
  safety_score?: number
}

export type Route = { distance_m: number; duration_s: number; points: [number, number][]; alternatives?: [number, number][][] }

export type Notification = {
  to_name: string
  to: string
  reason: string
  at: string
  text: string
  channel: string
  status: string
  sms?: { to: string; status: string }
}

export type AiResult = { text: string; source: 'bedrock' | 'guardrail' | 'fallback'; model: string | null }

export type SafetyEvent = {
  trip_id: string
  event_id: string
  type: 'PROLONGED_STOP' | 'ROUTE_DEVIATION' | 'SOS' | 'TRIP_SHARED'
  status: 'awaiting_checkin' | 'resolved_ok' | 'escalated' | 'info'
  created_at: string
  trip_ts?: number
  lat?: number
  lng?: number
  details: { stationary_s?: number; deviation_m?: number; toward_destination?: boolean; channel?: string }
  response?: 'ok' | 'help'
  response_channel?: string
  responded_at?: string
  escalation_reason?: string
  notifications: Notification[]
  prompt_ms?: number
  response_text?: string
  response_reason?: string
  response_understood_by?: string
  unclear_replies?: { text: string; at: string; channel: string }[]
  reminded_at?: string
  escalated_at?: string
  ai?: Record<string, AiResult>
  triage?: AiResult
  operator_ack?: OperatorAck
}

export type OperatorAck = { at: string; action: string }

export type DriverCheck = { status: 'verified' | 'not_verified'; method: string; at: string; simulated: boolean }

export type CheckinReply = { intent: 'ok' | 'help' | 'unclear'; reason: string; source: string; event: SafetyEvent }

export type PhotoCheck = { plate: string | null; lookup: DriverLookup | null; source: string; advice?: string; stored: boolean }

export type Risk = 'red' | 'amber' | 'handled' | 'green'

export type FleetRow = {
  trip_id: string
  passenger_name: string
  pickup_name: string
  destination_name: string
  driver: Driver
  safe_mode: boolean
  whatsapp_channel: WhatsAppChannel | null
  position: { lat: number; lng: number; ts: number; speed_kmh?: number; at: string }
  risk: Risk
  latest_event: SafetyEvent | null
  triage: (AiResult & { event_id: string; operator_ack?: OperatorAck }) | null
}

export type WhatsAppChannel = 'whatsapp' | 'simulator' | 'simulated'

export type Trip = {
  trip_id: string
  passenger_name: string
  pickup: string
  destination: string
  pickup_name: string
  destination_name: string
  ride_type: 'individual' | 'shared'
  riders: number
  fare_zar: number
  individual_fare_zar: number
  distance_km: number
  duration_min: number
  driver: Driver
  status: 'driver_assigned' | 'in_progress' | 'completed' | 'cancelled'
  safe_mode: boolean
  trusted_contact: { name: string; phone: string; delivery?: 'whatsapp' | 'simulated' } | null
  created_at: string
  started_at?: string
  events_count: number
  whatsapp_linked: boolean
  whatsapp_channel?: WhatsAppChannel
  passenger_phone?: string
  last_position?: { lat: number; lng: number; ts: number; speed_kmh?: number }
  driver_check?: DriverCheck
  route?: Route
  events?: SafetyEvent[]
}

export type TelemetryResult = {
  trip: { trip_id: string; status: string; safe_mode: boolean }
  new_events: SafetyEvent[]
  escalated: SafetyEvent[]
  reminded: SafetyEvent[]
  open_events: SafetyEvent[]
  server_ms: number
}

export type DriverLookup = {
  query: string
  matches: Driver[]
  verdict: 'registered' | 'caution' | 'not_found' | 'invalid'
  advice: string
}

export type AppConfig = {
  whatsapp: { enabled: boolean; paused?: boolean; number: string }
  model: string
  guardrail: boolean
  checkin_timeout_s: number
  region: string
  cognito?: CognitoConfig | null
}

export type CognitoConfig = { region: string; user_pool_id: string; client_id: string }

export type OpsConfig = { checkin_timeout_s: number; whatsapp_enabled: boolean }

export type Health = {
  checked_at: string
  whatsapp: {
    status: 'ok' | 'degraded' | 'down' | 'not_configured' | 'paused'
    advice: string
    gateway: { ok: boolean; ms: number | null } | null
    last_sent_at?: string
    last_received_at?: string
    last_error_at?: string
    last_error?: string
  }
  ai: {
    primary_model: string
    fallback_model: string
    last_model?: string
    last_at?: string
    calls_today: number
    via_fallback_model: number
    rules_fallback: number
    status: 'ok' | 'degraded'
  }
  messages_today: Record<
    | 'whatsapp_sent' | 'whatsapp_failed' | 'whatsapp_received' | 'whatsapp_undeliverable' | 'sms_sent' | 'sms_failed'
    | 'contact_alerts_whatsapp' | 'contact_alerts_simulated' | 'contact_alerts_rate_limited',
    number
  >
  errors_last_hour: { api?: number; whatsapp?: number } | null
  dashboard_url?: string
  email_alerts?: { confirmed: number; pending: number } | null
}

export type Dashboard = {
  fleet: FleetRow[]
  summary: {
    trips: number
    active: number
    at_risk: number
    trips_safe_mode: number
    events: number
    events_by_type: Record<string, number>
    events_by_status: Record<string, number>
    responses: { ok: number; help: number; no_response: number }
    notifications: number
    avg_prompt_ms: number | null
  }
  trips: Trip[]
  events: SafetyEvent[]
}
