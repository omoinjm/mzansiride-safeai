# Flash cards: Magala

**Your part:** the opening, the problem, the solution, the AI, and the close.
Slides 1–12, 19–20, 26, plus the try-it slide 27 during questions (about 10 minutes). Nhlanhla does the architecture, the frontend, AWS, the live demo and the
outstanding work.

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
  (500 m if still heading to the destination) · wait window **1–5 min**, reminder halfway · Bedrock about **$0.003 a call**.
- **In danger:** 10111 or 112. We never auto-call emergency services, and we never accuse the driver.

---

## Your slides

### Slide 1 · Cover · 0:00 · 20 s
**Open:** “Good day. I'm Magala, and this is Nhlanhla. We're presenting MzansiRide SafeAI.”
- A safety intelligence platform for ride operators, built for passengers in South Africa.
- **The order:** I do the problem and the solution · Nhlanhla does the architecture and the frontend · I do the AI ·
  Nhlanhla does AWS and the live demo · I close.

*Don't linger on this slide.*

### Slide 2 · Picture this · 0:20 · 30 s
**Open:** “Imagine you're in the back of a ride at night. The car stops somewhere you don't recognise.”
- “Is it a detour? A phone call? Something worse?” *Pause.*
- Finding your phone, opening an app, pressing the right button, while your heart is racing. *Pause.*
- **Land it:** “A panic button asks you to act in the hardest moment of your journey. We asked a different question: what
  if the system noticed first?”

*Speak slowly.*

### Slide 3 · What we'll cover · 0:50 · 15 s
- Problem → solution → architecture and security → frontend → AI → AWS → working prototype → outstanding work.
- “Nhlanhla and I will share it, and we'll tell you when we swap.”

### Slide 4 · Safety shouldn't depend on a button · 1:05 · 60 s
**Open:** “Let's start with why this matters.”
- Women alone, students and commuters: **unexpected stops, route changes, does anyone know where I am?**
- **Three weaknesses of the panic button:**
  - **Reactive:** it only works if you can press it.
  - **Blunt:** a phone call and a real problem look the same.
  - **Invisible to the operator:** they learn when a complaint arrives, not when it starts.
- **Cost:** students and commuters need cheaper travel; sharing works only if people feel safe sharing.
- **The question:** “How can AI and the cloud detect a problem early, support the passenger, and give the operator
  visibility, without ever assuming the worst about anyone?”

*Only quote a statistic if you can name its source aloud.*

### Slide 5 · Proactive, not reactive · 2:05 · 30 s
**Open:** “We didn't set out to build a better panic button. The difference is who acts first.”
- **Left:** you notice, find the button and press it.
- **Right:** the system watches the trip for you, checks in on WhatsApp with one tap, rules detect and AI explains, and the
  operator sees it live.

### Slide 6 · Who it's for · 2:35 · 30 s
- **Six groups:** women and vulnerable passengers · students · daily commuters · budget-conscious riders · drivers
  (passengers see their details) · transport operators (live visibility).
- “Every passenger and driver profile is simulated, not real people's information.”

### Slide 7 · How it works · 3:05 · 45 s
**Open:** “Here's how it works.”
1. **Request and activate:** see the driver and car, switch on Safe Journey Mode.
2. **The trip is watched:** a long unexpected stop, or a big route deviation.
3. **We check in:** “Are you safe? Reply 1 for yes, 2 for help”, on WhatsApp and in the app.
4. **We escalate:** if she says help, or doesn't reply.
5. **The operator sees it:** a live dashboard with an AI summary, and everything is recorded.

**Land it:** “We never assume the driver is acting maliciously. The passenger is always asked first.”

### Slide 8 · A check-in, not an alarm · 3:50 · 40 s
**Open:** “We chose WhatsApp for three reasons.”
- It works **outside our app**: nothing to open.
- It's **already on every phone**: nothing to install.
- **One tap, not a search** for a button in a crisis.
- Reply 1: the alert closes. Reply 2, or no reply: escalation. “**Silence is recorded as a fact, never as a conclusion.**”

*Don't say WhatsApp needs no mobile data.*

### Slide 9 · WhatsApp: a safety line, not just an alert · 4:30 · 40 s
**Open:** “WhatsApp isn't only where alerts arrive. It's a two-way channel on a real number.”
- **CHECK** a driver (simulated) · **TRIP** to link the chat · **STATUS** · **SOS** · **1 or 2** to answer.
- Or she simply describes her situation, and the AI assistant guides her.

### Slide 10 · If you don't answer · 5:10 · 45 s
**Open:** “A fair question: what happens if you don't answer?”
- The check-in goes out → a **wait window the operator sets** (1–5 min), with a **reminder halfway**.
- No reply, or a 2 → the **trusted contact is messaged** → the operator's screen turns **red** with the AI's next step.
- **A person acts:** the operator calls the driver, and it's all logged. Reply 1 at any point and the alert closes.
- “**We never auto-call emergency services, and we never assume wrongdoing. People make those decisions.**”

### Slide 11 · Know your driver before you get in · 5:55 · 40 s
**Open:** “We want passengers to know who is driving before they get in.”
- The driver unlocks the app with **Face ID or a fingerprint** at the start of every ride.
- The passenger sees **“Verified at the start of this ride”** or **“Not verified”**, and decides.
- **Limits:** it proves who unlocked the phone, not that they hold a licence, so an ID check at sign-up is still needed.
- Face data stays on the driver's phone; we get only a pass or a fail.
- **Say clearly: the Face ID result is SIMULATED in the prototype.**

### Slide 12 · Safer and cheaper · 6:35 · 40 s
**Open:** “Now the part that makes a difference to the pocket.”
- **R67.50 alone · R40.50 each with two · R27.00 each with three = 60% cheaper per rider.**
- The saving shows before you book, next to the safety check-ins: sharing works only when people feel safe sharing.
- Illustrative fares, on a simulated trip.

**Hand over:** “That's our solution. Nhlanhla will now show you how we built it.”

*Don't claim that no competitor offers shared rides.*

### Slide 19 · What the AI does, and doesn't · 11:10 · 90 s
**Open:** “Thanks, Nhlanhla. Now the AI, and just as importantly, how we don't use it.”
- **Detection and intelligence are separate.** Rules decide that an event happened: predictable, testable, auditable.
  “We never let a language model decide whether someone is in danger.”
- **The AI's three jobs (Amazon Bedrock):**
  1. A **one-line triage action** for the fleet manager.
  2. A **calm, plain explanation** for the passenger: what happened and her options.
  3. **Answers safety questions** on WhatsApp and in the app, from approved guidance only.
- **Why AI:** turning a raw event into a calm, clear sentence in seconds is what language models do well.
- **Limits:** it never decides someone is in danger, never blames the driver or predicts crime, never says a passenger is
  safe, and never replaces emergency services.
- **Land it:** “**Rules detect. AI explains. People decide.**”

*Which model? Claude Haiku 5.5 on Bedrock is the main model; **Amazon Nova Lite** answers today, because our AWS account
is on the free plan.*

### Slide 20 · The AI assistant in action · 12:40 · 40 s
**Open:** “Here's the assistant in a real chat with our prototype number.”
- It **stays on topic**: trip safety and the app only.
- Asked about Uber, it said this is a prototype and Uber is a different service.
- In danger, it points to **10111 or 112**. It even **greets in isiZulu**.
- **Where people use it:** WhatsApp (typing, or 1 and 2), the Assistant tab, and the operator's triage line.

**Hand over:** “Nhlanhla will now explain why we chose each AWS service, and then show you the live demo.”

### Slide 26 · Close · 19:25 · 70 s
**Open:** “Let's go back to that car.” *Full pause.*
- It's night, and it stopped somewhere you don't know. In most apps, what happens next depends on you finding a button.
- **Here it doesn't:** WhatsApp buzzes, “Are you safe? Reply 1 or 2.” One tap. And silence isn't ignored: the operator
  already has a next step on screen, and everything is on record.
- **Not a mock-up:** a working prototype on AWS, with a real WhatsApp number, Bedrock and DynamoDB. The trips and drivers
  are simulated, and we said so on every screen.
- **Three things to remember:** proactive, not reactive · rules detect, AI explains, people decide · built to scale.
- **Access:** a student who pays R27.00 instead of R67.50 will only share if she feels safe doing it.
- **Next steps:** live route data, driver verification, a POPIA assessment, a pilot with a real operator.

*Slow down on the last sentence. Say “Thank you” quietly, and add nothing after it.*

### Slide 27 · Try it yourself · after the close, during questions
**Open:** “If you'd like to try it, scan a code.”
- **Left, the web app:** book a ride with your own WhatsApp number, start the trip, press **Simulate prolonged stop**, and
  the check-in comes to your phone.
- **Right, WhatsApp:** say hi, **CHECK CA 123-456**, or ask a safety question.
- “The trips and drivers are simulated, so please don't use it in a real emergency.”

*Only after the live demo: a room full of people using it at once can slow the demo down.*

---

## Questions you'll likely get

**Q: Isn't this just another panic button?**
A: No. A panic button is reactive: you act in the crisis. We're proactive: the rules watch every reading, we reach out on
WhatsApp first, and if she needs help or doesn't answer, the system acts for her. SOS still exists as a backup.

**Q: What does the AI do that rules can't?**
A: The rules detect “stopped 240 s off-route”. The AI turns that into a calm explanation for this trip, reads a reply in
the passenger's own words (“we took a detour, still going to Sandton”), and writes the operator's next step. Templates
can't handle free text.

**Q: What if the AI is wrong or gives harmful advice?**
A: It never makes the safety decision: the rules raise the alert, and escalation runs on a timer. Its answers come from
approved guidance, Bedrock Guardrails filter harmful content and profiling, and emergency numbers always appear. If
Bedrock is down, a labelled rules-based text is shown.

**Q: Can the AI wrongly close an alert?**
A: Not by guessing. Danger words (“knife”, “locked”, “won't stop”) escalate without the AI. An unclear reply never closes
the alert; we ask again and the clock keeps running.

**Q: Isn't flagging stops unfair to drivers?**
A: An event is a check-in to the passenger, never an accusation. The driver isn't penalised, the AI is told to mention
normal reasons, and most alerts end in “I'm OK”.

**Q: Why does the triage mention the driver's safety score? Isn't that biased?**
A: It's context, not evidence. The AI is forbidden to blame or speculate about crime, and the Guardrail blocks profiling.
In the prototype the score is fictional; in production it would come from the operator's records and be audited for
fairness.

**Q: Who pays for this?**
A: The e-hailing operator (B2B): a small fee per monitored trip. They get fewer incidents, faster response and an audit
trail. Other partners: universities, employers, insurers. Passengers stay free; safety can't be an upsell.

**Q: Why WhatsApp and not push notifications?**
A: It works when the app is closed, it's what South Africans already use, and WhatsApp bundles are cheap where general
data isn't. (Don't say it needs no data at all.)

**Q: Is the Face ID real?**
A: No, and the app says “Simulated”. In the real design, the driver's own phone checks the face or fingerprint and we get
only a pass or a fail. Biometrics are special information under POPIA, so it needs a formal assessment and an ID check at
sign-up.

**Q: What if the driver follows Waze and takes a different road?**
A: We store the other sensible roads between two places and don't flag those. On an unknown road that's still heading to
the destination, we wait longer (500 m off-route, not 250 m) before asking. A car heading away still triggers a check-in.

**Q: Which AI model do you use?**
A: Amazon Bedrock. Claude Haiku 5.5 is the main model; Amazon Nova Lite answers today, because our AWS account is on the
free plan. Same prompt, same Guardrail, and it's one setting to switch back.

**Q: What about POPIA?**
A: The prototype uses simulated data only. We minimise data: alerts expire after 14 days, plate photos aren't stored, and
contacts are messaged only on escalation. Production needs consent at booking, a cross-border assessment (the AI runs in
Ireland) and a biometrics assessment.

**Q: If we gave you funding, what would you do first?**
A: A pilot with one operator or a campus shuttle, to measure false alarms and response times. Then the official WhatsApp
API, a POPIA assessment, live GPS, and isiZulu, Sesotho and Afrikaans.

**Q: Who did what?**
A: Answer honestly and together, with the split you actually agreed (decide it before you present, so you both say the
same thing). Then add: both of us can walk the diagram and the demo.
