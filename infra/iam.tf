data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

locals {
  table_arns = [
    aws_dynamodb_table.trips.arn,
    aws_dynamodb_table.events.arn,
    aws_dynamodb_table.drivers.arn,
    aws_dynamodb_table.whatsapp.arn,
  ]
}

# Shared statements: DynamoDB on our four tables only, Bedrock model invoke (EU cross-region
# inference profiles route to several EU regions, hence region "*" for foundation models).
data "aws_iam_policy_document" "common" {
  statement {
    sid       = "Tables"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = local.table_arns
  }

  statement {
    sid     = "InvokeModel"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:${var.region}:${local.account_id}:inference-profile/*",
    ]
  }

  dynamic "statement" {
    for_each = var.enable_guardrail ? [1] : []
    content {
      sid       = "Guardrail"
      actions   = ["bedrock:ApplyGuardrail"]
      resources = [aws_bedrock_guardrail.safety[0].guardrail_arn]
    }
  }

  statement {
    sid       = "QueueWhatsApp"
    actions   = ["lambda:InvokeFunction"]
    resources = [local.wa_fn_arn]
  }
}

resource "aws_iam_role" "api" {
  name               = "${local.api_name}-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "api" {
  source_policy_documents = [data.aws_iam_policy_document.common.json]

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api.arn}:*"]
  }
}

resource "aws_iam_role_policy" "api" {
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

resource "aws_iam_role" "whatsapp" {
  name               = "${local.wa_name}-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "whatsapp" {
  source_policy_documents = [data.aws_iam_policy_document.common.json]

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.whatsapp.arn}:*"]
  }

  # OpenWA base URL, API key, session id and webhook secret (SecureString, AWS-managed key).
  statement {
    sid       = "OpenWASecrets"
    actions   = ["ssm:GetParametersByPath"]
    resources = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter${trimsuffix(local.openwa_prefix, "/")}"]
  }
}

resource "aws_iam_role_policy" "whatsapp" {
  role   = aws_iam_role.whatsapp.id
  policy = data.aws_iam_policy_document.whatsapp.json
}
