# OpenWA (self-hosted WhatsApp gateway, github.com/rmyndharis/OpenWA) on one small EC2 instance.
#   - OpenWA listens on 127.0.0.1:2785 only. Caddy terminates TLS (Let's Encrypt, <ip>.sslip.io) and
#     exposes ONLY the send-text endpoint + health. The dashboard and admin API are never public:
#     admin is done through SSM (scripts/openwa.sh), so no SSH key or port 22.
#   - Session data (the linked WhatsApp login) lives on the instance volume: re-creating the instance
#     means scanning the QR code again.
locals {
  wa_count = var.enable_whatsapp ? 1 : 0
  wa_host  = var.enable_whatsapp ? "${replace(aws_eip.openwa[0].public_ip, ".", "-")}.sslip.io" : ""
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "openwa" {
  count       = local.wa_count
  name        = "${var.name}-openwa"
  description = "HTTPS for the OpenWA send endpoint (Caddy); HTTP only for ACME + redirect"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP for the Lets Encrypt challenge, redirects to HTTPS"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "openwa" {
  count              = local.wa_count
  name               = "${var.name}-openwa-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "openwa_ssm" {
  count      = local.wa_count
  role       = aws_iam_role.openwa[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# The instance publishes OpenWA's generated admin API key to SSM so the Lambda can read it.
data "aws_iam_policy_document" "openwa" {
  statement {
    actions   = ["ssm:PutParameter", "ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter${local.openwa_prefix}*"]
  }
}

resource "aws_iam_role_policy" "openwa" {
  count  = local.wa_count
  role   = aws_iam_role.openwa[0].id
  policy = data.aws_iam_policy_document.openwa.json
}

resource "aws_iam_instance_profile" "openwa" {
  count = local.wa_count
  name  = "${var.name}-openwa"
  role  = aws_iam_role.openwa[0].name
}

resource "aws_eip" "openwa" {
  count  = local.wa_count
  domain = "vpc"
  tags   = { Name = "${var.name}-openwa" }
}

resource "aws_instance" "openwa" {
  count                       = local.wa_count
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.openwa_instance_type
  iam_instance_profile        = aws_iam_instance_profile.openwa[0].name
  vpc_security_group_ids      = [aws_security_group.openwa[0].id]
  associate_public_ip_address = true

  metadata_options {
    http_tokens = "required" # IMDSv2 only
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  user_data_replace_on_change = false
  user_data = templatefile("${path.module}/../openwa/user_data.sh.tftpl", {
    image        = var.openwa_image
    domain       = local.wa_host
    region       = var.region
    param_prefix = local.openwa_prefix
  })

  tags = { Name = "${var.name}-openwa" }

  lifecycle {
    ignore_changes = [ami] # don't replace (and lose the WhatsApp login) when a newer AMI is published
  }
}

resource "aws_eip_association" "openwa" {
  count         = local.wa_count
  instance_id   = aws_instance.openwa[0].id
  allocation_id = aws_eip.openwa[0].id
}

resource "aws_ssm_parameter" "openwa_base_url" {
  count = local.wa_count
  name  = "${local.openwa_prefix}base_url"
  type  = "String"
  value = "https://${local.wa_host}"
}

resource "aws_ssm_parameter" "openwa_webhook_secret" {
  count = local.wa_count
  name  = "${local.openwa_prefix}webhook_secret"
  type  = "SecureString"
  value = random_password.webhook_secret.result
}
