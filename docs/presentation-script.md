# MzansiRide SafeAI: presentation script

Read from this while presenting. It follows the deck slide by slide
([`presentation/MzansiRide_SafeAI_Deck.pptx`](presentation/MzansiRide_SafeAI_Deck.pptx); the words are the speaker notes).
**Bold quotes are what you say.** *Italic lines are cues, not to be read aloud.* Times are when the slide starts.

**Presenters:** Magala (problem, solution, AI, close) · Nhlanhla (architecture, frontend, AWS, live demo, outstanding work).
**Length:** about 22 minutes, then questions. Hard questions and answers: [`aws-services-qa.md`](aws-services-qa.md).

## Before you start (10 minutes before)

- [ ] Open the live app and **sign in on the Fleet page** with your Cognito email and password. Keep that tab open.
- [ ] On the Fleet page, set the **check-in wait window to 5 minutes** and make sure the **WhatsApp switch is on**.
- [ ] Press **Run demo fleet** once and stop it, to warm up Lambda and Bedrock.
- [ ] Send the bot a WhatsApp message from the demo phone and check it answers (if not: `make wa-restart`).
- [ ] Have the backup ready: `make local` (http://localhost:8077, Fleet code `local`), and the screenshots in `docs/screenshots/`.
- [ ] Phone on loud, notifications from other apps off, screen brightness up.

## Real vs simulated (say it the same way every time)

| Real | Simulated (labelled in the app) |
|---|---|
| WhatsApp check-ins and replies on a real number | The trip's movement (a real road route, replayed) |
| WhatsApp alert to the trusted contact | Drivers, vehicles and the safety score |
| Amazon Bedrock: explanations, reply reading, triage, plate reading, assistant | The driver Face ID result |
| Operator sign-in (Cognito), alert emails (SNS) | The SMS to the trusted contact (our AWS account is on the free plan) |

## Running order

| Slide | Who | Starts | Section |
|---|---|---|---|
| 1 | Magala | 0:00 | Cover: MzansiRide SafeAI |
| 2 | Magala | 0:20 | Picture this |
| 3 | Magala | 0:50 | What we’ll cover |
| 4 | Magala | 1:05 | Safety shouldn’t depend on a button |
| 5 | Magala | 2:05 | Proactive, not reactive |
| 6 | Magala | 2:35 | Who it’s for |
| 7 | Magala | 3:05 | How it works |
| 8 | Magala | 3:50 | A check-in, not an alarm |
| 9 | Magala | 4:30 | WhatsApp: a safety line, not just an alert |
| 10 | Magala | 5:10 | If you don’t answer |
| 11 | Magala | 5:55 | Know your driver before you get in |
| 12 | Magala | 6:35 | Safer and cheaper |
| 13 | Nhlanhla | 7:15 | How we built it on AWS |
| 14 | Nhlanhla | 8:30 | The full architecture |
| 15 | Nhlanhla | 9:15 | Built to be responsible |
| 16 | Nhlanhla | 9:45 | Request a ride, see the saving |
| 17 | Nhlanhla | 10:15 | Safe Journey Mode in action |
| 18 | Nhlanhla | 10:45 | Every trip leaves a record |
| 19 | Nhlanhla | 11:15 | What the operator sees |
| 20 | Magala | 11:55 | What the AI does, and doesn’t |
| 21 | Magala | 13:25 | The AI assistant in action |
| 22 | Nhlanhla | 14:05 | Why each AWS service |
| 23 | Nhlanhla | 15:05 | Live demo: the main user journey |
| 24 | Nhlanhla | 18:20 | Try it yourself |
| 25 | Nhlanhla | 19:20 | Working, simulated and still to come |
| 26 | Nhlanhla | 20:00 | Outstanding work |
| 27 | Nhlanhla | 20:40 | Expected impact |
| 28 | Magala | 21:10 | Safety shouldn’t depend on a button |

---

## Slide 1 · Cover: MzansiRide SafeAI

`Magala · 0:00 · about 20 seconds`

> **“Good day. I’m Magala, and this is Nhlanhla. We’re presenting MzansiRide SafeAI: a safety intelligence platform for ride operators, built for passengers in South Africa. I’ll take you through the problem and our solution. Nhlanhla will cover the architecture and the frontend. I’ll come back for the AI, and then Nhlanhla will explain our AWS implementation and run the live demo before I close.”**

*Cue: don’t linger on this slide.*

---

## Slide 2 · Picture this

`Magala · 0:20 · about 30 seconds`

> **“Imagine you’re in the back of a ride at night. The car stops somewhere you don’t recognise. Is it a detour? A phone call? Something worse?” *[pause]***

> **“Now imagine finding your phone, opening an app and pressing the right button, while your heart is racing.” *[pause]* “A panic button asks you to act in the hardest moment of your journey. We asked a different question: what if the system noticed first? This is MzansiRide SafeAI.”**

*Cue: speak slowly and let the last line land before you move on.*

---

## Slide 3 · What we’ll cover

`Magala · 0:50 · about 15 seconds`

> **“Here’s our route: the problem, our solution, the architecture and security, the frontend, the AI integration, our AWS implementation, the working prototype, and what’s still outstanding. Nhlanhla and I will share it, and we’ll tell you when we swap.”**

---

## Slide 4 · Safety shouldn’t depend on a button

`Magala · 1:05 · about 60 seconds`

> **“Let’s start with why this matters. For millions of South Africans, especially women travelling alone, getting into a car with an unfamiliar driver is a calculation made on every trip. Students and daily commuters worry about unexpected stops, route changes, and whether anyone they trust knows where they are. Today’s answer is the panic button, and it has three weaknesses. It is reactive: it only works if you’re able to press it. It is blunt: every unusual event looks the same. And it is invisible to the operator, who often learns about an incident when a complaint arrives, not when it begins. Cost matters too. Students and commuters need cheaper travel, and shared rides can help, but only if people feel safe sharing. So we asked one question: how can AI and cloud technology detect a problem early, support the passenger, and give the operator visibility, without ever assuming the worst about anyone?”**

*Cue: add a statistic only if you can name its source aloud.*

---

## Slide 5 · Proactive, not reactive

`Magala · 2:05 · about 30 seconds`

> **“We didn’t set out to build a better panic button. The difference is who acts first. On the left, a typical panic button needs you to notice, find it and press it. On the right, our system watches the trip data for you, checks in on WhatsApp with a single tap, uses rules to detect and AI to explain, and gives the operator a live view. Proactive, not reactive.”**

---

## Slide 6 · Who it’s for

`Magala · 2:35 · about 30 seconds`

> **“We built this for six groups: women and vulnerable passengers who want extra safety support; students who need affordable transport; daily commuters; budget-conscious passengers interested in shared rides; drivers, whose details and trip status passengers can see; and transport operators, who gain clearer visibility of trips and alerts. In this prototype, every passenger and driver profile is simulated, not real people’s information.”**

---

## Slide 7 · How it works

`Magala · 3:05 · about 45 seconds`

> **“Here’s how it works. One: the passenger requests a ride, sees the driver and vehicle, and switches on Safe Journey Mode. Two: rules watch the trip for a long unexpected stop or a big route deviation. Three: when a rule fires, we check in on WhatsApp and in the app: ‘Are you safe? Reply 1 for yes, 2 for help.’ Four: if she replies help, or doesn’t reply, the system escalates. Five: the operator sees it on a live dashboard with an AI summary, and everything is recorded. We never assume the driver is acting maliciously. A stop can have an innocent explanation, so the passenger is always asked first. In the prototype, the stops and deviations are simulated.”**

---

## Slide 8 · A check-in, not an alarm

`Magala · 3:50 · about 40 seconds`

> **“We chose WhatsApp for three reasons. It works outside our app, so nothing needs to be opened. It’s already on every phone, with no extra app to install. And it asks for one tap, not a search for a button in a crisis. Reply 1 and the alert closes. Reply 2, or no reply, and escalation begins. Silence is recorded as a fact, never as a conclusion.”**

*Cue: the message on screen is an example. Don’t say WhatsApp needs no mobile data.*

---

## Slide 9 · WhatsApp: a safety line, not just an alert

`Magala · 4:30 · about 40 seconds`

> **“WhatsApp isn’t only where alerts arrive. It’s a two-way channel on a real number. A passenger can type CHECK to look up a driver, which is simulated, TRIP to link the chat to her trip, STATUS to see it, SOS to alert her trusted contact, or 1 or 2 to answer a check-in. Or she can simply describe her situation and our AI assistant guides her. We’ll show that assistant in the AI section.”**

---

## Slide 10 · If you don’t answer

`Magala · 5:10 · about 45 seconds`

> **“A fair question: what happens if you don’t answer? Here is the workflow. The check-in goes out on WhatsApp and in the app. A wait window follows, and the operator sets how long. If there’s no reply, or she sends a 2, her trusted contact is messaged. The operator’s screen turns red with the AI’s one-line next step. Then a person acts: the operator calls the driver, and everything is logged. Reply 1 at any point and the alert closes. We never auto-call emergency services, and we never assume wrongdoing. People make those decisions.”**

*Cue: this is built. The operator sets the wait window on the Fleet page (1 to 5 minutes) and a reminder goes out halfway. Before the demo, set it to 5 minutes so there is time to reply.*

---

## Slide 11 · Know your driver before you get in

`Magala · 5:55 · about 40 seconds`

> **“We want passengers to know who is driving before they get in. At the start of every ride, the driver unlocks the app with Face ID or a fingerprint on their own phone. The passenger sees ‘Verified at the start of this ride’ or ‘Not verified’, and decides. We’re honest about the limits. A phone biometric proves who unlocked the phone, not that they hold a licence, so a one-time ID check at sign-up is still needed. Drivers without a biometric phone show as ‘Not verified’. Face data stays on the driver’s phone, and we only receive a pass or a fail.**

*Cue: say clearly that the Face ID result is SIMULATED in the prototype: the driver card shows “Driver verified with Face ID at the start of this ride” (or “not verified”) when the trip starts. Real biometrics come later.*

---

## Slide 12 · Safer and cheaper

`Magala · 6:35 · about 40 seconds`

> **“Now the part that makes a difference to the pocket. The same trip costs R67.50 alone. Share it with one other person and it’s R40.50 each. Share it with two others and it’s R27.00 each, which is 60 percent cheaper per rider. We show that saving before you book, right next to the safety check-ins, because sharing only works when people feel safe sharing. These fares are illustrative, from simple pricing rules, on a simulated trip.”**

*Handover: “That’s our solution. Nhlanhla will now show you how we built it.”*

*Cue: don’t claim that no competitor offers shared rides. Some do.*

---

## Slide 13 · How we built it on AWS

`Nhlanhla · 7:15 · about 75 seconds`

> **“Thanks. Let me walk one alert through our architecture. We chose a serverless design on AWS, so it scales automatically and cost grows with use. The React app is served through Amazon CloudFront, and it sends requests to Amazon API Gateway, our front door. API Gateway is also the webhook for WhatsApp: every message and reply from the passenger arrives here. It triggers AWS Lambda, the brain. Lambda runs the rule engine, sends the check-ins, handles escalation, and calls Amazon Bedrock, which returns the triage line, the explanation or the assistant’s answer. Amazon DynamoDB stores trips, alerts and the safety log, and Amazon CloudWatch records logs so we can trace every alert. The red dashed line is the outbound side: check-ins and AI replies travel from Lambda back out to the passenger on WhatsApp. In one line: WhatsApp is how we reach the passenger, and API Gateway is how that conversation reaches our system.”**

*Cue: point to each box as you name it. If a service isn’t wired up yet, call it planned.*

---

## Slide 14 · The full architecture

`Nhlanhla · 8:30 · about 45 seconds`

> **“Here is the full picture, following one alert with the numbers. One: the passenger opens the app from CloudFront, which serves it from Johannesburg and Cape Town. Two: API calls go through API Gateway to the api Lambda. Three: the rules flag a stop or a deviation and store the event in DynamoDB. Four: Bedrock explains it, and writes the operator's triage line if it escalates. Five and six: WhatsApp messages arrive through our OpenWA gateway on EC2, and check-ins, replies and the trusted-contact alert go back out the same way. Around that: operators sign in with Cognito, SNS emails us when something is down, secrets are in SSM, and everything is logged in CloudWatch. Orange dashed is simulated, the journey replay. Grey dashed is planned, Amazon Location Service for live GPS.”**

*Cue: point at each number as you say it. Don't read the box labels.*

---

## Slide 15 · Built to be responsible

`Nhlanhla · 9:15 · about 30 seconds`

> **“Security and privacy are designed in. We use simulated data only, so no real location data is collected. An unusual event is a prompt to check in, never proof of wrongdoing. The AI works only from approved safety information, and it is clearly not an emergency service: in danger, call 10111 or 112. We store minimal data, control access at the backend, and keep credentials out of the frontend. We’ve designed with POPIA in mind, and a production version would need a formal assessment.”**

---

## Slide 16 · Request a ride, see the saving

`Nhlanhla · 9:45 · about 30 seconds`

> **“This is the working frontend. The passenger chooses a pickup and destination from predefined Johannesburg locations on real road routes, and sees the individual fare, R67.50 for this trip, next to the shared options: R40.50 with two riders and R27.00 with three. It’s marked simulated, and the fares are illustrative.”**

---

## Slide 17 · Safe Journey Mode in action

`Nhlanhla · 10:15 · about 30 seconds`

> **“Once the trip starts, Safe Journey Mode is on and watching for unusual stops and route changes. The passenger can see her trusted contact, share her trip, or send an SOS in one tap. The page says plainly what is real and what is simulated: WhatsApp alerts to the trusted contact are real, and the SMS is labelled simulated, so nothing here is hidden.”**

---

## Slide 18 · Every trip leaves a record

`Nhlanhla · 10:45 · about 30 seconds`

> **“When the trip ends, the summary shows the fare, the distance and the number of safety alerts, plus what sharing would have saved, about R27 on this trip. Below it, the safety log is stored in DynamoDB. On the right, the driver card says ‘demo driver, not verified’ and tells the passenger to check the plate, the car and the driver before getting in.”**

---

## Slide 19 · What the operator sees

`Nhlanhla · 11:15 · about 40 seconds`

> **“This is what the operator sees. Most trips are green. The one that needs attention turns red, with the AI’s one-line next step: stopped off-route, passenger unresponsive on WhatsApp, request an immediate driver voice call. Operators get live status, a clear next step instead of a raw alert, and a full record of every alert and response.”**

> Point at the bottom panel: “This is system health. Is WhatsApp working, which AI model is answering, what was sent today, and any errors in the last hour. We see a problem before the passenger does.”

*Handover: “I’ll hand back to Magala to explain the AI.”*

*Cue: this is a real screenshot of the live Fleet page. The trips are a simulated demo fleet; the AI triage lines are real Amazon Bedrock output.*

---

## Slide 20 · What the AI does, and doesn’t

`Magala · 11:55 · about 90 seconds`

> **“Thanks, Nhlanhla. Now the AI, and just as importantly, how we don’t use it. We made one deliberate decision: detection and intelligence are separate. Detection is rule-based. Deterministic rules decide whether an event has occurred, for example a stop beyond a set time and off the planned route. That makes the system predictable, testable and auditable, and we never let a language model decide whether someone is in danger. Once a rule fires, the AI, running on Amazon Bedrock, does three jobs. It writes a one-line triage action for the fleet manager. It explains to the passenger, in calm plain language, what happened and what her options are. And it answers safety questions on WhatsApp and in the app, from approved guidance only. Why AI? Because turning a raw event into a calm, clear sentence in seconds is exactly what language models do well. And the limits: it never decides someone is in danger, never blames the driver or predicts crime, never claims a passenger is safe, and never replaces emergency services. Rules detect. AI explains. People decide.”**

*Cue: if asked which model, name the Bedrock model you configured. If asked what happens when the AI is wrong: it never makes the safety decision.*

---

## Slide 21 · The AI assistant in action

`Magala · 13:25 · about 40 seconds`

> **“Here’s the assistant in a real chat with our prototype number. When we asked what it can do, it explained that it only helps with trip safety and the app. When we asked about Uber, it stayed on topic, said this is a prototype with simulated trips, and said Uber is a different service. In danger, it points to 10111 or 112. It even greets in isiZulu. People use it on WhatsApp by typing or replying 1 or 2, and in the app through the Assistant tab. Operators see the AI’s one-line next step on the fleet dashboard.”**

*Handover: “Nhlanhla will now explain why we chose each AWS service, and then show you the live demo.”*

---

## Slide 22 · Why each AWS service

`Nhlanhla · 14:05 · about 60 seconds`

> **“Thanks. Now let me explain why we chose each AWS service. CloudFront serves the app quickly and securely, with no web servers for us to run. API Gateway is the front door, including for WhatsApp, and it’s managed, secure and scales with traffic. Lambda runs our rules, check-ins, escalation and AI calls, and we pay only when it runs, so the same code serves one trip or a national fleet. Bedrock gives us foundation models as a service, with no model servers to build. DynamoDB stores trips, alerts and the safety log, fast and scalable, which gives operators their audit trail. CloudWatch lets us trace and prove what happened. And IAM gives each function only the access it needs. It’s serverless throughout: we pay for what we use, and nothing sits idle.”**

*Cue: delete the row of any service you haven’t actually wired up before you present.*

*If asked about sign-in or alerts: “Operators sign in with **Amazon Cognito**, and API Gateway checks the token before any code runs. **Amazon SNS** emails the team when something is down, and EventBridge runs a health check every five minutes.”*

---

## Slide 23 · Live demo: the main user journey

`Nhlanhla · 15:05 · about 3 minutes 15 seconds`

> **“Now let’s see it running. Here is the main user journey. One: I request a ride. Two: here’s the driver and vehicle, a labelled demo driver. Three: I switch on Safe Journey Mode. Four: I trigger a simulated stop. Five: watch the phone. The check-in arrives on WhatsApp.” *[hold up the phone. Reply 1, or deliberately don’t]* “Six: on the operator’s dashboard, the alert appears. Seven: finally, the shared-ride saving. Remember: the trip and events are simulated, the WhatsApp number is real, and the assistant runs on Amazon Bedrock.”**

*Cue: before you start, set the Fleet wait window to 5 minutes and the simulator to 15× speed, so there is time to reply on the phone. If time allows, show the AWS console in this order: API Gateway, Lambda, DynamoDB, CloudWatch. Keep backup screenshots and a screen recording ready in case anything fails, and switch to them without apologising.*

*Before you start: **sign in on the Fleet page** (Cognito, your own password) in a separate tab, and keep it signed in. The team code no longer works on the live site.*

*Real vs simulated during the demo: the WhatsApp check-in and the trusted contact's WhatsApp alert are **real**; the trip, the driver and the **SMS** are **simulated**.*

---

## Slide 24 · Try it yourself

`Nhlanhla · 18:20 · about 1 minute, while the audience scans`

> **“Now it's your turn. Scan a code. The left one opens the web app: book a ride with your own WhatsApp number, start the trip and press Simulate prolonged stop, and the check-in comes to your phone. The right one opens a WhatsApp chat with our bot: say hi, check a driver, or ask a safety question.” *[give them a few seconds, then switch to the Fleet page]* “While you do that, here's the operator's view. Your trips are appearing on the fleet map right now, and the ones that stop turn amber, then red, with the AI's next step.”**

*Cue: keep the Fleet page open in another tab, already signed in. Trips and drivers are simulated; if someone asks, it's not for real emergencies: 10111 or 112.*

---

## Slide 25 · Working, simulated and still to come

`Nhlanhla · 19:20 · about 40 seconds`

> **“Here’s an honest view of where we are. Working today: ride request with the fare comparison and a monthly budget; Safe Journey Mode with trusted contact, share trip and SOS; proactive WhatsApp check-ins on a real number, answered with 1, 2 or in your own words; the no-reply workflow with an operator-set wait window; the fleet dashboard with AI triage; the Amazon Bedrock assistant; and the safety log in DynamoDB. Simulated: trips and route events, driver profiles and the Face ID result, and the SMS to the trusted contact. The WhatsApp alerts are real. Still to come: live GPS, real driver verification, emergency-service integration, real payments, and a POPIA assessment with an operator pilot. We do not claim to prevent crime, guarantee safety or verify drivers.”**

---

## Slide 26 · Outstanding work

`Nhlanhla · 20:00 · about 40 seconds`

> **“We set ourselves six things to finish before Tuesday. All six are built and in today’s demo: the app is mobile friendly and can be installed on a phone; the AI assistant button is on every page; fares show weekly and monthly totals; the full no-reply workflow runs with an operator-set wait window; and the driver’s Face ID check shows at the start of each ride, simulated for now. And operators now sign in with Amazon Cognito, so only the operator’s safety team can open the fleet dashboard.”**

---

## Slide 27 · Expected impact

`Nhlanhla · 20:40 · about 30 seconds`

> **“Three groups benefit. Passengers get calm, clear support and a one-tap check-in. Operators get real-time visibility, faster response and a record of every alert. Communities get cheaper shared travel: a trip at R67.50 alone drops to R27.00 each when three riders share. Those are illustrative fares.”**

*Handover: “I’ll hand back to Magala to close.”*

---

## Slide 28 · Safety shouldn’t depend on a button

`Magala · 21:10 · about 70 seconds`

> **“Let’s go back to that car.” *[pause for a full beat]* “It’s night. It has stopped somewhere you don’t recognise. In most apps today, what happens next depends on you finding a button.**

> In MzansiRide SafeAI, it doesn’t. Your phone buzzes on WhatsApp: ‘Are you safe? Reply 1 or 2.’ One tap. And if you can’t reply, that silence isn’t ignored. The operator already has a clear next step on their screen, and every alert and response is on record. What you’ve seen today isn’t a mock-up of an idea. It’s a working prototype on AWS: a real WhatsApp number, an assistant on Amazon Bedrock, and a safety log in DynamoDB. The trips and drivers are simulated, and we’ve said so on every screen. Three things to remember. One: proactive, not reactive. We don’t wait for the worst moment to ask someone to act. Two: rules detect, AI explains, people decide. The AI helps, and it never judges and never blames. Three: it’s built to scale. It’s serverless, so the same design serves one operator or a national fleet, and the cost grows only with use. And safety isn’t only about fear. It’s about access. A student who shares a R67.50 ride and pays R27.00 is only willing to share if she feels safe doing it. Our next steps are live route data, driver verification, a POPIA assessment, and a pilot with a real operator. We’re not asking anyone to hand their safety to AI. We’re showing how AI can mean fewer passengers face that moment alone, and fewer operators find out too late. Safety shouldn’t depend on a button. Thank you.”

*Cue: slow down on the last sentence, say “Thank you” quietly, and add nothing after it.*

---

## If something goes wrong

| Problem | Do this (don't apologise, just switch) |
|---|---|
| WhatsApp message doesn't arrive | Show the same conversation in the app's **WhatsApp** page (simulator). Later: `make wa-restart` |
| The AI is slow | Carry on talking; the answer appears, or a labelled rules-based text does |
| The live site won't load | Switch to `make local` on the laptop (same screens, Fleet code `local`) |
| Fleet page asks you to sign in again | Sign in with your Cognito email and password (the session ends when the tab closes) |
| Everything fails | Use the screenshots in `docs/screenshots/` and the deck |
