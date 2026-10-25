# Monday progress presentation: run-sheet

Requirements (Hackathon 2026 Project Requirements §3) say the presentation must cover: **problem → solution → architecture →
frontend → AI integration → AWS implementation → working prototype → outstanding work**. Both members must be able to
explain everything, so **each of you should rehearse the other's sections too** (see [aws-services-qa.md](aws-services-qa.md)).

Split as agreed in the meeting (swap if you prefer): **A** = problem + solution, then AI + AWS, then the close.
**B** = architecture + frontend, then the live demo + outstanding work.

| # | Who | Section | Time | Show |
|---|---|---|---|---|
| 1 | A | Problem | 1:00 | Title slide |
| 2 | A | Solution + target users + key features | 1:15 | Home page |
| 3 | B | Architecture | 1:30 | `docs/architecture.png` |
| 4 | B | Frontend | 0:45 | Quick tour of the screens |
| 5 | A | AI integration (what, why, limits) | 1:15 | Check-in modal + assistant |
| 6 | A | AWS implementation (services + why) | 1:00 | Architecture + CloudWatch dashboard |
| 7 | B | **Live demo**: passenger journey → WhatsApp check-in → fleet dashboard | 3:30 | Live site + phone |
| 8 | B | Completed / simulated / outstanding | 0:45 | About page status list |
| 9 | A | Close + business model + Q&A | 1:00 + Q&A | Fleet dashboard |

Total is about 12 minutes. If you're told 10 minutes, cut section 4 into the demo and shorten section 6.

---

## 1. Problem (A, 1:00)
- "Transport is how South Africans get to work, school and clinics. But for many passengers, especially women, students and anyone travelling alone at night, getting into a car with a stranger is stressful."
- "Concerns about **GBV, kidnapping and unexpected route changes** are real. And if something feels wrong, the passenger is often alone with that decision: *is this stop normal? should I worry? does anyone know where I am?*"
- "Second problem: **cost**. Daily commuters and students spend a big share of their income on transport."
- "Third, the twist that shaped our design: **many people have WhatsApp bundles but no general mobile data**, so a safety app that needs data fails exactly the people who need it most."
- "And most safety features today are a **panic button**. That's *reactive*: it asks the passenger to act in the middle of a crisis, which is exactly when it's hardest to do anything."

## 2. Solution (A, 1:15)
- "**MzansiRide SafeAI** is a **safety telemetry and intelligence layer** for e-hailing operators. We didn't build a panic button. We built a system that watches the *data* of every trip, notices when something looks wrong, and acts on the passenger's behalf: **proactive, not reactive**."
- "We don't sell to passengers, we sell to operators like Bolt or Uber in South Africa: real-time risk telemetry, automated WhatsApp check-ins, and an AI-assisted fleet dashboard, so their safety team handles incidents faster and can show regulators an audit trail."
- Key features (point at the home page, then the Fleet page):
  1. **Safe Journey Mode**: rules watch for a **prolonged stop** or a **route deviation**.
  2. A **check-in on WhatsApp**, sent automatically ("Hi Sarah, we noticed your trip to Sandton has left the planned route. Are you safe? Reply 1 for YES, 2 for HELP"). No answer within 2 minutes → automatic escalation.
  3. An **AI safety assistant** (Amazon Bedrock) that explains *why* we're asking and what your options are.
  4. **Trusted-contact alerts** with the driver, vehicle and last location.
  5. **Driver check**: look up a plate or name in our registry before getting in.
  6. **Shared-ride fare comparison**: share with 2 people and save about 40%.
  7. **All of it on WhatsApp**, so no app or data bundle is needed.
  8. **Fleet dashboard** for the operator: every live trip green, amber or red, with an **AI triage** sentence telling the fleet manager what to do next.
- Users: the **operator's safety team** (the customer), and their passengers: women and vulnerable passengers, students, daily commuters and budget-conscious riders.
- Say it plainly: "**We never assume the driver did something wrong.** Stops have normal reasons. An alert is a check-in, not an accusation."

## 3. Architecture (B, 1:30)
Walk the diagram left to right and follow the numbers:
1. "The passenger opens the React app from **CloudFront**, which serves it from Johannesburg and Cape Town edge locations. The files sit in a private **S3** bucket."
2. "API calls go through the same CloudFront address to **API Gateway**, which calls our **Lambda** function, so there are no servers to manage."
3. "Every few seconds the app sends the car's position. The **rules engine** in Lambda decides whether there's a stop or a deviation, and stores the event in **DynamoDB**."
4. "Only then do we call **Amazon Bedrock** to explain the event. The rules decide, and the AI explains."
5. "On WhatsApp, a message reaches **OpenWA**, an open-source WhatsApp gateway running on a small **EC2** server. It calls our webhook, and the second Lambda answers using the *same* core code."
6. "Replies, check-in prompts and trusted-contact alerts go back through OpenWA."
- "Secrets are in **SSM Parameter Store**, and everything is logged in **CloudWatch**. The whole stack is **Terraform**, and every push to GitHub deploys automatically."
- Dashed boxes: "Orange dashed is simulated: we replay a real road route instead of live GPS. Grey dashed is planned: Cognito and Amazon Location Service."

## 4. Frontend (B, 0:45)
Quick tour (or fold into the demo): **Ride** (booking + fare comparison) → **Trip** (map, driver, Safe Journey, trusted contact, WhatsApp link, safety log) → **Assistant** → **WhatsApp** (QR + simulator) → **Fleet** (operator dashboard) → **About** (status). "It's responsive: here it is on a phone." Show it on your phone, or resize the browser window.

## 5. AI integration (A, 1:15)
- **What it does:** two audiences.
  - *Passenger:* explains each alert in calm, plain language, lists their options, and answers safety questions in the app or on WhatsApp.
  - *Operator:* when an alert escalates, writes a **one-sentence triage action** for the fleet manager, for example "Trip MZ4K2P stopped off-route; passenger unresponsive on WhatsApp. Call the driver now."
- **Why AI:** a stressed passenger needs a clear, contextual explanation (trip, driver, how long the stop has lasted) in seconds, not a policy document. The AI also handles free-text questions like "the driver is asking for extra cash".
- **Why AI on the dashboard:** the rules say *which* trip needs attention; the AI turns five fields into the next action, which matters when one person watches a whole fleet.
- **Which service:** Amazon Bedrock with **Claude Haiku 5.5** (fast and cheap) via the Converse API, plus **Bedrock Guardrails**. If Claude can't be used, **Amazon Nova Lite** answers instead; if Bedrock is down entirely, a rules-based message.
- **How it's kept responsible:**
  - It's grounded in an **approved guidance file**: SA emergency numbers, what alerts mean, check-in options. It's told never to invent numbers.
  - **Detection is rule-based.** The AI can't create or cancel an alert.
  - It never blames the driver or predicts crime, and the Guardrail **denies profiling** people by race, nationality and similar traits.
  - It always points to **10111 / 112**. It can't call anyone and doesn't know whether you're safe.
  - **If Bedrock is down**, we show a rules-based message, labelled as such, and the check-in still works.
- **Limits:** it can be wrong, it only knows what's in the guidance, and it only covers English, with light local phrases.

## 6. AWS implementation (A, 1:00)
"We picked a small number of managed, pay-per-use services so it costs almost nothing when idle." Then name each service with **why** in one line (see the table in the README). Close with: "Least-privilege IAM per function, no credentials in the browser, GitHub OIDC for deploys, and a CloudWatch dashboard and alarms." Optionally show the CloudWatch dashboard for 10 seconds.

## 7. Live demo (B, 3:30)

### Before you present (15 minutes before)
1. Open the **live URL** (`make url`). Open **Fleet** and enter the team code (`make code`). The browser remembers it. Press **Run demo fleet** once and stop it, to warm up Lambda and Bedrock.
2. **Warm up**: book a quick trip and trigger one stop, so Lambda and Bedrock are warm.
3. Phone: WhatsApp chat with the bot number open. Send `hi` once to check it replies.
4. Zoom the browser to **125%**. Turn notifications off.
5. Backup ready: `make local` on the laptop (works offline except the map tiles), plus `docs/screenshots/`.

### Script
Before the demo, on the **Ride** page put the **spare-phone / teammate's number** (allow-listed) in *Your WhatsApp* so the real messages arrive on a phone you can show. If WhatsApp isn't set up, any other number sends them to the **WhatsApp simulator** page instead: keep it open in a second tab.

| Time | Do | Say |
|---|---|---|
| 0:00 | **Ride**: *Rosebank Gautrain* → *Sandton City*. Point at the fares. | "Meet Thandi, going from Rosebank to Sandton. Individual R67.50, or share with two others and pay R40.50, 40% less." |
| 0:15 | Name *Thandi*, her WhatsApp number, trusted contact *Mom*, Safe Journey ✔, **Request**. Show the phone. | "She gives us her WhatsApp number, nothing else to install. She's already got a WhatsApp message with her driver and plate." |
| 0:35 | **Check plate in registry**. | "She checks the plate against the registry: registered, safety score 94." |
| 0:45 | **Start trip**, **30× speed**. | "This is a simulated trip on real Joburg roads. The car sends its position and speed every few seconds, and our rules engine in Lambda checks every reading." |
| 1:00 | **Simulate off-route**, then **Simulate prolonged stop**. | "The car leaves the route… and stops." |
| 1:10 | Point at the phone: the check-in arrives. **Don't answer it.** | "Without Thandi pressing anything, she gets: *Hi Thandi, we noticed your trip to Sandton has left the planned route. Are you safe? Reply 1 for YES, 2 for HELP.* The explanation comes from Amazon Bedrock." |
| 1:30 | Wait ~4 s (2 min of trip time). The safety log shows *escalated*. | "She doesn't answer. Maybe she can't. So the system acts for her: her mom is alerted with the driver, plate and location." |
| 1:50 | **Fleet** page (team code already saved). | "This is the product the operator buys. Every live trip. Thandi's is flashing red…" |
| 2:00 | Read the **AI triage** sentence aloud. Click **Called driver**. | "…and Bedrock has written the next action for the fleet manager. The operator takes ownership with one click, and it's logged." |
| 2:20 | **Run demo fleet**. Let it run 20 s. | "Here's what it looks like with a fleet. Most trips are green. Thabo's car leaves the route, amber, he replies *I'm OK*, back to green. Sarah's car stops off-route and she doesn't answer: red, with triage." |
| 2:50 | **Phone, WhatsApp**: `CHECK BX 33 KK GP`, then "The driver locked the doors and wants more money". | "And the passenger side still works without data: a plate check flags a suspended driver, and the same assistant answers in plain language." |
| 3:20 | **Stop demo fleet**. | "Proactive, not reactive. That's the difference from a panic button." |

### If something goes wrong
- The AI is slow: keep talking. The modal shows the alert immediately, and the explanation follows a few seconds later.
- The AI shows "standard guidance shown": "That's our fallback. The safety flow never depends on the AI being up."
- WhatsApp is down or the account is restricted: use the **WhatsApp simulator** page, which runs the same backend code.
- The Wi-Fi drops: run `make local` on the laptop, or use the screenshots in `docs/screenshots/`.

## 8. Completed / simulated / outstanding (B, 0:45)
Show the **About** page list. Say it plainly:
- **Completed:** booking, journey + Safe Journey Mode, both rules, proactive WhatsApp check-ins + escalation, Bedrock assistant + Guardrail, AI triage + fleet dashboard with operator acknowledge, fare comparison, WhatsApp channel, Terraform + CI/CD + monitoring.
- **Simulated:** trip positions and speed (no live GPS), the demo fleet, drivers, vehicles and safety scores (demo registry), notifications and operator actions such as "Escalated to SAPS" (real WhatsApp only for our allow-listed numbers).
- **Outstanding / next:** Cognito accounts, live GPS with Amazon Location Service, multilingual assistant (isiZulu, Sesotho, Afrikaans), official WhatsApp Business API (AWS End User Messaging Social) to replace OpenWA, and operator partnerships for verified drivers and emergency response.

## 9. Close (A, 1:00)
"A panic button waits for the passenger to act. MzansiRide SafeAI doesn't wait. It watches the trip data, checks in on WhatsApp, even with no data bundle, acts for the passenger when they can't, and gives the operator's safety team a live fleet view with AI triage. We sell it to operators, so every passenger on their platform is protected. Thank you."

---

## Plain words for technical terms
| Instead of… | Say… |
|---|---|
| Lambda | "small programs that run only when needed: we pay per request, nothing when idle" |
| API Gateway | "the secure front door for our backend" |
| DynamoDB | "our database of trips and alerts" |
| Bedrock | "Amazon's service for running AI models like Claude, without us managing any AI servers" |
| Guardrails | "a safety filter on what goes into and comes out of the AI" |
| CloudFront | "a delivery network, so the app loads fast from Johannesburg" |
| OpenWA | "an open-source bridge between WhatsApp and our backend" |
| Webhook | "WhatsApp messages are pushed to our backend the moment they arrive" |

## Final checklist (from the requirements)
- [ ] Two members, both presenting
- [ ] ≥ 80% of the planned work done (all 10 proposal features plus WhatsApp)
- [ ] Architecture diagram ready and explainable
- [ ] Frontend complete and demo-ready (desktop + phone)
- [ ] Main user journey demonstrated
- [ ] AI demonstrated, with its limits explained
- [ ] AWS services and their purpose identified
- [ ] Features tested (48 unit tests + Playwright e2e)
- [ ] Completed / simulated / outstanding clearly identified (About page, README)
- [ ] Remaining work documented (section 8)
- [ ] Backup demo ready (`make local`, screenshots)
