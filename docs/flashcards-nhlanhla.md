# Flash cards: Nhlanhla

**Your part:** architecture and security, the frontend, why each AWS service, **the live demo**, outstanding work and impact.
Slides 13–19, 22–27 (about 11 minutes). Magala does the problem, the solution, the AI and the close.

Each slide card has the opening line (say it word for word), the key points (say them in your own words) and the
handover. Then come the questions judges are most likely to ask you. Full script:
[presentation-script.md](presentation-script.md).

---

## Know by heart (both of us)

- **One line:** a safety telemetry and intelligence layer for e-hailing operators. **Proactive, not reactive.**
- **Three messages:** proactive, not reactive · rules detect, AI explains, people decide · serverless, so it scales.
- **Real:** WhatsApp check-ins on a real number · WhatsApp alert to the trusted contact · Bedrock AI · Cognito sign-in ·
  alert emails.
- **Simulated:** the trip's movement (a real road, replayed) · drivers and vehicles · the Face ID result · the SMS.
- **Numbers:** R67.50 alone → R40.50 with 2 → **R27.00 with 3 (60% cheaper)** · stop **3 min** · off-route **250 m**
  (500 m if still heading to the destination) · wait window **1–5 min**, reminder halfway · Bedrock about **$0.003 a call**
  · WhatsApp server about **$20 a month** · **80** unit tests + **7** end-to-end tests.
- **In danger:** 10111 or 112. We never auto-call emergency services, and we never accuse the driver.

---

## Your slides

### Slide 13 · How we built it on AWS · 7:15 · 75 s
**Open:** “Thanks. Let me walk one alert through our architecture.”
- **Serverless:** scales by itself, and cost grows with use.
- **React app → CloudFront → API Gateway**, the front door. API Gateway is also the **WhatsApp webhook**.
- **Lambda = the brain:** rules, check-ins, escalation, and it calls **Bedrock** for triage, explanations and answers.
- **DynamoDB** stores trips, alerts and the safety log. **CloudWatch** lets us trace every alert.
- The red dashed line is the outbound side: check-ins and replies go back out on WhatsApp.
- **Close:** “WhatsApp is how we reach the passenger; API Gateway is how that conversation reaches our system.”

*Point to each box as you name it.*

### Slide 14 · The full architecture · 8:30 · 45 s
**Open:** “Here is the full picture, following one alert with the numbers.”
1. The passenger opens the app from **CloudFront** (Johannesburg and Cape Town edges).
2. API calls go through **API Gateway** to the **api Lambda**.
3. The **rules** flag a stop or a deviation, and the event is stored in **DynamoDB**.
4. **Bedrock** explains it, and writes the operator's triage line if it escalates.
5. and 6. **WhatsApp** comes in through our **OpenWA** gateway on EC2; check-ins, replies and the contact alert go back out
   the same way.
- **Around it:** Cognito sign-in for operators · SNS emails us when something is down · secrets in SSM · logs in
  CloudWatch.
- **Orange dashed** = simulated (the journey replay) · **grey dashed** = planned (Location Service, live GPS).

*Point at each number as you say it. Don't read the box labels.*

### Slide 15 · Built to be responsible · 9:15 · 30 s
**Open:** “Security and privacy are designed in.”
- **Simulated data only:** no real locations are collected.
- **An event is a prompt to check in,** never proof of wrongdoing.
- **The AI uses approved guidance only.** It isn't an emergency service: in danger, 10111 or 112.
- **Minimal data,** access controlled at the backend, no credentials in the frontend.
- **POPIA:** designed with it in mind; production needs a formal assessment.

### Slide 16 · Request a ride, see the saving · 9:45 · 30 s
**Open:** “This is the working frontend.”
- Predefined Johannesburg places, on **real road routes**.
- **R67.50 alone, R40.50 with two, R27.00 with three.**
- It's marked simulated, and the fares are illustrative.

### Slide 17 · Safe Journey Mode in action · 10:15 · 30 s
**Open:** “Once the trip starts, Safe Journey Mode is on.”
- It watches for **unusual stops and route changes**.
- The passenger can see her **trusted contact**, **share the trip**, and send **SOS in one tap**.
- **Honest labels:** the WhatsApp alerts are real, and the SMS is labelled simulated.

### Slide 18 · Every trip leaves a record · 10:45 · 30 s
**Open:** “When the trip ends, the summary shows the fare, the distance and the alerts.”
- Plus what sharing would have saved, about **R27**.
- The **safety log is stored in DynamoDB**: the audit trail.
- The driver card says **“demo driver, not verified”**: check the plate, the car and the driver.

### Slide 19 · What the operator sees · 11:15 · 40 s
**Open:** “This is what the operator sees.”
- **Green** = normal. **Red** = needs action, with the **AI's one-line next step**.
- Example: stopped off-route, passenger not answering on WhatsApp → call the driver now.
- **System health panel:** is WhatsApp working, which AI model is answering, what was sent today, any errors.
  “We see a problem before the passenger does.”
- *A real screenshot of the live Fleet page: the trips are a demo fleet, the triage lines are real Bedrock output.*

**Hand over:** “I'll hand back to Magala to explain the AI.”

### Slide 22 · Why each AWS service · 14:05 · 60 s
**Open:** “Now let me explain why we chose each AWS service.”
- **CloudFront:** fast and secure, with no web servers to run.
- **API Gateway:** a managed front door, including for WhatsApp.
- **Lambda:** pay only when it runs; the same code serves one trip or a national fleet.
- **Bedrock:** foundation models as a service, with no model servers.
- **DynamoDB:** fast and scalable; the operator's audit trail.
- **CloudWatch:** trace and prove what happened. **IAM:** each function gets only the access it needs.
- **Close:** “Serverless throughout: we pay for what we use, and nothing sits idle.”
- *If asked:* **Cognito** for operator sign-in (API Gateway checks the token before any code runs), **SNS** emails us
  when something is down, **EventBridge** runs the health check every 5 minutes.

### Slide 23 · LIVE DEMO · 15:05 · about 3 min 15 s
**Before you start:** signed in on Fleet in another tab · wait window **5 min** · simulator at **15×** · phone on loud.
**Open:** “Now let's see it running.”
1. Request a ride.
2. The driver and vehicle: a labelled **demo driver**.
3. Switch on **Safe Journey Mode**.
4. Trigger a **simulated stop**.
5. **Watch the phone:** the check-in arrives on WhatsApp. *Hold up the phone; reply 1, or deliberately don't.*
6. **Fleet page:** the alert appears, with the AI triage line.
7. The **shared-ride saving**.

**Close:** “The trip and events are simulated, the WhatsApp number is real, and the assistant runs on Amazon Bedrock.”
**If it fails:** switch without apologising. Use the WhatsApp simulator page, `make local`, or the screenshots.

### Slide 24 · Try it yourself · 18:20 · about 1 min, while they scan
**Before:** the Fleet page open in another tab, already signed in.
**Open:** “Now it's your turn. Scan a code.”
- **Left, the web app:** book a ride with your own WhatsApp number, start the trip, press **Simulate prolonged stop**, and
  the check-in comes to your phone.
- **Right, WhatsApp:** say hi, **CHECK CA 123-456**, or ask a safety question.
- *Give them a few seconds, then switch to the Fleet page:* “While you do that, here's the operator's view. Your trips
  are appearing on the fleet map right now, and the ones that stop turn amber, then red, with the AI's next step.”
- If asked: the trips and drivers are simulated; not for real emergencies (10111 or 112).

### Slide 25 · Working, simulated and still to come · 19:20 · 40 s
**Open:** “Here's an honest view of where we are.”
- **Working:** booking, fares and budget · Safe Journey, trusted contact, share and SOS · WhatsApp check-ins (1, 2 or your
  own words) · the no-reply workflow · the Fleet dashboard with AI triage · the Bedrock assistant · the safety log.
- **Simulated:** trips and events · driver profiles · the Face ID result · the SMS (the WhatsApp alerts are real).
- **Still to come:** live GPS · real driver verification · emergency services · payments · a POPIA assessment and a pilot.
- **Close:** “We do not claim to prevent crime, guarantee safety or verify drivers.”

### Slide 26 · Outstanding work · 20:00 · 40 s
**Open:** “We set ourselves six things to finish before Tuesday. All six are built and in today's demo.”
- The app works on a phone and installs to the home screen · the Ask AI button on every page · weekly and monthly fares
- The full no-reply workflow · the driver Face ID check (simulated) · **operator sign-in with Amazon Cognito**

### Slide 27 · Expected impact · 20:40 · 30 s
**Open:** “Three groups benefit.”
- **Passengers:** calm support and a one-tap check-in.
- **Operators:** real-time visibility, faster response, and a record of every alert.
- **Communities:** cheaper shared travel, R67.50 down to R27.00 each (illustrative).

**Hand over:** “I'll hand back to Magala to close.”

---

## Questions you'll likely get

**Q: Walk me through what happens when a car stops.**
A: The browser sends a position → API Gateway → Lambda → the rules see a 3-minute stop → the event is saved in DynamoDB →
a check-in goes out on WhatsApp and in the app → Bedrock explains it → no answer → the trusted contact is alerted and the
trip turns red on the Fleet page with an AI triage line.

**Q: Why eu-west-1 and not Cape Town?**
A: Bedrock isn't available in af-south-1. CloudFront still serves the app from Johannesburg and Cape Town. The API adds
about 170 ms, which is fine for check-ins. Production: review POPIA cross-border rules.

**Q: Why two Lambdas?**
A: Different triggers and permissions: only the WhatsApp one can read the gateway secrets. WhatsApp needs an answer
within 10 seconds, so that one processes in the background. Both share the same core code, so web and WhatsApp behave
the same.

**Q: Why DynamoDB and not a relational database?**
A: Every query is by key: a trip, a trip's events, a chat link. On-demand pricing, no capacity planning, and TTL deletes
data after 14 days for free. For reporting, we'd stream to S3 and Athena.

**Q: Why OpenWA and not the official WhatsApp API?**
A: Speed: a real two-way number today, without waiting for Meta's business verification. We know it's unofficial, so
it's isolated in one small module. Production: **AWS End User Messaging Social**.

**Q: How is it secured?**
A: Operators sign in with **Cognito**, and API Gateway rejects bad tokens before any code runs · no AWS keys in the
browser · secrets in SSM · the WhatsApp webhook is signed (HMAC) and de-duplicated · the gateway exposes only send and
health · rate limits per number · data expires after 14 days.

**Q: How would it scale to a million trips?**
A: Lambda, API Gateway and DynamoDB scale by themselves. For high-frequency GPS: Kinesis or IoT Core. The Fleet view moves
from a scan to an index. The official WhatsApp API replaces the server. **Today's limits:** Lambda concurrency is 10 and
the API is throttled at 100 requests a second; both are quotas we can raise.

**Q: What does it cost?**
A: Idle, close to nothing except the WhatsApp server (about $20 a month). About $0.003 per Bedrock call, which only
happens when an alert fires. Cents per trip.

**Q: How do you know when something breaks?**
A: A health check every 5 minutes (EventBridge) → CloudWatch metrics → alarms → **SNS emails the team**, when it breaks
and when it recovers. The Fleet page has a live health panel too.

**Q: How did you test it?**
A: 80 unit tests (rules, check-ins, escalation, WhatsApp, rate limits, sign-in), 7 browser end-to-end tests on desktop
and mobile, and live checks on AWS. Every push runs them, and it deploys only if they pass.

**Q: Why is the SMS simulated?**
A: It's built on Amazon SNS and tested, but our AWS account is on the free plan, which blocks SMS. It's a setting to
switch on once the account is upgraded. The WhatsApp alerts are real today.

**Q: Why not Amplify?**
A: Amplify Hosting would work. We already have S3 + CloudFront in Terraform: same CDN underneath, same-origin `/api`, and
one IaC for everything.

**Q: What would you do with another week?**
A: Live GPS with Amazon Location Service, the official WhatsApp API, passenger accounts, a multilingual assistant
(isiZulu, Sesotho, Afrikaans), an AI evaluation set, and a pilot with one operator.

**Q: Who did what?**
A: Answer honestly and together, with the split you actually agreed (decide it before you present, so you both say the
same thing). Then add: both of us can walk the diagram and the demo.
