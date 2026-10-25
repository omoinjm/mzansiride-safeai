# CLAUDE.md

## What this is
**MzansiRide SafeAI**: AWS AI Hackathon 2026 prototype (Praesignis). It's a safety-first ride-sharing app for South Africa: Safe Journey Mode check-ins, an Amazon Bedrock safety assistant, trusted-contact alerts, a fare comparison, and a WhatsApp channel via OpenWA. The proposal and requirements PDFs are in `docs/`. `docs/presentation-notes.md` is the Monday demo script, and `docs/aws-services-qa.md` holds the service rationale and Q&A. Region eu-west-1 (Bedrock isn't in af-south-1).

## Commands
```bash
make setup / make test            # pytest (tests/, moto-mocked DynamoDB) + tsc + eslint
.venv/bin/python -m pytest tests/test_rules.py -q
make local                        # app on :8077, in-memory DB, offline AI fallback (also the backup demo)
make e2e                          # Playwright (web/e2e), default against :8077; E2E_URL/TEAM_CODE for live
make deploy                       # plan -out + apply that plan + `make site` (S3 sync + invalidation)
make wa-setup / wa-qr / wa-status # OpenWA admin via SSM (scripts/openwa.sh)
```
Deploying = pushing to `main` (`.github/workflows/deploy.yml`, OIDC role `github-deploy-mzansiride`). The Makefile wraps Terraform with `aws configure export-credentials` because Terraform can't read `aws login` sessions. Port 8000 is taken on the dev machine, so local mode uses 8077.

## Architecture (cross-file)
- **`src/core/` is channel-agnostic.** The `api` Lambda (`api.handler.handler`) and `whatsapp` Lambda (`whatsapp.handler.handler`) ship the same zip of `src/` (no third-party deps). `core/commands.py` is the WhatsApp conversation logic, also used by the web simulator (`/api/whatsapp/simulate`, chat ids `sim:<session>`, pushed messages via the `outbox#` item).
- **Rules detect, AI explains.** `core/rules.py` is pure and unit-tested. Its thresholds are in `DEFAULTS` and are mirrored in UI copy (TripPage DemoControls, guidance.md). `core/assistant.py` only explains; on any Bedrock error it returns `source: "fallback"`. Explanations are cached on the event per channel.
- **Trip clock:** the browser simulator (`web/src/lib/sim.ts`) posts `ts` in trip seconds. The backend ignores readings with `ts <= last_ts`, so a resumed trip continues from `last_position.ts`. Escalation for no response (`CHECKIN_TIMEOUT_S`, trip time) is evaluated on telemetry readings.
- **Fleet view:** the pitch is B2B (operator safety team). `trips.dashboard()` returns `fleet` (live in-progress trips with a risk of red/amber/handled/green, from `_risk`). `assistant.triage` writes the operator's one-line action on every escalation/SOS, and `trips.acknowledge` (team code) marks a trip's escalated alerts as handled. `web/src/lib/fleet.ts` is the dashboard's 5-car demo fleet (Sarah's trip is scripted to go red).
- **Proactive WhatsApp:** `passenger_phone` at booking links the chat with no `TRIP` code (`_link_passenger_whatsapp`): real WhatsApp if allow-listed, else the browser's simulator session (`wa_session`).
- **Notifications:** `core/notify.py`. Real WhatsApp sends only via an async invoke of the whatsapp Lambda, and only to linked chats or `WA_ALLOWLIST`. Everything else is recorded as `simulated`.
- **OpenWA** (`infra/openwa.tf`, `openwa/user_data.sh.tftpl`): Caddy exposes only `send-text` and `health`. Secrets are in SSM `/mzansiride/openwa/*` (`api_key` is written by the instance on first boot, `session_id` by `scripts/openwa.sh setup`). Webhook HMAC is `X-OpenWA-Signature: sha256=<hex>`. The instance ignores AMI changes so the WhatsApp login isn't lost.
- **Frontend:** Vite + React 19 + Tailwind v4 (component classes are `@utility` in `index.css`). It talks to `/api` same-origin through CloudFront, and a CloudFront Function does the SPA rewrite. `routes.json` (OSM routes between 6 Joburg places) is the single source for maps and fares.
- **Terraform state** is in `mzansiride-tfstate-<account>-eu-west-1` (`scripts/bootstrap_state.sh` writes `infra/backend.hcl`). Same AWS account as RekogNail, whose stack has been torn down.

## Gotchas
- Lambda concurrency in this account is 10: don't add reserved concurrency.
- Keep "simulated" labels on anything that isn't real (judging requirement).
- Don't put the team code or phone numbers in docs or commits.
