/**
 * Journey simulator (proposal 8.2: no live GPS). Moves a virtual car along the planned route on a
 * "trip clock" and can inject the two demo scenarios. The backend decides whether anything is
 * unusual. This class only produces positions.
 */
export type SimMode = 'driving' | 'stopped' | 'detour' | 'returning' | 'arrived'

export type SimSnapshot = {
  ts: number // trip time in seconds
  pos: [number, number]
  mode: SimMode
  progress: number // 0..1 along the route
  offsetM: number // distance pushed off the route (detour)
  stoppedFor: number // trip seconds stationary
  trail: [number, number][] // detour path for the map
}

const M_PER_DEG = 111_320

export class Sim {
  private pts: [number, number][]
  private cum: number[]
  private total: number
  private speed: number // m per trip second
  ts = 0
  dist = 0
  mode: SimMode = 'driving'
  offsetM = 0
  stoppedSince = 0
  private perp: [number, number] = [0, 0] // unit vector (east, north)
  trail: [number, number][] = []

  constructor(points: [number, number][], durationS: number, start?: { lat: number; lng: number; ts: number }) {
    this.pts = points
    this.cum = [0]
    for (let i = 1; i < points.length; i++) this.cum.push(this.cum[i - 1] + metres(points[i - 1], points[i]))
    this.total = this.cum[this.cum.length - 1]
    this.speed = this.total / Math.max(60, durationS)
    if (start) {
      // resume after a page reload: continue the trip clock (the backend ignores older readings)
      this.ts = start.ts
      let best = 0
      let bestD = Infinity
      points.forEach((p, i) => {
        const d = metres(p, [start.lat, start.lng])
        if (d < bestD) {
          bestD = d
          best = i
        }
      })
      this.dist = this.cum[best]
    }
  }

  private base(): [number, number] {
    const d = Math.min(this.dist, this.total)
    const i = this.cum.findIndex((c) => c >= d)
    if (i <= 0) return this.pts[0]
    const seg = this.cum[i] - this.cum[i - 1] || 1
    const t = (d - this.cum[i - 1]) / seg
    const a = this.pts[i - 1]
    const b = this.pts[i]
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
  }

  position(): [number, number] {
    const [lat, lng] = this.base()
    if (!this.offsetM) return [lat, lng]
    return [lat + (this.perp[1] * this.offsetM) / M_PER_DEG, lng + (this.perp[0] * this.offsetM) / (M_PER_DEG * Math.cos((lat * Math.PI) / 180))]
  }

  step(stepS: number) {
    this.ts += stepS
    if (this.mode === 'driving') {
      this.dist = Math.min(this.total, this.dist + this.speed * stepS)
      if (this.dist >= this.total) this.mode = 'arrived'
    } else if (this.mode === 'detour') {
      this.offsetM = Math.min(900, this.offsetM + (130 * stepS) / 15)
      this.trail.push(this.position())
    } else if (this.mode === 'returning') {
      this.offsetM = Math.max(0, this.offsetM - (250 * stepS) / 15)
      this.trail.push(this.position())
      if (this.offsetM === 0) {
        this.mode = 'driving'
        this.trail = []
      }
    }
    return this.snapshot()
  }

  /** Stops where the car is, also mid-detour ("stopped off-route"). */
  stop() {
    if (this.mode === 'driving' || this.mode === 'detour') {
      this.mode = 'stopped'
      this.stoppedSince = this.ts
    }
  }

  deviate() {
    if (this.mode !== 'driving') return
    const a = this.base()
    const ahead = Math.min(this.total, this.dist + 60)
    const saved = this.dist
    this.dist = ahead
    const b = this.base()
    this.dist = saved
    const east = (b[1] - a[1]) * Math.cos((a[0] * Math.PI) / 180)
    const north = b[0] - a[0]
    const len = Math.hypot(east, north) || 1
    this.perp = [-north / len, east / len] // 90° left of travel direction
    this.mode = 'detour'
    this.trail = [this.position()]
  }

  resume() {
    if (this.mode === 'stopped') this.mode = this.offsetM ? 'returning' : 'driving'
    else if (this.mode === 'detour') this.mode = 'returning'
  }

  snapshot(): SimSnapshot {
    return {
      ts: this.ts,
      pos: this.position(),
      mode: this.mode,
      progress: this.total ? this.dist / this.total : 0,
      offsetM: Math.round(this.offsetM),
      stoppedFor: this.mode === 'stopped' ? this.ts - this.stoppedSince : 0,
      trail: [...this.trail],
    }
  }
}

function metres(a: [number, number], b: [number, number]) {
  const toRad = Math.PI / 180
  const dLat = (b[0] - a[0]) * toRad
  const dLng = (b[1] - a[1]) * toRad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * toRad) * Math.cos(b[0] * toRad) * Math.sin(dLng / 2) ** 2
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h))
}
