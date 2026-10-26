/**
 * Operator sign-in for the Fleet page. On AWS: Amazon Cognito (user pool from /api/config), called directly over
 * its public JSON API, so no SDK. The ID token goes to the operator endpoints in x-operator-token and API Gateway's
 * JWT authorizer checks it. Local mode (make local) has no Cognito, so the old team code is used instead.
 *
 * Tokens live in sessionStorage: closing the tab signs the operator out.
 */
import type { CognitoConfig } from './types'

type Session =
  | { kind: 'cognito'; email: string; region: string; clientId: string; idToken: string; refreshToken: string; expiresAt: number }
  | { kind: 'code'; code: string }

export type SignInResult = { ok: true } | { ok: false; challenge: 'NEW_PASSWORD_REQUIRED'; session: string }

const KEY = 'mz.operator'
let current: Session | null = load()

function load(): Session | null {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || 'null')
  } catch {
    return null
  }
}

function keep(s: Session | null) {
  current = s
  try {
    if (s) sessionStorage.setItem(KEY, JSON.stringify(s))
    else sessionStorage.removeItem(KEY)
  } catch {
    /* private mode: stays in memory for this page */
  }
}

export const signedIn = () => current !== null
export const operatorName = () => (current?.kind === 'cognito' ? current.email : current ? 'team code' : '')
export const signOut = () => keep(null)
export const signInWithCode = (code: string) => keep({ kind: 'code', code })

async function cognito<T>(region: string, action: string, body: unknown): Promise<T> {
  const res = await fetch(`https://cognito-idp.${region}.amazonaws.com/`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-amz-json-1.1', 'x-amz-target': `AWSCognitoIdentityProviderService.${action}` },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(friendly(data.__type, data.message))
  return data as T
}

function friendly(type = '', message = '') {
  if (type.includes('NotAuthorized')) return 'Wrong email or password.'
  if (type.includes('UserNotFound')) return 'Wrong email or password.'
  if (type.includes('InvalidPassword')) return message || 'That password is too weak.'
  if (type.includes('PasswordResetRequired')) return 'Your password must be reset. Ask the team to reset it.'
  if (type.includes('TooManyRequests') || type.includes('LimitExceeded')) return 'Too many attempts. Wait a minute and try again.'
  return message || 'Sign-in failed.'
}

type AuthResult = { AuthenticationResult?: { IdToken: string; RefreshToken?: string; ExpiresIn: number }; ChallengeName?: string; Session?: string }

function accept(cfg: CognitoConfig, email: string, r: AuthResult, refreshToken?: string): SignInResult {
  if (r.ChallengeName === 'NEW_PASSWORD_REQUIRED') return { ok: false, challenge: 'NEW_PASSWORD_REQUIRED', session: r.Session! }
  const a = r.AuthenticationResult
  if (!a) throw new Error(`Unsupported sign-in step: ${r.ChallengeName}`)
  keep({
    kind: 'cognito', email, region: cfg.region, clientId: cfg.client_id, idToken: a.IdToken,
    refreshToken: a.RefreshToken || refreshToken || '', expiresAt: Date.now() + a.ExpiresIn * 1000,
  })
  return { ok: true }
}

export async function signIn(cfg: CognitoConfig, email: string, password: string) {
  const r = await cognito<AuthResult>(cfg.region, 'InitiateAuth', {
    AuthFlow: 'USER_PASSWORD_AUTH', ClientId: cfg.client_id, AuthParameters: { USERNAME: email, PASSWORD: password },
  })
  return accept(cfg, email, r)
}

/** First sign-in with the emailed temporary password: Cognito asks for a new one. */
export async function setNewPassword(cfg: CognitoConfig, email: string, session: string, password: string) {
  const r = await cognito<AuthResult>(cfg.region, 'RespondToAuthChallenge', {
    ChallengeName: 'NEW_PASSWORD_REQUIRED', ClientId: cfg.client_id, Session: session,
    ChallengeResponses: { USERNAME: email, NEW_PASSWORD: password },
  })
  return accept(cfg, email, r)
}

/** Headers for an operator request; renews the ID token shortly before it expires. */
export async function authHeaders(): Promise<Record<string, string>> {
  const s = current
  if (!s) return {}
  if (s.kind === 'code') return { 'x-team-code': s.code }
  if (s.expiresAt - Date.now() < 2 * 60_000 && s.refreshToken) {
    try {
      const r = await cognito<AuthResult>(s.region, 'InitiateAuth', {
        AuthFlow: 'REFRESH_TOKEN_AUTH', ClientId: s.clientId, AuthParameters: { REFRESH_TOKEN: s.refreshToken },
      })
      accept({ region: s.region, client_id: s.clientId, user_pool_id: '' }, s.email, r, s.refreshToken)
    } catch {
      signOut() // refresh token expired or revoked: sign in again
      return {}
    }
  }
  // A custom header, not Authorization: CloudFront drops Authorization on GET requests (infra/cognito.tf).
  return { 'x-operator-token': (current as Extract<Session, { kind: 'cognito' }>).idToken }
}
