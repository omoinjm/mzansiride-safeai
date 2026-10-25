# On-demand tables: no capacity planning, pennies at demo scale. Items expire via TTL (attribute "ttl").
resource "aws_dynamodb_table" "trips" {
  name         = "${var.name}-trips"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "trip_id"

  attribute {
    name = "trip_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

resource "aws_dynamodb_table" "events" {
  name         = "${var.name}-events"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "trip_id"
  range_key    = "event_id"

  attribute {
    name = "trip_id"
    type = "S"
  }

  attribute {
    name = "event_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

resource "aws_dynamodb_table" "drivers" {
  name         = "${var.name}-drivers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "driver_id"

  attribute {
    name = "driver_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "whatsapp" {
  name         = "${var.name}-whatsapp"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

# Demo driver registry, seeded from the same JSON the code falls back to.
locals {
  drivers = jsondecode(file("${path.module}/../src/core/drivers.json")).drivers
}

resource "aws_dynamodb_table_item" "driver" {
  for_each   = { for d in local.drivers : d.driver_id => d }
  table_name = aws_dynamodb_table.drivers.name
  hash_key   = aws_dynamodb_table.drivers.hash_key

  item = jsonencode({
    # jsondecode() of a string on both branches avoids "inconsistent conditional result types"
    for k, v in each.value : k => jsondecode(contains(["rating", "trips_completed", "reports_open", "safety_score"], k) ? jsonencode({ N = tostring(v) }) : jsonencode({ S = tostring(v) }))
  })
}
