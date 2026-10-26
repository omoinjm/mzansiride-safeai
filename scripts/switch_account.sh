#!/usr/bin/env bash
# Move MzansiRide SafeAI to another AWS account/region (e.g. the hackathon sandbox) in one go.
#
#   AWS_PROFILE=sandbox ./scripts/switch_account.sh --region us-east-1 --check   # preflight only, changes nothing
#   AWS_PROFILE=sandbox ./scripts/switch_account.sh --region us-east-1           # full switch
#   AWS_PROFILE=sandbox ./scripts/switch_account.sh --region us-east-1 --old-profile default --ci
#
# Credentials: whatever the AWS CLI resolves (AWS_PROFILE, or AWS_ACCESS_KEY_ID/... env vars from the sandbox).
# Steps:
#   1. confirm the target account + region
#   2. pick Bedrock models this account can actually call (Claude Haiku 5.5 preferred, Nova Lite fallback)
#   3. state bucket in the new account (writes infra/backend.hcl) + infra/target.auto.tfvars (region, models)
#   4. terraform init -reconfigure + make deploy (tests, plan, apply, site upload)
#   5. smoke test (API, operator routes locked behind Cognito, Bedrock)
#   6. WhatsApp: wait for the new gateway, register the session + webhook, fetch the QR code
#   7. optional --old-profile: stop the OLD gateway instance, so two gateways don't both answer every message
#   8. optional --ci: point GitHub Actions deploys at the new account
# Switching back = run it again with the old profile and region (the old state bucket is found and reused).
set -euo pipefail
cd "$(dirname "$0")/.."

REGION="${AWS_REGION:-eu-west-1}"; CHECK_ONLY=0; YES=0; CI=0; OLD_PROFILE=""; OLD_REGION=""; SKIP_WA=0
while [ $# -gt 0 ]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    --check) CHECK_ONLY=1; shift ;;
    --yes|-y) YES=1; shift ;;
    --ci) CI=1; shift ;;
    --old-profile) OLD_PROFILE="$2"; shift 2 ;;
    --old-region) OLD_REGION="$2"; shift 2 ;;
    --skip-whatsapp) SKIP_WA=1; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)"; exit 2 ;;
  esac
done
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" REGION
step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mxx %s\033[0m\n' "$*"; exit 1; }
CURRENT_REGION="$(sed -n 's/^region *= *"\(.*\)"/\1/p' infra/backend.hcl 2>/dev/null || true)"
CURRENT_BUCKET="$(sed -n 's/^bucket *= *"\(.*\)"/\1/p' infra/backend.hcl 2>/dev/null || true)"

# ---------- 1. who are we? ----------
step "1/8 Target"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "No AWS credentials. Run 'aws login' (or export the sandbox's AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN) first."
ARN="$(aws sts get-caller-identity --query Arn --output text)"
echo "Account: $ACCOUNT   Region: $REGION   Identity: ${ARN##*/}"
echo "Current target: ${CURRENT_BUCKET:-none} (${CURRENT_REGION:-?})"
for cmd in terraform python3 npm; do command -v "$cmd" >/dev/null || die "$cmd is not installed"; done

# ---------- 2. Bedrock models ----------
step "2/8 Bedrock models available to this account"
case "$REGION" in eu-*) P=eu ;; us-*|ca-*) P=us ;; ap-*) P=apac ;; *) P=global ;; esac
try_model() {
  aws bedrock-runtime converse --region "$REGION" --model-id "$1" \
    --messages '[{"role":"user","content":[{"text":"Reply with OK"}]}]' \
    --inference-config '{"maxTokens":5}' --query 'output.message.content[0].text' --output text >/dev/null 2>&1
}
PRIMARY=""; FALLBACK=""
for m in "$P.anthropic.claude-haiku-5-5" "global.anthropic.claude-haiku-5-5" \
         "$P.anthropic.claude-haiku-4-5-20251001-v1:0" "global.anthropic.claude-haiku-4-5-20251001-v1:0"; do
  if try_model "$m"; then PRIMARY="$m"; echo "  ✅ $m"; break; else echo "  ✗  $m"; fi
done
for m in "$P.amazon.nova-lite-v1:0" "amazon.nova-lite-v1:0"; do
  if try_model "$m"; then FALLBACK="$m"; echo "  ✅ $m (fallback)"; break; else echo "  ✗  $m"; fi
done
if [ -z "$PRIMARY" ] && [ -z "$FALLBACK" ]; then
  warn "No Claude or Nova model answered in $REGION. The app still works (rules-based text), but enable model access"
  warn "in the Bedrock console (Model access) and re-run, or pick a region that has Bedrock."
  PRIMARY="$P.anthropic.claude-haiku-5-5"; FALLBACK="$P.amazon.nova-lite-v1:0"
elif [ -z "$PRIMARY" ]; then
  warn "Claude isn't available to this account yet: Nova Lite will answer (request Anthropic access in the Bedrock console)."
  PRIMARY="$FALLBACK"
fi
FALLBACK="${FALLBACK:-$PRIMARY}"
echo "Primary model: $PRIMARY   Fallback: $FALLBACK"
SANDBOX="$(aws sns get-sms-sandbox-account-status --region "$REGION" --query IsInSandbox --output text 2>/dev/null || echo unknown)"
echo "SNS SMS sandbox: $SANDBOX   (if True, verify each demo number: make sms-verify NUMBER=0821234567)"

if [ "$CHECK_ONLY" = 1 ]; then
  step "Check only: nothing was changed. Re-run without --check to switch."
  exit 0
fi
if [ "$YES" != 1 ]; then
  read -r -p "Deploy MzansiRide to account $ACCOUNT in $REGION and make it the active target? [y/N] " ok
  [[ "$ok" =~ ^[Yy] ]] || die "Cancelled"
fi

# ---------- 3. state + target config ----------
step "3/8 Terraform state bucket + target config"
REGION="$REGION" ./scripts/bootstrap_state.sh
cat > infra/target.auto.tfvars <<EOF
# The active AWS target's region and Bedrock models. Written by scripts/switch_account.sh; committed so
# local deploys and CI agree. (Phone numbers and other private values go in terraform.tfvars, git-ignored.)
region            = "$REGION"
model_id          = "$PRIMARY"
model_fallback_id = "$FALLBACK"
EOF
cat infra/target.auto.tfvars | tail -3

# ---------- 4. deploy ----------
step "4/8 Deploy (tests, terraform plan + apply, site upload): about 10 minutes on a new account"
[ -d .venv ] && [ -d web/node_modules ] || make setup
make init
make deploy
URL="$(make -s url)"

# ---------- 5. smoke test + demo settings ----------
step "5/8 Smoke test"
for i in $(seq 1 30); do
  python3 -c "import urllib.request,sys; urllib.request.urlopen(sys.argv[1]+'/api/health', timeout=10)" "$URL" 2>/dev/null && break
  sleep 10   # CloudFront can take a few minutes to start serving a new distribution
done
python3 - "$URL" <<'PY'
import json, sys, urllib.error, urllib.request
url = sys.argv[1]
health = json.load(urllib.request.urlopen(url + "/api/health", timeout=15))
assert health.get("ok"), health
try:
    urllib.request.urlopen(url + "/api/dashboard", timeout=15)
    sys.exit("The Fleet API answered without a sign-in: check the Cognito JWT authorizer")
except urllib.error.HTTPError as e:
    assert e.code == 401, e.code
print("API ok; operator routes need a Cognito sign-in")
reply = json.load(urllib.request.urlopen(urllib.request.Request(url + "/api/assistant", data=json.dumps({"message": "Is it normal for the driver to stop for fuel?"}).encode(), headers={"content-type": "application/json"}), timeout=60))
print("Assistant answered via:", reply.get("model") or "rules-based fallback")
PY

# ---------- 6. WhatsApp ----------
if [ "$SKIP_WA" = 1 ]; then
  warn "6/8 Skipping WhatsApp (--skip-whatsapp). Later: make wa-setup && make wa-dashboard"
else
  step "6/8 WhatsApp gateway (first boot takes ~3-5 minutes)"
  PREFIX="/mzansiride/openwa/"   # infra/main.tf: "/${var.name}/openwa/"
  for i in $(seq 1 60); do
    aws ssm get-parameter --region "$REGION" --name "${PREFIX}api_key" >/dev/null 2>&1 && break
    printf '.'; sleep 10
  done; echo
  aws ssm get-parameter --region "$REGION" --name "${PREFIX}api_key" >/dev/null 2>&1 \
    || die "The gateway didn't publish its API key in 10 min. Check the EC2 instance, then: make wa-setup"
  make wa-setup
  make wa-qr || true
  echo "Scan the QR with the bot phone: WhatsApp > Settings > Linked devices > Link a device."
  echo "QR expired? 'make wa-qr' again, or 'make wa-dashboard' and open http://localhost:2785 (shows a fresh QR)."
fi

# ---------- 7. stop the old gateway ----------
if [ -n "$OLD_PROFILE" ]; then
  step "7/8 Stopping the OLD WhatsApp gateway (profile $OLD_PROFILE)"
  OLD_REGION="${OLD_REGION:-${CURRENT_REGION:-eu-west-1}}"
  OLD_ID="$(AWS_PROFILE="$OLD_PROFILE" aws ec2 describe-instances --region "$OLD_REGION" \
    --filters "Name=tag:Name,Values=mzansiride-openwa" "Name=instance-state-name,Values=running" \
    --query 'Reservations[].Instances[].InstanceId' --output text 2>/dev/null || true)"
  if [ -n "$OLD_ID" ] && [ "$OLD_ID" != "None" ]; then
    AWS_PROFILE="$OLD_PROFILE" aws ec2 stop-instances --region "$OLD_REGION" --instance-ids $OLD_ID >/dev/null
    echo "Stopped $OLD_ID in $OLD_REGION (data kept; 'aws ec2 start-instances' brings it back)."
  else
    warn "No running old gateway found (or the old profile's login expired). If one is running, stop it or unlink it on the phone."
  fi
else
  warn "7/8 Old gateway not stopped. If the old account's gateway is still running, BOTH will answer WhatsApp messages:"
  warn "    re-run with --old-profile <old profile>, or on the bot phone remove the old device under Linked devices."
fi

# ---------- 8. CI ----------
if [ "$CI" = 1 ]; then
  step "8/8 GitHub Actions deploys -> account $ACCOUNT"
  ./scripts/bootstrap_ci.sh
  echo "Commit infra/backend.hcl and infra/target.auto.tfvars and push, so CI deploys here too."
else
  warn "8/8 CI not switched: pushes to main still deploy to the old target until you run with --ci and push"
  warn "    infra/backend.hcl + infra/target.auto.tfvars. Don't push those two files without it."
fi

step "Done"
cat <<EOF
App:        $URL
Fleet page: sign in with an admin_emails address. Cognito emails each one a temporary password
            (first sign-in asks for a new one). Set the check-in wait window there (5 min suits a demo).
Region:     $REGION   Models: $PRIMARY / $FALLBACK
Next:       scan the WhatsApp QR, then  make wa-send TO=<your number>  and book a test trip.
Switch back: AWS_PROFILE=<old profile> ./scripts/switch_account.sh --region ${CURRENT_REGION:-eu-west-1}
EOF
