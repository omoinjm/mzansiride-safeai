/**
 * Demo fleet for the operator dashboard: books a handful of simulated trips and drives them on the trip
 * clock, so the fleet view shows mostly green trips and one that goes wrong. Like the trip page, this only
 * produces positions (and one scripted passenger answer); the backend rules decide what is unusual.
 */
import { api, waSession } from './api'
import { Sim } from './sim'

type Script = 'normal' | 'off_route_ok' | 'stopped_off_route'

const DEMO: { name: string; from: string; to: string; script: Script; whatsapp?: boolean }[] = [
  // Goes off-route, stops, and never answers the WhatsApp check-in: escalates, AI triage, red.
  { name: 'Sarah', from: 'rosebank', to: 'sandton', script: 'stopped_off_route', whatsapp: true },
  // Short detour, answers "I'm OK" a few seconds later: amber, then back to green.
  { name: 'Thabo', from: 'wits', to: 'park-station', script: 'off_route_ok' },
  { name: 'Aisha', from: 'maponya', to: 'uj-apk', script: 'normal' },
  { name: 'Lwazi', from: 'sandton', to: 'wits', script: 'normal' },
  { name: 'Naledi', from: 'uj-apk', to: 'rosebank', script: 'normal' },
]

const STEP_S = 30 // trip seconds per real second

type Car = { tripId: string; sim: Sim; script: Script; ticks: number; openEvent?: string; answerAt?: number; done: boolean }

export class FleetDemo {
  private cars: Car[] = []
  private timer: ReturnType<typeof setInterval> | undefined
  private busy = false

  get running() {
    return this.timer !== undefined
  }

  async start(onLog: (msg: string) => void) {
    this.cars = await Promise.all(
      DEMO.map(async (d) => {
        const trip = await api.book({
          pickup: d.from,
          destination: d.to,
          passenger_name: `${d.name} (demo fleet)`,
          riders: 1,
          safe_mode: true,
          trusted_contact: { name: `${d.name}'s contact`, phone: '082 000 0000' },
          // Sarah's check-ins go to this browser's WhatsApp simulator, where nobody answers.
          ...(d.whatsapp ? { passenger_phone: '082 000 0001', wa_session: waSession() } : {}),
        })
        await api.start(trip.trip_id)
        return { tripId: trip.trip_id, sim: new Sim(trip.route!.points, trip.route!.duration_s), script: d.script, ticks: 0, done: false }
      }),
    )
    onLog(`Demo fleet started: ${this.cars.length} simulated trips`)
    this.timer = setInterval(() => this.tick(onLog), 1000)
  }

  private async tick(onLog: (msg: string) => void) {
    if (this.busy) return
    this.busy = true
    try {
      await Promise.all(this.cars.filter((c) => !c.done).map((c) => this.drive(c, onLog)))
    } finally {
      this.busy = false
    }
  }

  private async drive(c: Car, onLog: (msg: string) => void) {
    c.ticks++
    if (c.script === 'stopped_off_route') {
      if (c.ticks === 4) c.sim.deviate()
      if (c.ticks === 7) c.sim.stop()
    }
    if (c.script === 'off_route_ok' && c.ticks === 3) c.sim.deviate()
    const s = c.sim.step(STEP_S)
    const res = await api.telemetry(c.tripId, { lat: s.pos[0], lng: s.pos[1], ts: s.ts })
    for (const ev of res.new_events) onLog(`${c.tripId}: ${ev.type.replaceAll('_', ' ').toLowerCase()} detected`)
    for (const ev of res.escalated) onLog(`${c.tripId}: no answer to check-in, escalated (${ev.triage?.source === 'fallback' ? 'rules' : 'AI'} triage)`)
    if (c.script === 'off_route_ok') {
      if (res.new_events[0] && !c.openEvent) {
        c.openEvent = res.new_events[0].event_id
        c.answerAt = c.ticks + 3
      }
      if (c.openEvent && c.ticks === c.answerAt) {
        // Answers in their own words; the AI decides whether that means OK. Unclear (e.g. no AI locally): taps OK.
        const r = await api.reply(c.tripId, c.openEvent, 'Driver took a detour around traffic, still heading to Park Station')
        if (r.intent !== 'ok') await api.checkin(c.tripId, c.openEvent, 'ok')
        c.sim.resume()
        onLog(r.intent === 'ok' ? `${c.tripId}: AI read the reply as OK (${r.reason})` : `${c.tripId}: passenger answered "I'm OK"`)
      }
    }
    if (s.mode === 'arrived') {
      c.done = true
      await api.complete(c.tripId)
      onLog(`${c.tripId}: arrived`)
    }
  }

  async stop() {
    clearInterval(this.timer)
    this.timer = undefined
    await Promise.all(this.cars.filter((c) => !c.done).map((c) => api.complete(c.tripId).catch(() => undefined)))
    this.cars = []
  }
}
