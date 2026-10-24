output "web_url" {
  description = "Live app (CloudFront)."
  value       = "https://${aws_cloudfront_distribution.web.domain_name}"
}

output "api_url" {
  value = aws_apigatewayv2_api.main.api_endpoint
}

output "webhook_url" {
  description = "Register this in OpenWA (scripts/openwa.sh setup does it)."
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/whatsapp/webhook"
}

output "team_code" {
  description = "Code for the operator dashboard."
  value       = local.team_code
  sensitive   = true
}

output "web_bucket" {
  value = aws_s3_bucket.web.id
}

output "distribution_id" {
  value = aws_cloudfront_distribution.web.id
}

output "openwa_instance_id" {
  value = var.enable_whatsapp ? aws_instance.openwa[0].id : ""
}

output "openwa_base_url" {
  value = var.enable_whatsapp ? "https://${local.wa_host}" : ""
}

output "openwa_param_prefix" {
  value = local.openwa_prefix
}

output "api_log_group" {
  value = aws_cloudwatch_log_group.api.name
}

output "whatsapp_log_group" {
  value = aws_cloudwatch_log_group.whatsapp.name
}

output "dashboard_url" {
  value = local.dashboard_url
}
