# The active AWS target's region and Bedrock models. Written by scripts/switch_account.sh; committed so
# local deploys and CI agree. (Phone numbers and other private values go in terraform.tfvars, git-ignored.)
region            = "eu-west-1"
model_id          = "eu.anthropic.claude-haiku-5-5"
model_fallback_id = "eu.amazon.nova-lite-v1:0"
