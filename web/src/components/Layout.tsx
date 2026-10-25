import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { Car, Info, LayoutDashboard, MessageCircle, Navigation, Sparkles } from 'lucide-react'
import { store } from '../lib/api'

export default function Layout() {
  const { pathname } = useLocation() // re-render on navigation so "My trip" appears after booking
  const currentTrip = store<string | null>('mz.trip', null)
  const nav = [
    { to: '/', label: 'Ride', icon: Car, end: true },
    ...(currentTrip ? [{ to: `/trip/${currentTrip}`, label: 'My trip', icon: Navigation, end: false }] : []),
    { to: '/assistant', label: 'Assistant', icon: Sparkles, end: false },
    { to: '/whatsapp', label: 'WhatsApp', icon: MessageCircle, end: false },
    { to: '/dashboard', label: 'Fleet', icon: LayoutDashboard, end: false },
    { to: '/about', label: 'About', icon: Info, end: false },
  ]
  return (
    <div className="flex min-h-full flex-col">
      <div className="bg-amber-100 px-4 py-1 text-center text-[11px] font-medium text-amber-900">
        Hackathon prototype: trips, drivers, alerts and notifications are <strong>simulated</strong>. In an emergency call <a className="underline" href="tel:10111">10111</a> or <a className="underline" href="tel:112">112</a>.
      </div>
      <header className="sticky top-0 z-[1000] border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2">
            <img src="/logo.svg" alt="" className="h-8 w-8" />
            <span className="text-lg font-extrabold tracking-tight text-brand-800">
              MzansiRide <span className="text-gold-500">SafeAI</span>
            </span>
          </NavLink>
          <nav className="ml-auto hidden gap-1 md:flex">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold ${isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`
                }
              >
                <Icon size={16} /> {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-4 pb-24 md:pb-10">
        <Outlet />
      </main>
      {pathname !== '/assistant' && (
        <Link
          to="/assistant"
          className="fixed right-4 bottom-20 z-[1100] flex items-center gap-2 rounded-full bg-brand-600 px-4 py-3 text-sm font-bold text-white shadow-lg ring-4 ring-white hover:bg-brand-700 md:bottom-6"
        >
          <Sparkles size={18} /> Ask AI
        </Link>
      )}
      <nav className="fixed inset-x-0 bottom-0 z-[1000] grid border-t border-slate-200 bg-white md:hidden" style={{ gridTemplateColumns: `repeat(${nav.length}, minmax(0, 1fr))` }}>
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `flex flex-col items-center gap-0.5 py-2 text-[10px] font-semibold ${isActive ? 'text-brand-700' : 'text-slate-500'}`}
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
