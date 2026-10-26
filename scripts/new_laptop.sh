#!/usr/bin/env bash
# Get a fresh laptop ready to run MzansiRide on AWS (deploy, logs, WhatsApp admin, local backup demo).
#
#   ./scripts/new_laptop.sh save     # on the OLD laptop, once: keep infra/terraform.tfvars in SSM (encrypted)
#   ./scripts/new_laptop.sh          # on the NEW laptop, after git clone: checks, login, tfvars, deps, terraform
#   ./scripts/new_laptop.sh --plan   # same, then a terraform plan that should say "No changes"
#
# infra/terraform.tfvars is git-ignored (WhatsApp number, admin emails). Without it a local deploy would remove the
# alert-email subscriptions and the operator accounts, so this script fetches it from SSM instead.
set -euo pipefail
cd "$(dirname "$0")/.."

REGION="$(sed -n 's/^region *= *"\(.*\)"/\1/p' infra/backend.hcl)"
ACCOUNT="$(sed -n 's/^bucket *= *"mzansiride-tfstate-\([0-9]*\)-.*"/\1/p' infra/backend.hcl)"
PARAM="/mzansiride/local/terraform.tfvars"   # outside /mzansiride/openwa/, so the Lambdas can't read it
export AWS_PROFILE="${AWS_PROFILE:-default}" AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"
step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mxx %s\033[0m\n' "$*"; exit 1; }

logged_in() { aws sts get-caller-identity --query Account --output text 2>/dev/null; }
need_login() {
  local acct; acct="$(logged_in || true)"
  if [ -z "$acct" ]; then
    warn "Not logged in to AWS (profile $AWS_PROFILE). Starting 'aws login' (on WSL/SSH use: aws login --remote)."
    aws login || die "Login failed. Run 'aws login' (or 'aws login --remote'), then re-run this script."
    acct="$(logged_in)" || die "Still not logged in."
  fi
  [ "$acct" = "$ACCOUNT" ] || die "Logged in to account $acct, but the stack lives in $ACCOUNT. Use the right profile: AWS_PROFILE=<name> $0"
  echo "AWS account $acct, region $REGION, profile $AWS_PROFILE"
}

if [ "${1:-}" = "save" ]; then
  [ -f infra/terraform.tfvars ] || die "infra/terraform.tfvars not found on this laptop."
  need_login
  aws ssm put-parameter --name "$PARAM" --type SecureString --overwrite \
    --value "file://infra/terraform.tfvars" --description "MzansiRide infra/terraform.tfvars (git-ignored)" >/dev/null
  echo "Saved infra/terraform.tfvars to SSM $PARAM (SecureString). On the new laptop: ./scripts/new_laptop.sh"
  exit 0
fi

# ---------- 1. tools ----------
step "1/5 Tools"
missing=()
have() { command -v "$1" >/dev/null 2>&1; }
check() {  # name, install hint
  if have "$1"; then printf '  ✅ %-24s %s\n' "$1" "$($1 --version 2>&1 | head -1 | cut -c1-60)"
  else printf '  ✗  %-24s install: %s\n' "$1" "$2"; missing+=("$1"); fi
}
check git       "sudo apt install -y git"
check aws       "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html (v2.32+ for 'aws login')"
check terraform "https://developer.hashicorp.com/terraform/install (1.10+)"
check python3   "sudo apt install -y python3"
check uv        "curl -LsSf https://astral.sh/uv/install.sh | sh"
check node      "https://nodejs.org (22+), or: curl -fsSL https://fnm.vercel.app/install | bash && fnm install 22"
check npm       "comes with node"
check make      "sudo apt install -y make"
if have session-manager-plugin; then printf '  ✅ %-24s\n' "session-manager-plugin"
else printf '  ⚠  %-24s only for make wa-dashboard: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html\n' "session-manager-plugin"; fi
have gh || printf '  ⚠  %-24s optional (CI runs, secrets): https://cli.github.com\n' "gh"
[ ${#missing[@]} -eq 0 ] || die "Install the missing tools above, then re-run: ${missing[*]}"
node -e 'process.exit(+process.versions.node.split(".")[0] >= 22 ? 0 : 1)' || die "Node 22+ is needed (found $(node --version))."
aws login help >/dev/null 2>&1 || warn "This AWS CLI has no 'aws login': upgrade to v2.32+, or use 'aws configure sso' / access keys."

# ---------- 2. AWS ----------
step "2/5 AWS login"
need_login

# ---------- 3. private settings ----------
step "3/5 infra/terraform.tfvars (WhatsApp number, admin emails)"
if [ -f infra/terraform.tfvars ]; then
  echo "Already present, kept as is."
elif aws ssm get-parameter --name "$PARAM" --with-decryption --query Parameter.Value --output text > infra/terraform.tfvars.tmp 2>/dev/null; then
  mv infra/terraform.tfvars.tmp infra/terraform.tfvars && chmod 600 infra/terraform.tfvars
  echo "Fetched from SSM $PARAM ($(grep -c '=' infra/terraform.tfvars) settings; values not shown)."
else
  rm -f infra/terraform.tfvars.tmp
  warn "Not in SSM yet. Either run './scripts/new_laptop.sh save' on the old laptop, or create infra/terraform.tfvars:"
  warn '    wa_number    = "+27 ..."            # the bot number'
  warn '    admin_emails = ["you@...", "teammate@..."]'
  warn "Until then, deploy by pushing to main (CI has these values) and DON'T run make deploy here."
fi

# ---------- 4. dependencies ----------
step "4/5 Dependencies (.venv + web/node_modules + build)"
make setup
make web >/dev/null && echo "Web app built (web/dist): make local works offline as the backup demo."

# ---------- 5. terraform ----------
step "5/5 Terraform state ($(sed -n 's/^bucket *= *"\(.*\)"/\1/p' infra/backend.hcl))"
make init >/dev/null && echo "terraform init OK"
URL="$(make -s url)"
python3 -c "import json,sys,urllib.request; assert json.load(urllib.request.urlopen(sys.argv[1]+'/api/health',timeout=15)).get('ok')" "$URL" \
  && echo "Live site healthy: $URL" || warn "Live site health check failed: $URL"
if [ "${1:-}" = "--plan" ]; then
  [ -f infra/terraform.tfvars ] || die "No infra/terraform.tfvars: skipping the plan (it would show the emails being removed)."
  eval "$(aws configure export-credentials --format env)"
  terraform -chdir=infra plan -input=false -detailed-exitcode -no-color >/dev/null 2>&1 && echo "terraform plan: No changes (this laptop is in sync)" \
    || warn "terraform plan shows changes or failed: run 'make plan' and read it before any deploy."
fi

step "Ready"
cat <<EOF
Live app:        $URL   (Fleet: sign in with your Cognito email)
WhatsApp:        make wa-status   ·   make wa-restart if sends hang   ·   make wa-send TO=<number>
Logs:            make logs   ·   make logs-wa
Backup demo:     make local   ->  http://localhost:8077 (Fleet code: local)
Deploy:          push to main (CI), or make deploy (needs infra/terraform.tfvars)
E2E tests:       cd web && npx playwright install chromium   (once), then make e2e
EOF
