# Bedrock Guardrail on every assistant call (input + output).
# The violence filter is deliberately OFF for user input: a passenger describing a threat
# ("he has a knife") must get help, not a block. Output is still filtered.
resource "aws_bedrock_guardrail" "safety" {
  count                     = var.enable_guardrail ? 1 : 0
  name                      = "${var.name}-safety"
  description               = "MzansiRide SafeAI assistant guardrail"
  blocked_input_messaging   = "I can only help with trip safety. If you are in danger, call 10111 or 112."
  blocked_outputs_messaging = "I can't answer that. If you are in danger, call 10111 or 112, or tap \"I need help\"."

  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "LOW"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "MEDIUM"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "NONE"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "LOW"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "Criminal-profiling"
      type       = "DENY"
      definition = "Judging whether a specific person is a criminal or dangerous based on their appearance, race, nationality, accent, gender or other personal characteristics."
      examples   = ["Is my driver a criminal because he is foreign?", "Do drivers from that area kidnap people?"]
    }
  }
}

resource "aws_bedrock_guardrail_version" "safety" {
  count         = var.enable_guardrail ? 1 : 0
  guardrail_arn = aws_bedrock_guardrail.safety[0].guardrail_arn
  description   = "managed by terraform"

  lifecycle {
    replace_triggered_by = [aws_bedrock_guardrail.safety[0]]
  }
}
