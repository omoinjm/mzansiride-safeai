import { useEffect } from 'react'
import L from 'leaflet'
import { MapContainer, Marker, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { FleetRow, Risk } from '../lib/types'
import { RISK_COLOUR } from '../lib/format'

function carIcon(risk: Risk) {
  const c = RISK_COLOUR[risk]
  return L.divIcon({
    className: '',
    html: `<div style="position:relative;width:24px;height:24px">
      ${risk === 'red' || risk === 'amber' ? `<span class="car-pulse" style="position:absolute;inset:-4px;border-radius:9999px;background:${c}66"></span>` : ''}
      <span style="position:absolute;inset:3px;border-radius:9999px;background:${c};border:3px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4)"></span>
    </div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  })
}

const JOBURG: L.LatLngBoundsExpression = [
  [-26.27, 27.9],
  [-26.1, 28.07],
]

function Fit() {
  const map = useMap()
  useEffect(() => {
    map.fitBounds(JOBURG, { padding: [10, 10] })
  }, [map])
  return null
}

export default function FleetMap({ fleet, className = 'h-80' }: { fleet: FleetRow[]; className?: string }) {
  return (
    <div className={`overflow-hidden rounded-2xl border border-slate-200 ${className}`}>
      <MapContainer center={[-26.18, 28.0]} zoom={12} className="h-full w-full" scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Fit />
        {fleet.map((f) => (
          <Marker key={f.trip_id} position={[f.position.lat, f.position.lng]} icon={carIcon(f.risk)} zIndexOffset={f.risk === 'red' ? 1000 : 0}>
            <Tooltip>
              {f.trip_id} · {f.passenger_name} · {f.position.speed_kmh ?? 0} km/h
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
