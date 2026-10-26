variable "region" {
  description = "AWS region. eu-west-1 has Amazon Bedrock (Claude via EU cross-region inference); af-south-1 does not."
  type        = string
  default     = "eu-west-1"
}

variable "name" {
  description = "Prefix for every resource name."
  type        = string
  default     = "mzansiride"
}

variable "model_id" {
  description = "Bedrock model or inference profile id used by the safety assistant."
  type        = string
  default     = "eu.anthropic.claude-haiku-5-5"
}

variable "model_fallback_id" {
  description = "Model tried when the primary model is refused (e.g. Anthropic access not granted yet)."
  type        = string
  default     = "eu.amazon.nova-lite-v1:0"
}

variable "enable_guardrail" {
  description = "Create a Bedrock Guardrail and apply it to every assistant call."
  type        = bool
  default     = true
}

variable "enable_whatsapp" {
  description = "Run the OpenWA WhatsApp gateway on a small EC2 instance."
  type        = bool
  default     = true
}

variable "openwa_image" {
  description = "OpenWA container image (github.com/rmyndharis/OpenWA)."
  type        = string
  default     = "rmyndharis/openwa:0.25.0"
}

variable "openwa_instance_type" {
  description = "whatsapp-web.js runs headless Chromium, so 2 GB RAM is the practical minimum."
  type        = string
  default     = "t3.small"
}

variable "wa_number" {
  description = "Display number of the WhatsApp account linked to OpenWA, e.g. +27 82 000 0000 (shown in the web app)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "team_code" {
  description = "Code for the operator dashboard. Leave empty to generate one (terraform output -raw team_code)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "budget_email" {
  description = "Email for the monthly AWS budget alert. Leave empty to skip creating the budget."
  type        = string
  default     = ""
}

variable "budget_usd" {
  type    = number
  default = 20
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "enable_sms" {
  description = "Send the trusted contact an SMS (Amazon SNS) when the passenger sends SOS or asks for help."
  type        = bool
  default     = true
}

variable "admin_emails" {
  description = "Team emails that get system-down alerts (and, with Cognito, operator sign-in). Private: tfvars or the ADMIN_EMAILS secret."
  type        = list(string)
  default     = []
  sensitive   = true
}
