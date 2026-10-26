resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = var.name

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 8, height = 6
        properties = {
          title  = "Lambda invocations / errors"
          region = var.region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", local.api_name, { label = "api" }],
            [".", "Errors", ".", ".", { label = "api errors" }],
            [".", "Invocations", ".", local.wa_name, { label = "whatsapp" }],
            [".", "Errors", ".", ".", { label = "whatsapp errors" }],
          ]
        }
      },
      {
        type = "metric", x = 8, y = 0, width = 8, height = 6
        properties = {
          title  = "API Gateway requests / 4xx / 5xx"
          region = var.region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", aws_apigatewayv2_api.main.id],
            [".", "4xx", ".", "."],
            [".", "5xx", ".", "."],
          ]
        }
      },
      {
        type = "log", x = 16, y = 0, width = 8, height = 6
        properties = {
          title  = "Bedrock latency and tokens"
          region = var.region
          query  = "SOURCE '${aws_cloudwatch_log_group.api.name}' | SOURCE '${aws_cloudwatch_log_group.whatsapp.name}' | filter event = 'bedrock' | stats count(*) as calls, avg(ms) as avg_ms, max(ms) as max_ms, sum(in_tokens) as in_tok, sum(out_tokens) as out_tok by channel"
          view   = "table"
        }
      },
      {
        type = "log", x = 0, y = 6, width = 12, height = 8
        properties = {
          title  = "Safety events, check-ins and escalations"
          region = var.region
          query  = "SOURCE '${aws_cloudwatch_log_group.api.name}' | SOURCE '${aws_cloudwatch_log_group.whatsapp.name}' | filter event in ['safety_event', 'checkin', 'event_escalated', 'contact_notified', 'sos'] | fields @timestamp, event, trip, type, response, reason, channel, status, prompt_ms | sort @timestamp desc | limit 50"
          view   = "table"
        }
      },
      {
        type = "log", x = 12, y = 6, width = 12, height = 8
        properties = {
          title  = "WhatsApp traffic"
          region = var.region
          query  = "SOURCE '${aws_cloudwatch_log_group.whatsapp.name}' | filter event like /whatsapp|webhook|driver_lookup|assistant_reply/ | fields @timestamp, event, chat, verdict, source, ms, error | sort @timestamp desc | limit 50"
          view   = "table"
        }
      },
      {
        type = "log", x = 0, y = 14, width = 24, height = 6
        properties = {
          title  = "Warnings and errors"
          region = var.region
          query  = "SOURCE '${aws_cloudwatch_log_group.api.name}' | SOURCE '${aws_cloudwatch_log_group.whatsapp.name}' | filter level in ['WARN', 'ERROR'] or @message like /(?i)(task timed out|exception)/ | fields @timestamp, @log, event, path, error, @message | sort @timestamp desc | limit 50"
          view   = "table"
        }
      },
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "errors" {
  for_each            = toset([local.api_name, local.wa_name])
  alarm_name          = "${each.key}-errors"
  alarm_description   = "${each.key} Lambda threw unhandled errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = each.key }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
}

# ---------- scheduled health check (every 5 min) -> custom metrics -> email alarms ----------
resource "aws_cloudwatch_event_rule" "health_check" {
  name                = "${var.name}-health-check"
  description         = "Runs the system health check (WhatsApp, AI, SMS) and publishes MzansiRide/Health metrics"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "health_check" {
  rule  = aws_cloudwatch_event_rule.health_check.name
  arn   = aws_lambda_function.api.arn
  input = jsonencode({ action = "health_check" })
}

resource "aws_lambda_permission" "health_check" {
  statement_id  = "AllowHealthCheckSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.health_check.arn
}

locals {
  health_alarms = {
    whatsapp = { metric = "WhatsAppHealthy", periods = 2, missing = "notBreaching", text = "WhatsApp gateway is down or every send is failing. Fix: make wa-restart (README: WhatsApp: when messages stop arriving)." }
    ai       = { metric = "AIHealthy", periods = 3, missing = "notBreaching", text = "Most Bedrock calls are falling back to rules-only text. Check Bedrock model access and quotas." }
    sms      = { metric = "SmsHealthy", periods = 1, missing = "notBreaching", text = "SMS to trusted contacts is failing (SNS sandbox, spend limit or destination). Check make sms-verify." }
    check    = { metric = "HealthCheckRan", periods = 2, missing = "breaching", text = "The 5-minute health check isn't running, so problems may go unnoticed. Check the api Lambda." }
  }
}

resource "aws_cloudwatch_metric_alarm" "health" {
  for_each            = local.health_alarms
  alarm_name          = "${var.name}-health-${each.key}"
  alarm_description   = each.value.text
  namespace           = "MzansiRide/Health"
  metric_name         = each.value.metric
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = each.value.periods
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = each.value.missing
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "gateway_instance" {
  count               = var.enable_whatsapp ? 1 : 0
  alarm_name          = "${var.name}-openwa-instance"
  alarm_description   = "The WhatsApp gateway server failed its EC2 status checks."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  dimensions          = { InstanceId = aws_instance.openwa[0].id }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name}-api-5xx"
  alarm_description   = "The API is returning server errors (5xx) to users."
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = aws_apigatewayv2_api.main.id, Stage = "$default" }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
}

resource "aws_budgets_budget" "monthly" {
  count        = var.budget_email != "" ? 1 : 0
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}
