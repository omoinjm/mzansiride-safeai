# Amazon SNS: SMS to the trusted contact (one message per SOS / "I need help"), and the ops alert topic
# (email to the team when something is down, see monitoring.tf).

# SMS type (Transactional) and sender ID are set per message in core/notify.send_sms. No account-wide
# aws_sns_sms_preferences: reading them needs an End User Messaging subscription that this account lacks.

# Email alerts for the team: CloudWatch alarms (monitoring.tf) publish here. Each address confirms once.
resource "aws_sns_topic" "ops_alerts" {
  name = "${var.name}-ops-alerts"
}

resource "aws_sns_topic_subscription" "ops_email" {
  count     = nonsensitive(length(var.admin_emails)) # the addresses themselves stay sensitive in plans and logs
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = var.admin_emails[count.index]
}

# Allow CloudWatch alarms to publish to the topic.
data "aws_iam_policy_document" "ops_alerts" {
  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.ops_alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "ops_alerts" {
  arn    = aws_sns_topic.ops_alerts.arn
  policy = data.aws_iam_policy_document.ops_alerts.json
}
