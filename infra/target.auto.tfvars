# The active AWS target's region and Bedrock models. Written by scripts/switch_account.sh; committed so
# local deploys and CI agree. (Phone numbers and other private values go in terraform.tfvars, git-ignored.)
region            = "eu-west-1"
model_id          = "eu.anthropic.claude-haiku-5-5"
model_fallback_id = "eu.amazon.nova-lite-v1:0"
# SMS stays simulated until AWS End User Messaging SMS is enabled for this account (then: true, and
# make sms-verify NUMBER=... while the account is in the SMS sandbox).
enable_sms = false
