data "aws_caller_identity" "current" {}

resource "random_id" "suffix" {
  byte_length = 3
}

resource "random_password" "team_code" {
  length  = 10
  special = false
}

resource "random_password" "webhook_secret" {
  length  = 40
  special = false
}

locals {
  suffix        = random_id.suffix.hex
  account_id    = data.aws_caller_identity.current.account_id
  api_name      = "${var.name}-api"
  wa_name       = "${var.name}-whatsapp"
  api_fn_arn    = "arn:aws:lambda:${var.region}:${local.account_id}:function:${local.api_name}"
  wa_fn_arn     = "arn:aws:lambda:${var.region}:${local.account_id}:function:${local.wa_name}"
  team_code     = var.team_code != "" ? var.team_code : random_password.team_code.result
  openwa_prefix = "/${var.name}/openwa/"
  dashboard_url = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards/dashboard/${var.name}"
}
