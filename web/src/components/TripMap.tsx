import { useEffect, useMemo } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { SafetyEvent } from '../lib/types'

const carIcon = L.divIcon({
  className: '',
  html: `<div style="position:relative;width:28px;height:28px">
    <span class="car-pulse" style="position:absolute;inset:0;border-radius:9999px;background:rgba(7,138,102,.35)"></span>
    <span style="position:absolute;inset:4px;border-radius:9999px;background:#078a66;border:3px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4)"></span>
  </div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
})

function pin(color: string, letter: string) {
  return L.divIcon({
    className: '',
    html: `<div style="width:26px;height:26px;border-radius:9999px 9999px 9999px 0;transform:rotate(-45deg);background:${color};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center"><b style="transform:rotate(45deg);color:white;font:700 12px Inter,sans-serif">${letter}</b></div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 26],
  })
}
const pickupIcon = pin('#0f766e', 'A')
const destIcon = pin('#b45309', 'B')

function Fit({ points }: { points: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [30, 30] })
  }, [map, points])
  return null
}

export default function TripMap({
  points,
  car,
  trail,
  events = [],
  className = 'h-72',
}: {
  points: [number, number][]
  car?: [number, number] | null
  trail?: [number, number][]
  events?: SafetyEvent[]
  className?: string
}) {
  const center = useMemo<[number, number]>(() => points[Math.floor(points.length / 2)] ?? [-26.15, 28.04], [points])
  return (
    <div className={`overflow-hidden rounded-2xl border border-slate-200 ${className}`}>
      <MapContainer center={center} zoom={13} className="h-full w-full" scrollWheelZoom={false} attributionControl>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Fit points={points} />
        <Polyline positions={points} pathOptions={{ color: '#078a66', weight: 5, opacity: 0.75 }} />
        {trail && trail.length > 1 && <Polyline positions={trail} pathOptions={{ color: '#dc2626', weight: 4, dashArray: '6 6' }} />}
        {points.length > 0 && <Marker position={points[0]} icon={pickupIcon} />}
        {points.length > 0 && <Marker position={points[points.length - 1]} icon={destIcon} />}
        {events
          .filter((e) => e.lat != null && e.lng != null)
          .map((e) => (
            <CircleMarker
              key={e.event_id}
              center={[e.lat!, e.lng!]}
              radius={9}
              pathOptions={{ color: e.status === 'escalated' ? '#dc2626' : e.status === 'resolved_ok' ? '#059669' : '#d97706', fillOpacity: 0.5 }}
            >
              <Tooltip>{e.type.replaceAll('_', ' ').toLowerCase()}</Tooltip>
            </CircleMarker>
          ))}
        {car && <Marker position={car} icon={carIcon} zIndexOffset={1000} />}
      </MapContainer>
    </div>
  )
}
