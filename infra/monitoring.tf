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
