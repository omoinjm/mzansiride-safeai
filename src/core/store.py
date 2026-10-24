"""DynamoDB access. Table names come from env (set by Terraform).

trips      pk trip_id                    one item per simulated trip (incl. rules state, last position)
events     pk trip_id, sk event_id       safety events + check-in responses + notifications
drivers    pk driver_id                  demo driver/vehicle registry (seeded by Terraform)
whatsapp   pk pk                         chat#<id> links, dedupe#<key> (TTL), outbox#<sim chat>
"""
import json
import os
import time
from decimal import Decimal

_ddb = None


def _resource():
    global _ddb
    if _ddb is None:
        import boto3

        _ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-west-1"))
    return _ddb


def table(kind):
    return _resource().Table(os.environ[f"{kind.upper()}_TABLE"])


def to_ddb(obj):
    """Python floats -> Decimal (DynamoDB has no float type)."""
    return json.loads(json.dumps(obj), parse_float=Decimal)


def from_ddb(obj):
    if isinstance(obj, list):
        return [from_ddb(v) for v in obj]
    if isinstance(obj, dict):
        return {k: from_ddb(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    return obj


def ttl_days(days):
    return int(time.time()) + days * 86400


def put(kind, item, **kwargs):
    table(kind).put_item(Item=to_ddb(item), **kwargs)
    return item


def get(kind, key):
    item = table(kind).get_item(Key=key, ConsistentRead=True).get("Item")
    return from_ddb(item) if item else None


def delete(kind, key):
    table(kind).delete_item(Key=key)


def scan(kind, limit=500):
    t = table(kind)
    items, kwargs = [], {}
    while True:
        resp = t.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp or len(items) >= limit:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return from_ddb(items[:limit])


def query_events(trip_id):
    from boto3.dynamodb.conditions import Key

    resp = table("events").query(KeyConditionExpression=Key("trip_id").eq(trip_id), ConsistentRead=True)
    return from_ddb(resp.get("Items", []))


def put_once(kind, item):
    """Insert only if the key does not exist yet. Returns False for a duplicate (webhook retries)."""
    from botocore.exceptions import ClientError

    try:
        table(kind).put_item(Item=to_ddb(item), ConditionExpression="attribute_not_exists(pk)")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
