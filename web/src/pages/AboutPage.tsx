import { CheckCircle2, CircleDashed, FlaskConical } from 'lucide-react'

type Status = 'done' | 'simulated' | 'outstanding'
const FEATURES: [string, Status, string][] = [
  ['Responsive booking interface', 'done', 'React + TypeScript + Tailwind, works on phone and desktop'],
  ['Driver and vehicle details', 'simulated', 'Demo drivers from the DynamoDB registry with an illustrative safety score, labelled "not verified"'],
  ['Safe Journey Mode + journey screen', 'done', 'Map, trip clock, status, check-in state'],
  ['Prolonged-stop and route-deviation rules', 'done', 'Backend rules in Lambda, unit-tested; positions come from the simulator'],
  ['Passenger check-in prompt', 'done', "I'm OK / I need help, plus auto-escalation after 2 min without an answer"],
  ['AI safety assistant (Amazon Bedrock)', 'done', 'Claude via Bedrock with grounded guidance, a Guardrail and a rules-based fallback'],
  ['Fleet safety dashboard (operator)', 'done', 'Live fleet map and list: green / amber / red per trip, speed, AI triage, operator acknowledge'],
  ['AI triage for the operator', 'done', 'When an alert escalates, Bedrock writes a one-sentence next action for the fleet manager (rules-based text if the AI is down)'],
  ['Proactive WhatsApp check-ins', 'done', 'Passenger number at booking, no TRIP code needed. Real messages only for allow-listed demo numbers; others go to the simulator'],
  ['Demo fleet + simulator panel', 'simulated', 'Normal drive / off-route / prolonged stop buttons, and a 5-car demo fleet with one scripted incident'],
  ['Trusted-contact notification', 'simulated', 'Recorded and shown. Real WhatsApp delivery only to allow-listed demo numbers'],
  ['Individual vs shared fare comparison', 'done', 'Illustrative pricing rules, no payments'],
  ['WhatsApp channel (OpenWA)', 'done', 'Driver check, trip link, check-ins, SOS and AI over WhatsApp, plus an in-browser simulator'],
  ['Driver registry lookup (CHECK <plate>)', 'simulated', 'Demo registry only, not an official police or licensing check'],
  ['Live GPS + map-matched deviation', 'outstanding', 'Future: device location + Amazon Location Service routes'],
  ['User accounts (Amazon Cognito)', 'outstanding', 'Future: passenger and operator sign-in, replacing the shared team code'],
  ['Emergency-service integration', 'outstanding', 'Needs partnerships and tested procedures'],
  ['Real driver verification, payments, ride matching', 'outstanding', 'Out of scope for the prototype'],
]

const ICON = {
  done: <CheckCircle2 size={16} className="text-emerald-600" />,
  simulated: <FlaskConical size={16} className="text-amber-600" />,
  outstanding: <CircleDashed size={16} className="text-slate-400" />,
}
const LABEL = { done: 'Completed', simulated: 'Simulated', outstanding: 'Outstanding' }

const SERVICES = [
  ['Amazon CloudFront + S3', 'Hosts the React app over HTTPS from SA edge locations; the bucket is private (OAC).'],
  ['Amazon API Gateway (HTTP API)', 'One HTTPS entry point for the web API and the WhatsApp webhook; throttled.'],
  ['AWS Lambda (Python 3.13, arm64)', 'Trip workflow, safety rules, check-ins, notifications, WhatsApp commands.'],
  ['Amazon Bedrock (Claude Haiku 5.5, Nova Lite fallback)', 'Explains alerts to passengers, answers safety questions, and writes triage actions for the operator.'],
  ['Amazon Bedrock Guardrails', 'Filters harmful content and prompt attacks; denies profiling of drivers.'],
  ['Amazon DynamoDB', 'Trips, safety events, driver registry and WhatsApp chat links (on-demand, TTL).'],
  ['Amazon EC2 + SSM', 'Runs the open-source OpenWA WhatsApp gateway; admin via Systems Manager, with no SSH.'],
  ['AWS Systems Manager Parameter Store', 'Gateway API key and webhook secret (SecureString).'],
  ['Amazon CloudWatch', 'Structured logs, dashboard, error alarms, Bedrock latency and token metrics.'],
]

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold">About MzansiRide SafeAI</h1>
        <p className="mt-2 text-slate-700">
          A safety telemetry and intelligence layer for e-hailing operators in South Africa, built for the AWS AI Hackathon 2026 (theme: AI for Real-World Impact). Instead of a panic button the passenger must press in a crisis, the platform watches trip data, checks in with the passenger on WhatsApp, alerts their trusted contact, and gives the operator's safety team a live fleet view with AI triage. It doesn't claim to prevent crime or guarantee safety.
        </p>
      </div>

      <section className="card p-5">
        <h2 className="mb-3 font-bold">Architecture</h2>
        <img src="/architecture.svg" alt="Architecture diagram: browser and WhatsApp users reach CloudFront, API Gateway and Lambda, which use Bedrock, DynamoDB and the OpenWA gateway on EC2" className="w-full rounded-xl border border-slate-100" />
        <dl className="mt-4 grid gap-2 sm:grid-cols-2">
          {SERVICES.map(([n, d]) => (
            <div key={n} className="rounded-xl bg-slate-50 p-3 text-sm">
              <dt className="font-bold">{n}</dt>
              <dd className="text-slate-600">{d}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="card overflow-hidden">
        <h2 className="p-5 pb-3 font-bold">What's completed, simulated and outstanding</h2>
        <ul className="divide-y divide-slate-100">
          {FEATURES.map(([f, s, note]) => (
            <li key={f} className="flex items-start gap-3 px-5 py-2.5 text-sm">
              <span className="mt-0.5">{ICON[s]}</span>
              <span className="flex-1">
                <strong>{f}</strong>
                <span className="block text-slate-500">{note}</span>
              </span>
              <span className="text-xs font-semibold text-slate-500">{LABEL[s]}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card p-5 text-sm text-slate-700">
        <h2 className="mb-2 font-bold">Responsible AI and privacy</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Rules detect events and AI only explains them, so detection is predictable and testable.</li>
          <li>Alerts are check-ins, not accusations. The assistant is instructed never to blame drivers or predict crime, and a Guardrail denies profiling.</li>
          <li>The AI doesn't replace emergency services: every prompt shows 10111 / 112.</li>
          <li>If Bedrock is unavailable, a rules-based message is shown, so the safety workflow never depends on the AI being up.</li>
          <li>All data is simulated. Phone numbers are masked in the UI and logs, and records expire after 14 days (DynamoDB TTL). POPIA would guide any real data collection.</li>
          <li>No privileged AWS credentials in the browser. Secrets are kept in SSM Parameter Store, and IAM roles are least-privilege.</li>
        </ul>
      </section>
    </div>
  )
}
