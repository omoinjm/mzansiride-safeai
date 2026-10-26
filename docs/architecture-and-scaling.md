# Architecture, trade-offs and scaling

This is for the two presenters and anyone reviewing the build. It explains what each AWS service does in MzansiRide SafeAI, why we picked it, and what we gave up by choosing it. It also covers how the system would grow from a prototype into a product, and where each outstanding feature would fit. For quick Q&A answers, see [aws-services-qa.md](aws-services-qa.md).

## 1. What we built, in one paragraph

MzansiRide SafeAI is a safety layer for ride operators. A passenger books a simulated ride in a React web app and turns on Safe Journey Mode. While the trip runs, every position reading passes through a rules engine in AWS Lambda. If the car stops for too long, or leaves every plausible road, the passenger gets a check-in on WhatsApp and in the app. If they ask for help or don't answer, the system escalates. Their trusted contact gets a WhatsApp alert, and the operator's Fleet page turns the trip red with a one-line next step written by Amazon Bedrock. The same core code serves the web app and a real WhatsApp number. Diagrams: [docs/architecture.png](architecture.png), and the Mermaid version in the [README](../README.md#architecture).

## 2. The services and why we chose each

| Service | What it does here | Why this one | Cost shape | Main trade-off / alternative |
|---|---|---|---|---|
| **CloudFront + S3** | Serves the React app from a private bucket (Origin Access Control). Forwards `/api/*` to API Gateway, so the app and API share one origin. A CloudFront Function handles client-side routes. | HTTPS and edge locations in Johannesburg and Cape Town, with no web servers. Same-origin means no CORS and no API URL baked into the app. | Cents at demo traffic | Amplify Hosting is simpler point-and-click, but we wanted everything in Terraform |
| **API Gateway (HTTP API)** | One HTTPS entry point: `ANY /api/{proxy+}` goes to the `api` Lambda, and `POST /whatsapp/webhook` goes to the `whatsapp` Lambda. Throttled to 25 requests a second (burst 50). | Managed, cheap, and has built-in throttling. A Cognito JWT authoriser guards the operator routes, so unsigned requests never reach Lambda. | Per million requests | The REST API flavour has WAF and usage plans; we don't need them yet |
| **Lambda × 2** (Python 3.13, arm64, 512 MB) | `api`: trips, the rules engine, check-ins, the no-answer ladder, escalation, the Fleet view, health. `whatsapp`: verifies the webhook, removes duplicates, runs the conversation and sends replies. Both ship the same `src/` zip. | Pay per request, scales to zero, no servers. One shared core means the web app and WhatsApp behave identically. | Effectively free at demo scale | Fargate suits long-lived connections; we have none |
| **Amazon Bedrock** | Explains alerts to the passenger, reads free-text check-in replies, reads a number plate from a photo, answers safety questions, and writes the operator's triage line. Main model: Claude Haiku 5.5 (EU profile). Fallback: Amazon Nova Lite. Guardrails on top. | Managed models, no GPUs, IAM-controlled, and data isn't used for training. The fallback model keeps the AI working when the main one is refused. | About $0.003 per call, and only called when needed | SageMaker means always-on endpoints. A Knowledge Base is overkill for one short guidance file |
| **DynamoDB** (4 tables, on-demand, TTL) | `trips`, `events` (alerts, replies, notifications), `drivers` (demo registry), `whatsapp` (chat links, webhook dedupe, simulator outbox, ops config, health counters, send-limit counters). Records expire after 14 days. | Single-digit-millisecond key lookups, no capacity planning, and TTL handles data retention for free. Atomic counters power the rate limits and the health panel. | Pennies | Aurora gives SQL analytics; we'd add that through a stream later, not as the main store |
| **EC2 + OpenWA** (small instance, Elastic IP, Caddy) | Runs the open-source WhatsApp gateway on our real number. Caddy provides TLS and exposes only `send-text` and `health`. Admin goes through SSM; there's no SSH and no public dashboard. | A two-way WhatsApp channel today, without waiting for Meta business verification. | About $15–20/month, always on | Unofficial client (ban risk) and a single point of failure. Production: AWS End User Messaging Social |
| **SSM Parameter Store** | The gateway API key, webhook secret, base URL and session id. | Free, IAM-scoped, encrypted. | Free | Secrets Manager adds rotation; not needed yet |
| **CloudWatch** | JSON logs for both Lambdas, a dashboard, error alarms, and Lambda error metrics read by the health panel. | Built in, with nothing extra to run. | Small at 14-day retention | X-Ray tracing would help once there are more services |
| **Amazon Cognito** | Operator sign-in for the Fleet page: an invite-only user pool, group `operators`. API Gateway's JWT authoriser checks the ID token on the operator routes. | Managed accounts, password policy and token refresh, and the authoriser rejects bad tokens before any Lambda runs. Passengers still book without an account. | Free at this size (MAU free tier) | A shared team code (what we had): one secret for everyone, nothing per person |
| **Amazon SNS** | One SMS to the trusted contact on SOS or "I need help". A topic that emails the team when a CloudWatch alarm fires or recovers. | SMS reaches phones without WhatsApp or data. Email alerts need no extra tool. | SMS: a few US cents per message to SA; email free | New accounts are in the SMS sandbox (verified numbers only). End User Messaging SMS for sender registration at scale |
| **EventBridge (schedule)** | Runs the health check every 5 minutes: WhatsApp gateway, AI, SMS, published as `MzansiRide/Health` metrics. | A heartbeat: if the check stops running, the "not reporting" alarm fires too. | Free | CloudWatch Synthetics canaries do more but cost more |
| **IAM + GitHub OIDC** | One least-privilege role per Lambda. CI assumes a deploy role through OIDC, with no stored keys. | No long-lived credentials anywhere, and nothing secret in the browser. | Free | None |
| **Terraform + GitHub Actions** | All infrastructure as code. Every push to `main` runs the tests, plans, applies that exact plan, publishes the app and smoke-tests it. | Repeatable, reviewable and easy to tear down. | Free | CDK would also work; Terraform was already familiar |

**Rules detect, AI explains.** Whether something is wrong (a stop longer than three minutes, or 250 m off every known road) is decided by plain, unit-tested code in `core/rules.py`. The AI never decides that someone is in danger, and never closes an alert on an unclear answer. This keeps the safety path predictable, testable and auditable. The AI adds what rules are bad at: calm wording, understanding free text, and summarising for the operator.

## 3. How it works together

**One safety alert, end to end**

1. The browser simulator sends a position reading roughly every second (`POST /api/trips/{id}/telemetry`), through CloudFront and API Gateway to the `api` Lambda.
2. The rules engine updates the trip's state. Driving on the planned road, or on a stored alternative such as the one Waze might choose, is normal. A stop of three minutes or more, or two readings 250 m off every road, raises an event. A car still heading towards the destination gets more leeway: it must be 500 m off for four readings.
3. The event is stored in DynamoDB as `awaiting_checkin`. The passenger sees "Are you OK?" in the app and gets "Your trip has stopped. Are you safe? Reply 1 = Safe 2 = Help" on WhatsApp.
4. **The no-answer ladder.** The operator sets the wait window. At half the window, the passenger gets a reminder. At the full window, the alert escalates.
5. On escalation, or when they reply 2, write "he locked the doors", or press SOS:
   - The trusted contact gets a WhatsApp alert with the car, plate and a map link.
   - Bedrock writes a one-line triage action.
   - The trip turns red on the Fleet page.
6. The operator acknowledges it ("Called driver"). Every step is stored on the event, which gives an audit trail.

**One WhatsApp message in**

1. OpenWA posts to `/whatsapp/webhook`. The Lambda checks the HMAC signature, maps WhatsApp's privacy ID back to a phone number if it can, and removes duplicates with a conditional write.
2. It answers OpenWA straight away, then invokes itself asynchronously to do the actual work. This beats the gateway's webhook timeout even when Bedrock takes a few seconds.
3. `core/commands.py` decides what the message is:
   - a check-in reply (1, 2, or free text);
   - a command: `CHECK`, `TRIP`, `STATUS` or `SOS`;
   - otherwise, a question for the assistant.
4. The reply goes back out through the gateway.

**Why the pieces fit**

- **One origin.** The app calls `/api` on its own domain, so there's no CORS and no configuration in the app.
- **A core that doesn't care about the channel.** The web app, the real WhatsApp number and the in-browser WhatsApp simulator all run the same functions, so a fix in one place fixes all three.
- **A fallback at every layer:**
  - Claude is refused: Nova Lite answers.
  - Bedrock is down: rules-based text appears, labelled as such.
  - The gateway isn't connected: messages go to the simulator.
  - The internet is down: `make local` runs everything on a laptop.
- **Safe sending.** Unsolicited messages (contact alerts, the first message to a passenger) are capped at 20 per number per hour and 500 per day. Only plausible mobile numbers get real messages, and the demo fleet and tests use `000` numbers.
- **We can see it working.** The Fleet page's system health panel shows the gateway status, which model answered, today's messages, and Lambda errors in the last hour.

## 4. Key trade-offs we made

| Decision | Why | Cost / risk | What we'd change in production |
|---|---|---|---|
| eu-west-1 instead of af-south-1 | Bedrock isn't in Cape Town | About 170 ms extra latency, and personal data leaves South Africa (a POPIA cross-border question) | Move when Bedrock arrives in af-south-1, or keep data in Cape Town and send only anonymised prompts to the EU |
| OpenWA instead of the official WhatsApp API | Working today; no Meta business verification needed | Unofficial client: the number can be restricted. Single instance | AWS End User Messaging Social (official API, per-conversation pricing). Only `whatsapp/openwa.py` changes |
| One EC2 gateway | Simple and cheap | Single point of failure. It can hang (fixed with `make wa-restart`) | Gone once we move to the official API. Until then: an auto-recovery alarm and a health-check restart |
| Guidance in the prompt instead of a Knowledge Base | One short approved guidance file; cheaper and easier to test | Doesn't scale past a few pages | Bedrock Knowledge Base, once guidance grows (languages, operator policies) |
| Fleet view built from DynamoDB scans | Fast to build; fine for hundreds of trips | Gets slower and costlier as data grows | Index on active trips, or a read model fed by DynamoDB Streams |
| Browser simulator instead of live GPS | Reliable demos; GPS was out of scope | Not real movement | A driver app or SDK sends GPS; the rules engine stays the same |
| Operators only in Cognito; passengers have no account | Booking stays one screen | No passenger trip history across devices | A Cognito `passengers` group, or phone sign-in |
| No reserved Lambda concurrency | This account's concurrency limit is only 10 | A traffic spike can starve the WhatsApp Lambda | Request a higher limit, then reserve concurrency for `whatsapp` |
| Allow-list removed, with send limits | Anyone can try the demo with their own contact | Abuse and ban risk, capped by the limits | Consent: the contact confirms by WhatsApp before they get alerts |

## 5. How it scales, and where to start

**What already scales on its own:**
- CloudFront, API Gateway and DynamoDB on-demand handle bursts with no changes.
- Lambda scales per request, up to the account's concurrency limit.
- Bedrock scales up to its per-account quotas.

The real bottlenecks, in the order we'd hit them:

1. **Lambda concurrency (10 in this account).** This hits first. Every telemetry reading is a Lambda call. *First step:* request a quota increase (to the 1,000 default or more), then reserve a slice for `whatsapp` so alerts never queue behind telemetry.
2. **The single WhatsApp gateway.** One small EC2 instance driving WhatsApp Web won't handle thousands of messages an hour, and the number can be restricted. *First step:* move to the official WhatsApp Business API through AWS End User Messaging Social. The webhook-in, send-out shape stays the same.
3. **The Fleet view uses scans.** It reads up to 1,000 events per refresh. *First step:* add an index on active trips and query only in-progress trips. Later, stream events (DynamoDB Streams) into a small read model per operator.
4. **The telemetry rate.** One request per reading per car is wasteful at fleet scale. *First step:* send readings in batches (every 10–15 s) from the driver app. *At scale:* AWS IoT Core or Kinesis Data Streams for GPS, with the same `rules.evaluate` running as a stream consumer. The rules are pure functions, so they move unchanged.
5. **Bedrock throttling and cost.** AI runs only on alerts, replies and questions, never on every reading, and explanations are cached per event. *First step:* raise the quotas and cache common answers. *At scale:* provisioned throughput, or a smaller model for classifying replies.
6. **Multiple operators.** Today it's one fleet. *First step:* add an operator ID to every key, and use Cognito groups per operator, so each operator sees only its own trips.
7. **Region.** Move closer to South Africa when Bedrock arrives in af-south-1, or use cross-region inference with data kept in Cape Town.

**What breaks first (rough estimates):**

| Concurrent trips | Readings / s (1 per s each) | What breaks first | Fix |
|---|---|---|---|
| 10 | ~10 | Nothing; this is today's demo | – |
| 1,000 | ~1,000 | Lambda concurrency (10) and API throttle (25/s); Fleet scan latency | Raise the quotas; batch readings; index on active trips |
| 100,000 | ~100,000 | Lambda-per-reading architecture, the WhatsApp gateway, single-region | IoT Core or Kinesis, rules as stream consumers; official WhatsApp API; per-operator partitions; multi-region |

## 6. Outstanding features and how they fit

| Feature | Plugs into | What changes | Rough effort |
|---|---|---|---|
| **Passenger accounts** | Cognito (already used for operators), booking | A `passengers` group and phone sign-in, so trips and trusted contacts follow the passenger | 1–2 days |
| **Live GPS + Amazon Location Service** | Telemetry → `core/rules.py` | A driver app sends real positions. Location Service calculates routes with alternatives (replacing `routes.json`) and snaps positions to roads. The rules stay the same | 1–2 weeks |
| **Real driver verification** | `trips._driver_check`, the driver card | Face ID or fingerprint on the driver's phone (we receive only pass or fail), plus a one-time ID and licence check at sign-up. Needs a POPIA assessment for biometrics | 2–4 weeks plus a partner |
| **Emergency-service integration** | The escalation in `trips._escalate` | A partner API (private security or response centre) called at escalation, with a person in the loop. Never automatic | Depends on the partner |
| **Payments and ride matching** | Booking (`create_trip`) | A payment provider and a matching service. The safety layer is unchanged | Weeks; not our focus |
| **Official WhatsApp API** | `whatsapp/openwa.py`, the webhook | Swap the gateway client for End User Messaging Social. Message templates for messages to people who haven't messaged us | 2–3 days plus Meta verification |
| **WhatsApp plate photos** | `whatsapp/handler.py` → `drivers.photo_check` | Download the image from WhatsApp; `read_plate` already works in the app | 1 day, once on the official API |
| **isiZulu, Sesotho, Afrikaans** | `core/assistant.py`, `notify.py` texts | Detect or choose a language per chat, translate the fixed messages, and give the assistant guidance per language | 3–5 days plus review by native speakers |
| **Operator analytics** | Events (via DynamoDB Streams) | Export to S3 and query with Athena or QuickSight: hotspots, response times, false-alarm rates | 1 week |
| **POPIA assessment + operator pilot** | The whole system | Consent flows (the contact opts in), data-retention review, data processing agreement; a pilot with one operator or campus shuttle to measure false alarms | Ongoing |

## 7. Costs at a glance (estimates)

| | Prototype idle (per month) | Per 1,000 trips with Safe Journey |
|---|---|---|
| EC2 gateway (always on) | ~$15–20 | – |
| Lambda + API Gateway | ~$0 | ~$0.50 (≈ 600 readings per trip) |
| DynamoDB | < $1 | ~$1 |
| Bedrock | $0 | ~$1–3 (only trips with alerts or questions) |
| CloudFront, S3, CloudWatch, SSM | < $2 | < $0.50 |
| **Total** | **≈ $20** | **≈ $3–5**, i.e. well under R0.10 per trip |

The gateway is the only fixed cost; everything else grows with use. With the official WhatsApp API, the fixed cost disappears and WhatsApp is charged per conversation instead.
