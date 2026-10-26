# Amazon SNS: SMS to the trusted contact (one message per SOS / "I need help"), and the ops alert topic
# (email to the team when something is down, see monitoring.tf).

resource "aws_sns_sms_preferences" "sms" {
  count             = var.enable_sms ? 1 : 0
  default_sms_type  = "Transactional" # time-critical: delivered ahead of promotional traffic
  default_sender_id = "MzansiRide"    # shown where the destination country supports alphanumeric sender IDs
}
