#!/usr/bin/env bash
# Amazon SNS SMS sandbox helper. New AWS accounts can only text VERIFIED numbers until SMS production
# access is granted (Amazon SNS console > Text messaging (SMS) > Exit SMS sandbox).
#   ./scripts/sms_verify.sh status            # sandbox on/off + verified numbers + spend limit
#   ./scripts/sms_verify.sh 0821234567        # send a one-time code to that phone, then type it in
set -euo pipefail
cd "$(dirname "$0")/.."
REGION="${REGION:-$(sed -n 's/^region *= *"\(.*\)"/\1/p' infra/backend.hcl)}"

if [ "${1:-status}" = "status" ]; then
  echo "SMS sandbox: $(aws sns get-sms-sandbox-account-status --region "$REGION" --query IsInSandbox --output text)"
  aws sns list-sms-sandbox-phone-numbers --region "$REGION" \
    --query 'PhoneNumbers[].[PhoneNumber,Status]' --output text | sed -E 's/(\+[0-9]{4})[0-9]+([0-9]{3})/\1•••\2/'
  echo "Monthly SMS spend limit (USD): $(aws sns get-sms-attributes --region "$REGION" --attributes MonthlySpendLimit --query 'attributes.MonthlySpendLimit' --output text)"
  exit 0
fi

DIGITS="$(echo "$1" | tr -cd '0-9')"; [[ "$DIGITS" == 0* && ${#DIGITS} -eq 10 ]] && DIGITS="27${DIGITS:1}"
PHONE="+$DIGITS"
aws sns create-sms-sandbox-phone-number --region "$REGION" --phone-number "$PHONE" --language-code en-US
read -r -p "Code sent by SMS to ${PHONE:0:5}•••${PHONE: -3}. Enter it: " CODE
aws sns verify-sms-sandbox-phone-number --region "$REGION" --phone-number "$PHONE" --one-time-password "$CODE"
echo "Verified. This number can now receive MzansiRide SMS alerts."
