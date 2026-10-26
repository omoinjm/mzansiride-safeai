# Amazon Cognito: sign-in for operators (Fleet page, WhatsApp switch, ops settings). Passengers don't sign in.
# Users are created here from var.admin_emails; Cognito emails each a temporary password, changed on first sign-in.
resource "aws_cognito_user_pool" "operators" {
  name                     = "${var.name}-operators"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  deletion_protection      = "INACTIVE" # hackathon stack: `make destroy` must work

  admin_create_user_config {
    allow_admin_create_user_only = true # no self sign-up
    invite_message_template {
      email_subject = "MzansiRide Fleet sign-in"
      email_message = "You're an operator on MzansiRide SafeAI. Sign in on the Fleet page with {username} and the temporary password {####} , then choose your own password."
      sms_message   = "MzansiRide Fleet: {username} / {####}"
    }
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_client" "fleet" {
  name                          = "${var.name}-fleet-web"
  user_pool_id                  = aws_cognito_user_pool.operators.id
  generate_secret               = false # browser app: public client
  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
  id_token_validity             = 1
  access_token_validity         = 1
  refresh_token_validity        = 7
  token_validity_units {
    id_token      = "hours"
    access_token  = "hours"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_group" "operators" {
  name         = "operators"
  user_pool_id = aws_cognito_user_pool.operators.id
  description  = "Fleet page, WhatsApp switch and operator settings"
}

resource "aws_cognito_user" "operator" {
  count        = nonsensitive(length(var.admin_emails)) # the addresses stay sensitive in plans and logs
  user_pool_id = aws_cognito_user_pool.operators.id
  username     = var.admin_emails[count.index]
  attributes = {
    email          = var.admin_emails[count.index]
    email_verified = true
  }
  desired_delivery_mediums = ["EMAIL"]
  lifecycle {
    ignore_changes = [attributes] # don't fight Cognito-managed attributes after first sign-in
  }
}

resource "aws_cognito_user_in_group" "operator" {
  count        = nonsensitive(length(var.admin_emails))
  user_pool_id = aws_cognito_user_pool.operators.id
  group_name   = aws_cognito_user_group.operators.name
  username     = aws_cognito_user.operator[count.index].username
}

# API Gateway checks the Cognito ID token on operator routes before the Lambda runs.
resource "aws_apigatewayv2_authorizer" "operators" {
  api_id           = aws_apigatewayv2_api.main.id
  authorizer_type  = "JWT"
  name             = "${var.name}-operators"
  # Not Authorization: CloudFront strips that header from GET requests unless it's part of the cache key.
  identity_sources = ["$request.header.x-operator-token"]
  jwt_configuration {
    issuer   = "https://${aws_cognito_user_pool.operators.endpoint}"
    audience = [aws_cognito_user_pool_client.fleet.id]
  }
}

# More specific than ANY /api/{proxy+}, so these win and require a signed-in operator.
resource "aws_apigatewayv2_route" "operator" {
  for_each           = toset(["GET /api/dashboard", "ANY /api/ops/{proxy+}", "POST /api/trips/{trip}/events/{ev}/ack"])
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.operators.id
}
