"""The operator's WhatsApp on/off switch: when off, nothing WhatsApp-related works."""
import json

from core import notify, trips
from test_trips_api import book, call, stop_for
from test_whatsapp import Ctx, _webhook

CODE = {"x-team-code": "secret-code"}


def pause(on=False):
    status, cfg = call("PUT", "/api/ops/config", {"whatsapp_enabled": on}, headers=CODE)
    assert status == 200 and cfg["whatsapp_enabled"] is on


def test_switch_is_an_operator_setting(aws):
    assert call("PUT", "/api/ops/config", {"whatsapp_enabled": False})[0] == 401
    assert call("PUT", "/api/ops/config", {"whatsapp_enabled": "no"}, headers=CODE)[0] == 400
    pause(False)
    cfg = call("GET", "/api/config")[1]
    assert cfg["whatsapp"]["paused"] is True and cfg["whatsapp"]["enabled"] is False
    assert call("GET", "/api/ops/config", headers=CODE)[1]["checkin_timeout_s"] == trips.CHECKIN_TIMEOUT_S  # untouched
    pause(True)
    assert call("GET", "/api/config")[1]["whatsapp"]["paused"] is False


def test_paused_blocks_booking_link_prompts_contact_alerts_and_simulator(aws, monkeypatch):
    monkeypatch.setenv("WHATSAPP_FUNCTION", "wa-fn")
    pause(False)
    trip = book(safe_mode=True, passenger_phone="082 555 0199", wa_session="p1")
    assert not trip["whatsapp_linked"] and trip["whatsapp_channel"] == "paused"
    stop_for(trip["trip_id"], 200 + 135)  # check-in, no answer, escalation
    ev = trips.list_events(trip["trip_id"])[0]
    assert ev["status"] == "escalated"  # the safety flow itself still works in the app
    assert ev["notifications"][0]["status"] == "paused"
    assert call("POST", "/api/whatsapp/simulate", {"session": "p1", "text": "hi"})[0] == 409
    assert call("GET", "/api/whatsapp/outbox", qs={"session": "p1"})[0] == 409
    assert notify.send_whatsapp("sim:p1", "x") == "paused"
    assert call("GET", "/api/ops/health", headers=CODE)[1]["whatsapp"]["status"] == "paused"


def test_paused_webhook_gets_one_reply_per_hour(aws, monkeypatch):
    from whatsapp import handler, openwa
    monkeypatch.setattr(openwa, "_params", {"webhook_secret": "s3cret-s3cret-123"})
    sent = []
    monkeypatch.setattr(openwa, "send_text", lambda chat, text: sent.append((chat, text)) or {})
    invoked = []

    class FakeLambda:
        def invoke(self, **kw):
            invoked.append(json.loads(kw["Payload"]))
    monkeypatch.setattr(handler.boto3, "client", lambda name: FakeLambda())
    pause(False)
    for i in range(3):
        msg = {"event": "message.received", "idempotencyKey": f"p{i}",
               "data": {"chatId": "27821234567@c.us", "body": "check CA 123-456", "type": "text", "fromMe": False}}
        handler.handler(_webhook(msg), Ctx())
        handler.handler(invoked[-1], Ctx())  # the async "process" step
    assert len(sent) == 1 and "paused" in sent[0][1] and "10111" in sent[0][1]
    pause(True)
    handler.handler(invoked[-1], Ctx())
    assert len(sent) == 2 and "Registered driver" in sent[1][1]  # back to normal
