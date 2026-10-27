# New laptop setup (AWS + MzansiRide)

How to get a different laptop ready to run, deploy and demo MzansiRide SafeAI in about 10 minutes.
One command does most of it: **`make laptop`** ([`scripts/new_laptop.sh`](../scripts/new_laptop.sh)).

## Once, on the old laptop

```bash
AWS_PROFILE=default make laptop-save
```

This keeps an encrypted copy (SSM Parameter Store, SecureString `/mzansiride/local/terraform.tfvars`) of
`infra/terraform.tfvars`. That file is git-ignored because it holds the bot's WhatsApp number and the two admin emails.
The Lambdas can't read this parameter; only a logged-in team member can.

## On the new laptop

### 1. Install the tools (skip any you have)

| Tool | Version | Ubuntu / WSL |
|---|---|---|
| git | any | `sudo apt install -y git make python3` |
| AWS CLI | v2.32+ (needed for `aws login`) | [install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Terraform | 1.10+ | [install guide](https://developer.hashicorp.com/terraform/install) |
| uv | any | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 22+ | `curl -fsSL https://fnm.vercel.app/install \| bash && fnm install 22` |
| Session Manager plugin | any | Only for `make wa-dashboard`: [install guide](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) |
| GitHub CLI (optional) | any | [cli.github.com](https://cli.github.com); `gh auth login` makes cloning the private repo easy |

`make laptop` checks all of these and prints the install command for anything missing.

### 2. Get the code and run the setup

```bash
gh auth login                       # the repo is private
git clone https://github.com/omoinjm/mzansiride-safeai.git && cd mzansiride-safeai
make laptop ARGS=--plan
```

What it does:
1. **Checks the tools** (above).
2. **Logs in to AWS.** It runs `aws login` if you aren't logged in (on WSL or over SSH, run `aws login --remote`
   yourself first). It stops if you're logged in to the wrong account; the stack lives in the account named in
   `infra/backend.hcl`. To use a named profile: `AWS_PROFILE=<name> make laptop`.
3. **Fetches `infra/terraform.tfvars` from SSM.** It never prints the values.
4. **Installs dependencies** (`.venv`, `web/node_modules`) and **builds the web app**, so `make local` works offline as
   the backup demo.
5. **Connects Terraform** to the shared state bucket (`terraform init`), checks the live site's health, and with
   `--plan` confirms **"No changes"**, which means this laptop is in sync with what's deployed.

At the end it prints the commands you'll need.

### 3. Check it's working

```bash
make url          # the live app
make wa-status    # WhatsApp gateway connected?
make local        # backup demo on http://localhost:8077 (Fleet code: local)
```

On the Fleet page, sign in with your **Cognito email and password**. Your account works in any browser, so there's
nothing to copy.

## Everyday commands

| Need | Command |
|---|---|
| Live URL | `make url` |
| WhatsApp status / fix stuck sends (keeps the login) | `make wa-status` / `make wa-restart` |
| Send a test WhatsApp message | `make wa-send TO=<number>` |
| OpenWA dashboard (private tunnel, scan a QR) | `make wa-dashboard`, then http://localhost:2785 |
| Logs | `make logs` (API) · `make logs-wa` (WhatsApp) |
| Tests | `make test` · `make e2e` (first time: `cd web && npx playwright install chromium`) |
| Deploy | Push to `main` (CI tests and deploys), or `make deploy` |
| Backup demo | `make local` |

## If something goes wrong

| Problem | Fix |
|---|---|
| `Your session has expired` | `aws login` (or `aws login --remote` on WSL). Logins expire often. |
| `Logged in to account X, but the stack lives in Y` | Wrong profile: `AWS_PROFILE=<name> make laptop` |
| tfvars "Not in SSM yet" | Run `make laptop-save` on the old laptop, or create `infra/terraform.tfvars` by hand. Until then deploy only by pushing to `main` (CI has these values); **don't** run `make deploy` |
| The plan shows changes | Don't deploy. Run `make plan`, read it, and check you're on the latest `main` (`git pull`) |
| `make wa-dashboard` fails | Install the Session Manager plugin |
| `aws login` isn't a command | Upgrade the AWS CLI to v2.32+ |
