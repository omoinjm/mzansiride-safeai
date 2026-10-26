# `aws login` / SSO sessions are not readable by Terraform directly, so export them first.
CREDS := eval "$$(aws configure export-credentials --format env 2>/dev/null)";
TF   := $(CREDS) terraform -chdir=infra
PY   := .venv/bin/python
# The active AWS target (account + region) is whatever infra/backend.hcl points at (scripts/switch_account.sh).
REGION ?= $(shell sed -n 's/^region *= *"\(.*\)"/\1/p' infra/backend.hcl)

.PHONY: help setup test web lint e2e local local-ai init plan deploy site url logs logs-wa wa-setup wa-qr wa-status wa-dashboard wa-restart wa-send sms-verify switch destroy

help:
	@echo "setup      .venv + web/node_modules"
	@echo "test       backend unit tests + frontend typecheck/lint"
	@echo "local      run the full app locally on :8077 (in-memory DB, offline AI fallback) = backup demo"
	@echo "local-ai   same, but with real Amazon Bedrock (needs aws login)"
	@echo "e2e        Playwright journey tests (E2E_URL=... for the live site)"
	@echo "deploy     tests -> terraform plan/apply -> upload site"
	@echo "url        live URL (Fleet page sign-in: Amazon Cognito, invite emails go to admin_emails)"
	@echo "wa-setup   create the OpenWA session + webhook (once), wa-qr shows the QR to scan"
	@echo "wa-restart recreate OpenWA if WhatsApp sends hang (fresh browser, keeps the login; ~1 min)"
	@echo "wa-send    TO=0821234567 [MSG='...']: send a test WhatsApp message through the real path"
	@echo "wa-dashboard  private tunnel to the OpenWA dashboard on http://localhost:2785 (scan the QR there)"
	@echo "logs       tail API logs   logs-wa  tail WhatsApp logs"
	@echo "switch     REGION_TO=us-east-1 [ARGS='--check|--old-profile default|--ci']: move the stack to the account you're logged into"
	@echo "sms-verify [NUMBER=0821234567]: SNS SMS sandbox status, or verify a number to receive SMS"
	@echo "destroy    tear everything down"

setup:
	uv venv -q .venv && uv pip install -q --python $(PY) -r requirements-dev.txt
	cd web && npm ci

test:
	$(PY) -m pytest -q tests
	cd web && npx tsc -b && npx eslint .

web:
	cd web && npm run build

lint:
	cd infra && terraform fmt -check -recursive

e2e:
	cd web && npx playwright test

local: web
	$(PY) scripts/local_server.py

local-ai: web
	$(CREDS) $(PY) scripts/local_server.py --bedrock

init:
	$(TF) init -reconfigure -backend-config=backend.hcl

plan:
	$(TF) plan -out=tfplan

# Apply exactly the reviewed plan, then publish the SPA.
deploy: test web
	$(TF) plan -out=tfplan
	$(TF) apply tfplan
	$(MAKE) site

site:
	$(CREDS) aws s3 sync web/dist "s3://$$($(TF) output -raw web_bucket)" --delete --region $(REGION) \
	  --cache-control "public,max-age=31536000,immutable" --exclude index.html
	$(CREDS) aws s3 cp web/dist/index.html "s3://$$($(TF) output -raw web_bucket)/index.html" --region $(REGION) \
	  --cache-control "no-cache"
	$(CREDS) aws cloudfront create-invalidation --distribution-id "$$($(TF) output -raw distribution_id)" --paths "/index.html" "/" >/dev/null
	@echo "Live: $$($(TF) output -raw web_url)"

url:
	@$(TF) output -raw web_url; echo

logs:
	$(CREDS) aws logs tail "$$($(TF) output -raw api_log_group)" --follow --format short --region $(REGION)

logs-wa:
	$(CREDS) aws logs tail "$$($(TF) output -raw whatsapp_log_group)" --follow --format short --region $(REGION)

wa-setup:
	$(CREDS) ./scripts/openwa.sh setup

wa-qr:
	$(CREDS) ./scripts/openwa.sh qr

wa-status:
	$(CREDS) ./scripts/openwa.sh status

wa-dashboard:
	$(CREDS) ./scripts/openwa.sh dashboard

wa-restart:
	$(CREDS) ./scripts/openwa.sh restart

sms-verify:
	$(CREDS) ./scripts/sms_verify.sh $(or $(NUMBER),status)

switch:
	./scripts/switch_account.sh --region "$(or $(REGION_TO),$(REGION))" $(ARGS)

wa-send:
	$(CREDS) ./scripts/openwa.sh send "$(TO)" "$(MSG)"

destroy:
	$(TF) destroy
