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

    status = {"event": "session.status", "data": {"status": "ready"}}
    assert handler.handler(_webhook(status), Ctx())["statusCode"] == 200  # acknowledged, not processed
    assert len(invoked) == 1

    own = {**msg, "idempotencyKey": "k2", "data": {**msg["data"], "fromMe": True}}
    handler.handler(_webhook(own), Ctx())
    assert len(invoked) == 1

    sent = []
    monkeypatch.setattr(openwa, "send_text", lambda chat, text: sent.append((chat, text)))
    handler.handler(invoked[0], Ctx())
    assert sent and "MzansiRide" in sent[0][1]


def test_notify_any_number_with_send_limits(aws, monkeypatch):
    from core import notify
    trip = {"trip_id": "MZTEST", "passenger_name": "Thandi", "driver": {}, "trusted_contact": {"name": "Mom", "phone": "082 555 0101"}}
    assert notify.notify_trusted_contact(trip, None, "passenger_sos")["status"] == "simulated"  # WhatsApp not connected
    monkeypatch.setenv("WHATSAPP_FUNCTION", "wa-fn")
    monkeypatch.setattr(notify, "send_whatsapp", lambda chat, text: f"queued:{chat}")
    r = notify.notify_trusted_contact(trip, None, "passenger_sos")  # any valid number, no allow-list
    assert r["status"] == "queued:27825550101@c.us"
    assert notify.msisdn("+27 (82) 555-0101") == "27825550101"
    monkeypatch.setattr(notify, "PER_NUMBER_PER_HOUR", 3)
    statuses = [notify.notify_trusted_contact(trip, None, "passenger_sos")["status"] for _ in range(3)]
    assert statuses[-1] == "rate_limited" and statuses[0].startswith("queued")


def test_lid_chats_map_back_to_the_phone_chat(aws, monkeypatch):
    """Check-ins go to <phone>@c.us; replies may arrive from the WhatsApp privacy id <lid>@lid."""
    from whatsapp import handler
    monkeypatch.setattr(openwa, "_params", {"webhook_secret": "s3cret-s3cret-123"})
    monkeypatch.setattr(openwa, "send_text", lambda chat, text: {"messageId": "true_93926740500592@lid_3EB0AB"})
    invoked = []

    class FakeLambda:
        def invoke(self, **kw):
            invoked.append(json.loads(kw["Payload"]))

    monkeypatch.setattr(handler.boto3, "client", lambda name: FakeLambda())
    msg = {"event": "message.received", "idempotencyKey": "lid1",
           "data": {"chatId": "93926740500592@lid", "body": "1", "type": "text", "fromMe": False}}

    handler.handler(_webhook(msg), Ctx())
    assert invoked[-1]["chat_id"] == "93926740500592@lid"  # unknown yet

    handler.handler({"action": "send", "chat_id": "27724326766@c.us", "text": "check-in"}, Ctx())
    handler.handler(_webhook({**msg, "idempotencyKey": "lid2"}), Ctx())
    assert invoked[-1]["chat_id"] == "27724326766@c.us"  # learned from the send

    with_phone = {**msg, "idempotencyKey": "lid3", "data": {**msg["data"], "chatId": "111@lid", "senderPhone": "+27 82 123 4567"}}
    handler.handler(_webhook(with_phone), Ctx())
    assert invoked[-1]["chat_id"] == "27821234567@c.us"
