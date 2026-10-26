#!/usr/bin/env bash
# One-time setup: creates the S3 bucket that holds the Terraform state and
# writes infra/backend.hcl. Run once per AWS account, then commit backend.hcl so
# teammates run `make init` and deploy to the same live stack.
set -euo pipefail
cd "$(dirname "$0")/.."

REGION="${REGION:-eu-west-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="mzansiride-tfstate-${ACCOUNT_ID}-${REGION}"

if aws s3api head-bucket --region "$REGION" --bucket "$BUCKET" 2>/dev/null; then
  echo "State bucket $BUCKET already exists"
else
  if [ "$REGION" = "us-east-1" ]; then  # us-east-1 rejects an explicit LocationConstraint
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  fi
  echo "Created $BUCKET"
fi
aws s3api put-bucket-versioning --region "$REGION" --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-public-access-block --region "$REGION" --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --region "$REGION" --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

cat > infra/backend.hcl <<HCL
bucket       = "$BUCKET"
key          = "mzansiride/terraform.tfstate"
region       = "$REGION"
encrypt      = true
use_lockfile = true
HCL
echo "Wrote infra/backend.hcl"
