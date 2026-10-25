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
| 7 | B | **Live demo**: main user journey + WhatsApp | 3:30 | Live site + phone |
| 8 | B | Completed / simulated / outstanding | 0:45 | About page status list |
| 9 | A | Close + Q&A | 1:00 + Q&A | Dashboard |

Total is about 12 minutes. If you're told 10 minutes, cut section 4 into the demo and shorten section 6.

---

## 1. Problem (A, 1:00)
- "Transport is how South Africans get to work, school and clinics. But for many passengers, especially women, students and anyone travelling alone at night, getting into a car with a stranger is stressful."
- "Concerns about **GBV, kidnapping and unexpected route changes** are real. And if something feels wrong, the passenger is often alone with that decision: *is this stop normal? should I worry? does anyone know where I am?*"
- "Second problem: **cost**. Daily commuters and students spend a big share of their income on transport."
- "Third, the twist that shaped our design: **many people have WhatsApp bundles but no general mobile data**, so a safety app that needs data fails exactly the people who need it most."

## 2. Solution (A, 1:15)
- "**MzansiRide SafeAI** is a safety-first ride-sharing prototype. We didn't try to rebuild Uber. We focused on the journey itself."
- Key features (point at the home page):
  1. **Safe Journey Mode**: rules watch for a **prolonged stop** or a **route deviation**.
  2. A **check-in**: "Are you OK?", with *I'm OK* or *I need help*. No answer within 2 minutes → automatic escalation.
  3. An **AI safety assistant** (Amazon Bedrock) that explains *why* we're asking and what your options are.
  4. **Trusted-contact alerts** with the driver, vehicle and last location.
  5. **Driver check**: look up a plate or name in our registry before getting in.
  6. **Shared-ride fare comparison**: share with 2 people and save about 40%.
  7. **All of it on WhatsApp**, so no app or data bundle is needed.
- Users: women and vulnerable passengers, students, daily commuters and budget-conscious riders. Operators get the dashboard.
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
Quick tour (or fold into the demo): **Ride** (booking + fare comparison) → **Trip** (map, driver, Safe Journey, trusted contact, WhatsApp link, safety log) → **Assistant** → **WhatsApp** (QR + simulator) → **Dashboard** → **About** (status). "It's responsive: here it is on a phone." Show it on your phone, or resize the browser window.

## 5. AI integration (A, 1:15)
- **What it does:** explains each alert in calm, plain language, lists the passenger's options, and answers safety questions in the app or on WhatsApp.
- **Why AI:** a stressed passenger needs a clear, contextual explanation (trip, driver, how long the stop has lasted) in seconds, not a policy document. The AI also handles free-text questions like "the driver is asking for extra cash".
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
1. Open the **live URL** (`make url`). Open **Dashboard** and enter the team code (`make code`). The browser remembers it.
2. **Warm up**: book a quick trip and trigger one stop, so Lambda and Bedrock are warm.
3. Phone: WhatsApp chat with the bot number open. Send `hi` once to check it replies.
4. Zoom the browser to **125%**. Turn notifications off.
5. Backup ready: `make local` on the laptop (works offline except the map tiles), plus `docs/screenshots/`.

### Script
| Time | Do | Say |
|---|---|---|
| 0:00 | **Ride**: pickup *Rosebank Gautrain*, destination *Sandton City*. Point at the fares. | "Meet Thandi. She's going from Rosebank to Sandton. Individual R67.50, or share with two others and pay R40.50, 40% less." |
| 0:20 | Name *Thandi*, trusted contact *Mom* + your teammate's number, Safe Journey ✔, **Request**. | "She adds her mom as a trusted contact and keeps Safe Journey Mode on." |
| 0:35 | Driver card → **Check plate in registry**. | "Before getting in she checks the plate against our registry: registered, no reports." |
| 0:50 | **Start trip**, set **30× speed**. | "This is a simulated trip on real Joburg roads. Each second is 30 seconds of trip time." |
| 1:05 | **Simulate prolonged stop**. Wait ~6 s. | "The car stops. Our rules engine in Lambda is watching: three minutes without moving, away from pickup…" |
| 1:15 | The modal appears. Read the AI text briefly. | "…and Thandi is asked if she's OK. This explanation comes from Amazon Bedrock. It says there may be a normal reason, and gives her options. No accusations." |
| 1:40 | **I'm OK**. | "She's fine. The alert is closed and logged." |
| 1:50 | **Simulate route deviation** → the modal → **I need help**. | "Now the car leaves the planned route. This time she taps *I need help*…" |
| 2:10 | Point at the safety log notification (and the teammate's phone buzzing, if allow-listed). | "…and her mom is alerted with the driver, plate and location." |
| 2:30 | **Phone, WhatsApp**: `CHECK BX 33 KK GP`. | "Now the thing that sets us apart. No data bundle, just WhatsApp. She checks a plate…" → caution reply. "This driver is suspended in our registry: take another ride." |
| 2:55 | WhatsApp: "The driver locked the doors and wants more money" | "And she can just describe her situation. The same Bedrock assistant answers on WhatsApp." |
| 3:15 | **Dashboard**. | "Operators see every trip, alert, response and notification, and how fast the prompt appeared." |

### If something goes wrong
- The AI is slow: keep talking. The modal shows the alert immediately, and the explanation follows a few seconds later.
- The AI shows "standard guidance shown": "That's our fallback. The safety flow never depends on the AI being up."
- WhatsApp is down or the account is restricted: use the **WhatsApp simulator** page, which runs the same backend code.
- The Wi-Fi drops: run `make local` on the laptop, or use the screenshots in `docs/screenshots/`.

## 8. Completed / simulated / outstanding (B, 0:45)
Show the **About** page list. Say it plainly:
- **Completed:** booking, journey + Safe Journey Mode, both rules, check-ins + escalation, Bedrock assistant + Guardrail, dashboard, fare comparison, WhatsApp channel, Terraform + CI/CD + monitoring.
- **Simulated:** trip positions (no live GPS), drivers and vehicles (demo registry), notifications (real only for our allow-listed numbers).
- **Outstanding / next:** Cognito accounts, live GPS with Amazon Location Service, multilingual assistant (isiZulu, Sesotho, Afrikaans), official WhatsApp Business API (AWS End User Messaging Social) to replace OpenWA, and operator partnerships for verified drivers and emergency response.

## 9. Close (A, 1:00)
"MzansiRide SafeAI makes sure that when something unusual happens on a trip, the passenger is never alone with it. Someone checks in, AI explains the options in plain language, and a trusted person can be alerted, even with no data, on WhatsApp. Thank you."

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
- [ ] Features tested (42 unit tests + Playwright e2e)
- [ ] Completed / simulated / outstanding clearly identified (About page, README)
- [ ] Remaining work documented (section 8)
- [ ] Backup demo ready (`make local`, screenshots)
