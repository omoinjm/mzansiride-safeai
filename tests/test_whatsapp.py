import base64
import hashlib
import hmac
import json

from whatsapp import openwa


def test_signature_roundtrip():
    body = b'{"event":"message.received"}'
    sig = "sha256=" + hmac.new(b"s3cret-s3cret-123", body, hashlib.sha256).hexdigest()
    assert openwa.verify_signature(body, sig, "s3cret-s3cret-123")
    assert not openwa.verify_signature(body, sig, "other-secret-12345")
    assert not openwa.verify_signature(body, "", "s3cret-s3cret-123")


def _webhook(aws_payload, secret="s3cret-s3cret-123", sign=True):
    raw = json.dumps(aws_payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest() if sign else "sha256=bad"
    return {"body": base64.b64encode(raw).decode(), "isBase64Encoded": True, "headers": {"X-OpenWA-Signature": sig}}


class Ctx:
    function_name = "wa-fn"


def test_webhook_flow(aws, monkeypatch):
    from whatsapp import handler
    monkeypatch.setattr(openwa, "_params", {"webhook_secret": "s3cret-s3cret-123"})
    invoked = []

    class FakeLambda:
        def invoke(self, **kw):
            invoked.append(json.loads(kw["Payload"]))

    monkeypatch.setattr(handler.boto3, "client", lambda name: FakeLambda())
    msg = {"event": "message.received", "idempotencyKey": "k1",
           "data": {"chatId": "27821234567@c.us", "body": "hi", "type": "text", "fromMe": False, "kind": "individual"}}

    assert handler.handler(_webhook(msg, sign=False), Ctx())["statusCode"] == 401
    assert handler.handler(_webhook(msg), Ctx())["statusCode"] == 200
    assert handler.handler(_webhook(msg), Ctx())["statusCode"] == 200  # retry: deduplicated
    assert invoked == [{"action": "process", "chat_id": "27821234567@c.us", "text": "hi"}]

    own = {**msg, "idempotencyKey": "k2", "data": {**msg["data"], "fromMe": True}}
    handler.handler(_webhook(own), Ctx())
    assert len(invoked) == 1

    sent = []
    monkeypatch.setattr(openwa, "send_text", lambda chat, text: sent.append((chat, text)))
    handler.handler(invoked[0], Ctx())
    assert sent and "MzansiRide" in sent[0][1]


def test_notify_allowlist(aws, monkeypatch):
    from core import notify
    trip = {"trip_id": "MZTEST", "passenger_name": "Thandi", "driver": {}, "trusted_contact": {"name": "Mom", "phone": "082 555 0101"}}
    assert notify.notify_trusted_contact(trip, None, "passenger_sos")["status"] == "simulated"
    monkeypatch.setenv("WHATSAPP_FUNCTION", "wa-fn")
    monkeypatch.setenv("WA_ALLOWLIST", "+27 82 555 0101")
    monkeypatch.setattr(notify, "send_whatsapp", lambda chat, text: f"queued:{chat}")
    r = notify.notify_trusted_contact(trip, None, "passenger_sos")
    assert r["status"] == "queued:27825550101@c.us"
    assert notify.msisdn("+27 (82) 555-0101") == "27825550101"
