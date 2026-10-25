# AWS services: what, why, trade-offs, and tough questions

Read this together before Monday. Every service below answers four questions: **what it does in our app**, **why we chose it**,
**what it costs or limits**, and **what we'd use instead**. Prices are approximate (eu-west-1, late 2026). Check the
[AWS pricing pages](https://aws.amazon.com/pricing/) if asked for exact figures.

## The one-minute version
> "The browser loads the React app from **CloudFront/S3**. API calls go to **API Gateway**, which runs **Lambda** functions.
> Lambda applies our safety rules, stores trips and alerts in **DynamoDB**, and asks **Bedrock** (Claude) to explain alerts,
> with a **Guardrail** on top. WhatsApp messages arrive through **OpenWA** on a small **EC2** server and are handled by a
> second Lambda using the same code. Secrets live in **SSM Parameter Store**, logs and alarms in **CloudWatch**, and it's all
> **Terraform**, deployed from GitHub with **OIDC**."

---

## Amazon Bedrock (+ Guardrails)
- **What:** `Converse` API call to **Claude Haiku 5.5** (EU cross-region inference profile `eu.anthropic.claude-haiku-5-5`), with **Amazon Nova Lite** as an automatic second model if Claude is refused (for example, model access not yet granted). Two uses: explain an alert, and answer chat questions (web + WhatsApp). The system prompt contains our approved guidance (`src/core/guidance.md`) and strict rules (no blame, no crime prediction, always 10111/112).
- **Why:** fully managed, so there are no GPU servers. It's pay-per-token, the data isn't used to train models, IAM controls access, and Guardrails are built in. Haiku-class models answer in 1–3 s and cost fractions of a cent.
- **Cost:** about 2.5k input + 200 output tokens per call, roughly **$0.003–0.004 per explanation**. 1,000 alerts ≈ $4. We cache each explanation on the event so re-opening doesn't bill twice.
- **Limits:** the model can be wrong, and it only knows the guidance we give it. Bedrock isn't in **af-south-1** (Cape Town), so we run in **eu-west-1** and accept about 170 ms of extra latency. Data leaves SA, which matters for **POPIA** in production (cross-border transfer rules).
- **Alternatives:**
  - *SageMaker endpoint with an open model*: more control, but you pay for an always-on instance and manage scaling. Overkill here.
  - *Bedrock Knowledge Bases (RAG)*: the right move once guidance grows beyond about 2 pages. It needs a vector store (OpenSearch Serverless has a minimum monthly cost), so for one short document the system prompt is cheaper, simpler and easier to test.
  - *Bedrock Agents*: not needed. Our "tools" are deterministic code, and we deliberately keep the AI out of decision-making.
- **Guardrail settings worth explaining:** hate/insults/sexual/misconduct filters, a **prompt-attack** filter on input, and a **denied topic "criminal profiling"**. The **violence filter is off for user input**: a passenger typing "he has a knife" must get help, not a block. Output is still filtered.

## AWS Lambda
- **What:** two functions from one code zip. `api` handles trips, the rules engine, check-ins, escalation, notifications, the assistant and the dashboard. `whatsapp` handles the OpenWA webhook (HMAC check, dedupe, async processing, replies).
- **Why:** pay per request, scales to zero, no servers to patch. Python 3.13 on **arm64 (Graviton)**, which is about 20% cheaper. There are no third-party dependencies, so packaging is trivial.
- **Limits:** cold starts (~300–600 ms, fine here). A new account's concurrency limit is 10. The **API Gateway 30 s timeout** is fine because Bedrock calls are short. WhatsApp processing is async, because OpenWA times out webhooks after 10 s and retries.
- **Alternatives:** *ECS Fargate / App Runner* for a long-running API: no cold starts, but you pay 24/7. *Step Functions* for the escalation timer: we escalate on the next telemetry reading instead, which is simpler. In production, live GPS would use **EventBridge Scheduler** or Step Functions to escalate even if the phone goes silent (see the tough questions).

## Amazon API Gateway (HTTP API)
- **What:** `ANY /api/{proxy+}` → `api` Lambda, `POST /whatsapp/webhook` → `whatsapp` Lambda. Throttle of 25 rps, burst 50. Access logs go to CloudWatch.
- **Why HTTP API rather than REST API:** about 70% cheaper and lower latency, and we don't need REST-only features (API keys/usage plans, request validation, WAF directly on the API).
- **Alternative:** *Lambda Function URLs* would work, but there would be two URLs and no throttling or route-level control. *ALB* is for container backends.

## Amazon CloudFront + Amazon S3
- **What:** the SPA is in a **private** S3 bucket and served only through CloudFront (Origin Access Control). `/api/*` is forwarded to API Gateway uncached. A CloudFront Function rewrites SPA routes to `index.html`, so real API 404s still return JSON.
- **Why:** HTTPS for free, edge locations in **Johannesburg and Cape Town** (fast first load for SA users), one origin for page + API (no CORS), and assets cached for a year (file names are content-hashed).
- **Alternative:** *AWS Amplify Hosting* (mentioned in our proposal) is simpler click-ops with built-in CI. We chose S3+CloudFront because everything else is Terraform and it gives us the `/api` same-origin routing and security headers explicitly.

## Amazon DynamoDB
- **What:** 4 on-demand tables: `trips`, `events` (pk trip, sk event: check-ins and notifications), `drivers` (demo registry, seeded by Terraform), `whatsapp` (chat↔trip links, webhook dedupe with a conditional put, simulator outbox). TTL deletes data after 14 days.
- **Why:** serverless and pay-per-request, with single-digit-ms key lookups. Our access patterns are simple key lookups ("get trip", "events for trip"). TTL handles data minimisation for free.
- **Limits:** the dashboard uses `Scan`, which is fine for demo volumes. In production we'd add a GSI (e.g. `status#date`) or stream events to analytics. There are no joins, so the driver is copied into the trip (denormalised).
- **Alternative:** *Aurora Serverless v2 (PostgreSQL)* if we needed relational queries or reporting. More cost and management, and it doesn't scale to zero as cleanly.

## Amazon EC2 running OpenWA (WhatsApp gateway)
- **What:** a t3.small (Amazon Linux 2023) running Docker: the **OpenWA** container (open-source, MIT) bound to localhost, plus **Caddy** for automatic HTTPS. Caddy exposes **only** the send-message endpoint and health. There's no SSH: admin happens over **SSM Run Command** (`scripts/openwa.sh`). Webhooks to us are signed with **HMAC-SHA256** and we verify each one.
- **Why OpenWA:** it worked in hours with no Meta business verification, and it's open source and free. That fit the meeting decision: *"the fact that it works on WhatsApp sets us apart"*.
- **Why EC2 rather than Fargate:** OpenWA keeps a logged-in WhatsApp session on disk and runs headless Chromium. That needs a persistent volume and roughly 1–2 GB of RAM, which is simplest on one small VM. Fargate would need EFS for the session.
- **Cost:** about $17/month for the instance plus about $3.6/month for the Elastic IP. **Stop it after the hackathon.**
- **Risks (be upfront):** OpenWA uses an **unofficial** WhatsApp client, so Meta can restrict the number (hence the spare number). It's a single instance, so it's a single point of failure. **Production path:** **AWS End User Messaging Social**, Meta's official WhatsApp Business API on AWS. It's the same webhook-in / send-out shape, so only `src/whatsapp/openwa.py` changes. Twilio is the other official option.

## AWS Systems Manager (Parameter Store + Session/Run Command)
- **What:** OpenWA API key (the instance publishes it on first boot), webhook secret, base URL and session id, stored as **SecureString**. Run Command administers the instance without SSH.
- **Why:** free tier and IAM-scoped. The Lambda only reads `/mzansiride/openwa/*`.
- **Alternative:** *Secrets Manager* gives automatic rotation for about $0.40 per secret per month. Worth it in production.

## Amazon CloudWatch
- **What:** JSON log lines (`event`, `trip`, `type`, `ms`, `in_tokens`...), a dashboard (Lambda errors, API 4xx/5xx, Bedrock latency and tokens, safety events, WhatsApp traffic), error alarms per function, an optional AWS Budget alert.
- **Why:** built in, and Logs Insights queries over structured logs give us metrics without extra code.

## IAM and delivery
- One role per Lambda: only its 4 tables, Bedrock invoke, its guardrail and log group. Only the WhatsApp role can read the OpenWA secrets.
- **Terraform** for everything (reproducible, reviewable). State is in S3 with a lockfile. **GitHub Actions with OIDC**, so no AWS keys are stored in GitHub: tests → `plan -out` → apply that exact plan → publish → smoke test.

---

## Tough questions: practice answers

1. **"Why not just use Uber's safety features?"** They exist, but they're inside one company's app and need data. We bring check-ins, explanations and trusted contacts together, and make them work on WhatsApp for people without data. The approach could also serve minibus taxi or e-hailing operators that have no safety tooling.
2. **"What exactly does the AI do that rules can't?"** The rules detect. The AI turns "stationary 240 s at -26.12, 28.05" into a calm explanation that fits the trip, and answers open questions ("he's asking for more cash"). Templates can't handle free text.
3. **"What if the AI gives wrong or harmful advice?"** It's grounded in approved guidance, at temperature 0.2. The Guardrail filters output and denies profiling. Emergency numbers always appear. The AI can't change alert state. If Bedrock fails, there's a deterministic fallback. Next step: an evaluation set of scenarios scored before each prompt change.
4. **"Isn't flagging stops unfair to drivers?"** That's why an event is a *check-in to the passenger*, never shown to anyone as an accusation. The driver isn't penalised, and the AI is told to mention normal reasons. Most alerts end in "I'm OK".
5. **"Why eu-west-1 when users are in South Africa?"** Bedrock isn't available in af-south-1. CloudFront serves the app from SA edges, and the API adds about 170 ms, which is fine for check-ins. In production we'd review POPIA cross-border rules or move non-AI parts to af-south-1.
6. **"How do you handle the passenger not answering?"** After 2 minutes of trip time the event escalates automatically and the trusted contact is notified. Today that check runs on the next telemetry reading. In production, a phone that goes silent should itself trigger escalation, using **EventBridge Scheduler** or a Step Functions wait.
7. **"How would this scale to a million trips?"** Lambda, API Gateway and DynamoDB on-demand scale automatically. Telemetry would move to **Kinesis or IoT Core** for high-frequency GPS. The dashboard would read from a GSI or OpenSearch instead of Scan. The OpenWA VM would be replaced by the official WhatsApp API.
8. **"What does it cost?"** Idle, almost nothing except the WhatsApp VM (~$20/month). Per alert, about $0.004 for Bedrock plus fractions of a cent for everything else.
9. **"Why OpenWA and not the official API?"** It was a speed decision for a 3-day hackathon. We know it's unofficial (ban risk), so we isolated it behind one small module. The production path is **AWS End User Messaging Social** (official WhatsApp Business API).
10. **"How do you stop someone spamming your webhook or API?"** HMAC signature verification on every webhook, webhook deduplication (DynamoDB conditional writes), API Gateway throttling, and the dashboard behind a team code (Cognito next). Only allow-listed numbers receive unsolicited messages.
11. **"Where's the personal data, and is it POPIA-compliant?"** The prototype uses simulated data only. Phone numbers are masked in the UI and logs, and items expire after 14 days. Production would need consent at sign-up, purpose limitation, an information officer, encryption (DynamoDB is encrypted at rest by default) and a cross-border assessment.
12. **"Is the driver lookup a criminal record check?"** No, and we say so in every response. It checks *our* registry (registered, suspended, under review). Production would need operator data and possibly licensing partners. A "not found" result explicitly isn't treated as dangerous.
13. **"Why DynamoDB and not a relational DB?"** Our queries are all by key (trip, events of a trip, chat link). On-demand pricing and TTL suit a spiky, small workload. If we needed reporting joins, we'd stream to S3/Athena or use Aurora.
14. **"Why two Lambdas?"** Different triggers and permissions: only the WhatsApp function can read gateway secrets. And WhatsApp must acknowledge within 10 s, so it processes asynchronously. They share the same `core` code, so behaviour is identical.
15. **"What happens if Bedrock is down or throttled?"** Boto3 retries, then the fallback text, labelled in the UI. Alerts, check-ins and escalation are unaffected.
16. **"Why not detect deviations with real maps?"** That's out of scope for the prototype (proposal §8.2). We use real OSM road geometry and point-to-polyline distance. With Amazon Location Service we'd recompute routes when the driver legitimately re-routes, which also reduces false alarms.
17. **"How did you test it?"** 42 unit tests (rules: no false alarm on a normal trip, short stops ignored, waiting at pickup ignored, latching; fares; driver lookup; AI model fallback; webhook signature and dedupe; the full API journey with DynamoDB mocked by moto) plus Playwright end-to-end tests of the real UI. CI runs them on every push.
18. **"What would you do with another week?"** Cognito accounts, live GPS with Amazon Location Service, a multilingual assistant, the official WhatsApp API, an AI evaluation suite, and a pilot with a student transport operator.
19. **"Who did what?"** Answer honestly and together. Both of you should be able to walk the diagram and the demo (that's why this doc exists).
20. **"Could you have used Amazon Lex or Amazon Connect?"** Lex suits structured intents (we have a few commands). Free-text safety questions suit an LLM better. Connect would add voice/USSD-style access for feature phones, which is a good future channel.
21. **"Why two AI models?"** Claude Haiku 5.5 is the main model: fast, cheap and good at calm, careful wording. If Bedrock refuses it (for example while Anthropic model access is still being approved for the account), the same request goes to Amazon Nova Lite, an Amazon-owned model that needs no extra approval. Same prompt, same Guardrail. If Bedrock is down entirely, the app shows the rules-based message instead. The response records which model answered, and the logs show it too.
