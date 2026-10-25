import os
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.update({
    "AWS_REGION": "eu-west-1", "AWS_DEFAULT_REGION": "eu-west-1",
    "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
    "TRIPS_TABLE": "t-trips", "EVENTS_TABLE": "t-events", "DRIVERS_TABLE": "t-drivers", "WHATSAPP_TABLE": "t-wa",
    "TEAM_CODE": "secret-code",
})


@pytest.fixture
def aws(monkeypatch):
    """Moto DynamoDB with the same tables as infra/dynamodb.tf, and Bedrock stubbed out."""
    with mock_aws():
        ddb = boto3.client("dynamodb", region_name="eu-west-1")
        def mk(name, pk, sk=None):
            keys = [{"AttributeName": pk, "KeyType": "HASH"}] + ([{"AttributeName": sk, "KeyType": "RANGE"}] if sk else [])
            attrs = [{"AttributeName": pk, "AttributeType": "S"}] + ([{"AttributeName": sk, "AttributeType": "S"}] if sk else [])
            ddb.create_table(TableName=name, KeySchema=keys, AttributeDefinitions=attrs, BillingMode="PAY_PER_REQUEST")
        mk("t-trips", "trip_id"); mk("t-events", "trip_id", "event_id"); mk("t-drivers", "driver_id"); mk("t-wa", "pk")

        from core import assistant, drivers, notify, store
        store._ddb = None
        drivers._cache = None
        for d in drivers.SEED:
            store.put("drivers", d)

        calls = []
        def fake_converse(messages, channel, **kw):
            calls.append({"messages": messages, "channel": channel})
            return {"text": f"AI says ({channel})", "source": "bedrock", "model": "test-model"}
        monkeypatch.setattr(assistant, "_converse", fake_converse)
        monkeypatch.delenv("WHATSAPP_FUNCTION", raising=False)
        monkeypatch.delenv("WA_ALLOWLIST", raising=False)
        yield {"bedrock_calls": calls}
        store._ddb = None
