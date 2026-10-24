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
  default     = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
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
}

variable "wa_allowlist" {
  description = "Phone numbers that may receive unsolicited WhatsApp messages (trusted-contact alerts). Demo team only."
  type        = list(string)
  default     = []
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
