#!/usr/bin/env bash
# Admin for the OpenWA gateway WITHOUT exposing its admin API: commands run on the instance via
# AWS Systems Manager (no SSH, no open admin port). Secrets are read on the instance from SSM.
#   ./scripts/openwa.sh setup    create session "mzansiride", register the webhook, start it
#   ./scripts/openwa.sh qr       fetch the pairing QR -> build/whatsapp-qr.png (scan: WhatsApp > Linked devices)
#   ./scripts/openwa.sh status   session status
#   ./scripts/openwa.sh logs     last OpenWA container logs
#   ./scripts/openwa.sh restart  recreate OpenWA if sends hang (fresh browser; the WhatsApp login is kept, no new QR)
#   ./scripts/openwa.sh send <phone> [message]  send a test message through the real path (Lambda -> gateway)
#   ./scripts/openwa.sh dashboard  SSM port-forward: OpenWA dashboard on http://localhost:2785 (never public)
set -euo pipefail
cd "$(dirname "$0")/.."
REGION="${REGION:-eu-west-1}"
TF="terraform -chdir=infra"
INSTANCE="$($TF output -raw openwa_instance_id)"
PREFIX="$($TF output -raw openwa_param_prefix)"
WEBHOOK_URL="$($TF output -raw webhook_url)"

remote() {
  # Runs a bash snippet on the instance; prints its stdout.
  local script="$1" id status
  id=$(aws ssm send-command --region "$REGION" --instance-ids "$INSTANCE" --document-name AWS-RunShellScript \
    --parameters "$(python3 -c 'import json,sys; print(json.dumps({"commands": [sys.argv[1]]}))' "$script")" \
    --query Command.CommandId --output text)
  for _ in $(seq 1 60); do
    sleep 2
    status=$(aws ssm get-command-invocation --region "$REGION" --command-id "$id" --instance-id "$INSTANCE" \
      --query Status --output text 2>/dev/null || echo Pending)
    case "$status" in Success|Failed|Cancelled|TimedOut) break ;; esac
  done
  aws ssm get-command-invocation --region "$REGION" --command-id "$id" --instance-id "$INSTANCE" \
    --query StandardOutputContent --output text
  [ "$status" = "Success" ] || { echo "remote command $status" >&2; aws ssm get-command-invocation --region "$REGION" --command-id "$id" --instance-id "$INSTANCE" --query StandardErrorContent --output text >&2; exit 1; }
}

# Prelude for every remote call: API key from SSM, curl helper against the local-only admin API.
PRELUDE="set -e; K=\$(aws ssm get-parameter --region $REGION --name '${PREFIX}api_key' --with-decryption --query Parameter.Value --output text); \
api() { curl -sS -H \"X-API-Key: \$K\" -H 'Content-Type: application/json' \"\$@\"; }; B=http://127.0.0.1:2785/api"

RECREATE='set -e
IMG=$(docker inspect -f "{{.Config.Image}}" openwa 2>/dev/null || true)
IMG=${IMG:-rmyndharis/openwa:0.25.0}
docker image inspect "$IMG" >/dev/null
docker rm -f openwa >/dev/null 2>&1 || true
docker run -d --name openwa --restart unless-stopped --network wa -p 127.0.0.1:2785:2785 --shm-size=1g \
  -v /opt/openwa/data:/app/data -e NODE_ENV=production -e DATABASE_TYPE=sqlite -e DATABASE_SYNCHRONIZE=true \
  -e ENGINE_TYPE=whatsapp-web.js -e AUTO_START_SESSIONS=true -e RESOLVE_LID_TO_PHONE=true \
  -e TRUSTED_PROXIES=172.16.0.0/12 "$IMG" >/dev/null
for i in $(seq 1 60); do sleep 3; docker logs openwa 2>&1 | grep -q "Session ready" && { echo "Session ready after $((i*3)) s"; exit 0; }; done
echo "Not ready after 3 min: check make wa-status"'

session_id() {
  aws ssm get-parameter --region "$REGION" --name "${PREFIX}session_id" --query Parameter.Value --output text 2>/dev/null || true
}

case "${1:-status}" in
  setup)
    SID="$(session_id)"
    if [ -z "$SID" ] || [ "$SID" = "None" ]; then
      OUT=$(remote "$PRELUDE; api -X POST \$B/sessions -d '{\"name\":\"mzansiride\"}'")
      SID=$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print(d.get("id") or d.get("data",{}).get("id"))' "$OUT")
      aws ssm put-parameter --region "$REGION" --name "${PREFIX}session_id" --type String --value "$SID" --overwrite >/dev/null
      echo "Created session $SID"
    fi
    remote "$PRELUDE; S=\$(aws ssm get-parameter --region $REGION --name '${PREFIX}webhook_secret' --with-decryption --query Parameter.Value --output text); \
      api -X POST \$B/sessions/$SID/webhooks -d \"{\\\"url\\\":\\\"$WEBHOOK_URL\\\",\\\"events\\\":[\\\"message.received\\\",\\\"session.status\\\"],\\\"secret\\\":\\\"\$S\\\"}\"; echo; \
      api -X POST \$B/sessions/$SID/start; echo"
    echo "Webhook -> $WEBHOOK_URL. Now run: make wa-qr"
    ;;
  qr)
    SID="$(session_id)"
    OUT=$(remote "$PRELUDE; api \$B/sessions/$SID/qr")
    mkdir -p build
    python3 - "$OUT" <<'PY'
import base64, json, sys
d = json.loads(sys.argv[1])
d = d.get("data", d)
url = d.get("qrCode") or d.get("qr") or ""
if not url.startswith("data:image"):
    sys.exit(f"No QR available (already linked?): {json.dumps(d)[:300]}")
open("build/whatsapp-qr.png", "wb").write(base64.b64decode(url.split(",", 1)[1]))
print("Saved build/whatsapp-qr.png: WhatsApp > Settings > Linked devices > Link a device")
PY
    # WSL: print the Windows path to open (launching explorer.exe fails when WSL interop is off)
    command -v wslpath >/dev/null && echo "Open in Windows: $(wslpath -w build/whatsapp-qr.png)" || true
    ;;
  status)
    SID="$(session_id)"
    remote "$PRELUDE; api \$B/sessions/$SID; echo; curl -s -o /dev/null -w 'public TLS endpoint: %{http_code}\n' https://\$(curl -s ifconfig.me | tr . -).sslip.io/api/health"
    ;;
  restart)
    # Recreate (not just restart) the container: a restart keeps Chromium's cached WhatsApp Web page, which
    # is what breaks when WhatsApp ships a build OpenWA can't drive. The login lives on the /app/data volume.
    # Same settings as openwa/user_data.sh.tftpl. The image is checked before anything is removed.
    remote "$RECREATE"
    ;;
  send)
    # Same path the app uses: invoke the whatsapp Lambda's "send" action, which calls the gateway.
    TO="${2:?usage: $0 send <phone, e.g. 0821234567> [message]}"
    MSG="${3:-✅ MzansiRide test: WhatsApp is working.}"
    FN="$($TF output -raw whatsapp_log_group)"; FN="${FN##*/}"
    DIGITS="$(echo "$TO" | tr -cd '0-9')"; [[ "$DIGITS" == 0* && ${#DIGITS} -eq 10 ]] && DIGITS="27${DIGITS:1}"
    PAYLOAD="$(python3 -c 'import json,sys; print(json.dumps({"action": "send", "chat_id": sys.argv[1] + "@c.us", "text": sys.argv[2]}))' "$DIGITS" "$MSG")"
    OUT="$(mktemp)"
    aws lambda invoke --region "$REGION" --function-name "$FN" --cli-binary-format raw-in-base64-out \
      --cli-read-timeout 90 --payload "$PAYLOAD" "$OUT" >/dev/null
    if grep -q '"ok": true' "$OUT"; then echo "Sent to +${DIGITS:0:4}•••${DIGITS: -3}"; rm -f "$OUT";
    else echo "Send failed: $(head -c 300 "$OUT")"; echo "Try: make wa-restart, then send again."; rm -f "$OUT"; exit 1; fi
    ;;
  dashboard)
    command -v session-manager-plugin >/dev/null || { echo "Install the AWS session-manager-plugin first" >&2; exit 1; }
    echo "OpenWA dashboard: http://localhost:2785/dashboard  (API key: aws ssm get-parameter --name ${PREFIX}api_key --with-decryption)"
    echo "Ctrl+C to close the tunnel."
    aws ssm start-session --region "$REGION" --target "$INSTANCE" --document-name AWS-StartPortForwardingSession \
      --parameters portNumber=2785,localPortNumber=2785
    ;;
  logs)
    remote "docker logs --tail 80 openwa 2>&1; docker logs --tail 20 caddy 2>&1"
    ;;
  *) echo "usage: $0 setup|qr|status|logs|restart|send|dashboard"; exit 2 ;;
esac
