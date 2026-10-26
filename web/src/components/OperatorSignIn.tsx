import { useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import { api } from '../lib/api'
import { setNewPassword, signIn, signInWithCode } from '../lib/auth'
import type { CognitoConfig } from '../lib/types'
import { Spinner } from './ui'

/** Operator sign-in: Amazon Cognito on AWS (email + password, new password on first sign-in); team code locally. */
export default function OperatorSignIn({ error, onSignedIn }: { error?: string; onSignedIn: () => void }) {
  const [cfg, setCfg] = useState<CognitoConfig | null | undefined>(undefined) // undefined: loading, null: local mode
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPw] = useState('')
  const [challenge, setChallenge] = useState('') // Cognito session for NEW_PASSWORD_REQUIRED
  const [msg, setMsg] = useState(error || '')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.config().then((c) => setCfg(c.cognito ?? null)).catch((e) => (setCfg(null), setMsg((e as Error).message)))
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (cfg === null) {
      signInWithCode(password)
      return onSignedIn()
    }
    if (!cfg) return
    setBusy(true)
    setMsg('')
    try {
      const r = challenge ? await setNewPassword(cfg, email.trim(), challenge, newPassword) : await signIn(cfg, email.trim(), password)
      if (r.ok) return onSignedIn()
      setChallenge(r.session)
      setMsg('First sign-in: choose your own password.')
    } catch (err) {
      setMsg((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (cfg === undefined) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8 text-brand-600" /></div>
  return (
    <form className="card mx-auto mt-10 max-w-sm space-y-3 p-6" onSubmit={submit}>
      <h1 className="flex items-center gap-2 text-lg font-extrabold">
        <Lock size={18} /> Operator dashboard
      </h1>
      {cfg ? (
        <>
          <p className="text-sm text-slate-600">For the operator's safety team. Sign in with your work email (Amazon Cognito).</p>
          <input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" disabled={!!challenge} autoFocus />
          {challenge ? (
            <input className="input" type="password" autoComplete="new-password" value={newPassword} onChange={(e) => setNewPw(e.target.value)} placeholder="New password (12+ characters)" autoFocus />
          ) : (
            <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
          )}
        </>
      ) : (
        <>
          <p className="text-sm text-slate-600">Local mode: enter the team code.</p>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Team code" autoFocus />
        </>
      )}
      {msg && <p className={`text-sm ${msg.startsWith('First') ? 'text-slate-700' : 'text-red-700'}`}>{msg}</p>}
      <button className="btn-primary w-full" disabled={busy || !(challenge ? newPassword : password) || (!!cfg && !email)}>
        {busy ? 'Signing in…' : challenge ? 'Set password and sign in' : cfg ? 'Sign in' : 'Open dashboard'}
      </button>
      {cfg && !challenge && <p className="text-xs text-slate-500">No account? Operators are invited by the team; the invite email has a temporary password.</p>}
    </form>
  )
}
