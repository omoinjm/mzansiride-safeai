# Both functions ship the same zip of src/ (core + api + whatsapp packages). No third-party
# dependencies: boto3 comes with the Lambda runtime, HTTP calls to OpenWA use urllib.
data "archive_file" "src" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/../build/src.zip"
  excludes    = ["**/__pycache__/**", "**/*.pyc"]
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.api_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "whatsapp" {
  name              = "/aws/lambda/${local.wa_name}"
  retention_in_days = var.log_retention_days
}

locals {
  common_env = {
    TRIPS_TABLE       = aws_dynamodb_table.trips.name
    EVENTS_TABLE      = aws_dynamodb_table.events.name
    DRIVERS_TABLE     = aws_dynamodb_table.drivers.name
    WHATSAPP_TABLE    = aws_dynamodb_table.whatsapp.name
    MODEL_ID          = var.model_id
    MODEL_FALLBACK_ID = var.model_fallback_id
    GUARDRAIL_ID      = var.enable_guardrail ? aws_bedrock_guardrail.safety[0].guardrail_id : ""
    GUARDRAIL_VERSION = var.enable_guardrail ? aws_bedrock_guardrail_version.safety[0].version : ""
    WHATSAPP_FUNCTION = var.enable_whatsapp ? local.wa_name : ""
    WA_NUMBER         = var.wa_number
    OPENWA_HEALTH_URL = var.enable_whatsapp ? "https://${local.wa_host}/api/health" : ""
    DASHBOARD_URL     = local.dashboard_url
    SMS_ENABLED       = tostring(var.enable_sms)
    OPS_TOPIC_ARN     = aws_sns_topic.ops_alerts.arn
  }
}

resource "aws_lambda_function" "api" {
  function_name    = local.api_name
  description      = "MzansiRide SafeAI web API: trips, safety rules, check-ins, Bedrock assistant"
  role             = aws_iam_role.api.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "api.handler.handler"
  filename         = data.archive_file.src.output_path
  source_code_hash = data.archive_file.src.output_base64sha256
  memory_size      = 512
  timeout          = 30

  environment {
    variables = merge(local.common_env, {
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.operators.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.fleet.id
    })
  }

  depends_on = [aws_cloudwatch_log_group.api, aws_iam_role_policy.api]
}

resource "aws_lambda_function" "whatsapp" {
  function_name    = local.wa_name
  description      = "MzansiRide SafeAI WhatsApp channel: OpenWA webhook + replies"
  role             = aws_iam_role.whatsapp.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "whatsapp.handler.handler"
  filename         = data.archive_file.src.output_path
  source_code_hash = data.archive_file.src.output_base64sha256
  memory_size      = 512
  timeout          = 60

  environment {
    variables = merge(local.common_env, { OPENWA_PARAM_PREFIX = local.openwa_prefix })
  }

  depends_on = [aws_cloudwatch_log_group.whatsapp, aws_iam_role_policy.whatsapp]
}

# Async invocations (self-invoke and API -> WhatsApp) must not retry forever or duplicate replies.
resource "aws_lambda_function_event_invoke_config" "whatsapp" {
  function_name                = aws_lambda_function.whatsapp.function_name
  maximum_retry_attempts       = 0
  maximum_event_age_in_seconds = 300
}
