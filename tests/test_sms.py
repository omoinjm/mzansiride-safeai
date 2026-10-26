"""SMS to the trusted contact (Amazon SNS): only for SOS and "I need help", one message, never blocking."""
from core import notify
from test_trips_api import book, call

TRIP = {"trip_id": "MZTEST", "passenger_name": "Thandi 😊", "last_position": {"lat": -26.1, "lng": 28.05},
        "driver": {"plate": "ND 456-789", "colour": "Orange", "vehicle": "Renault Kwid"},
        "trusted_contact": {"name": "Mom", "phone": "082 555 0101"}}


def sent_sms(monkeypatch):
    out = []

    class FakeSns:
        def publish(self, **kw):
            out.append(kw)
            return {"MessageId": "1"}
    import boto3
    monkeypatch.setattr(boto3, "client", lambda name, **kw: FakeSns() if name == "sns" else None)
    return out


def test_sms_on_sos_and_help_not_on_missed_checkin(aws, monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "true")
    sms = sent_sms(monkeypatch)
    for reason in ("passenger_sos", "passenger_help"):
        rec = notify.notify_trusted_contact(TRIP, None, reason)
        assert rec["sms"]["status"] == "sent" and "0101" not in rec["sms"]["to"]
    assert "sms" not in notify.notify_trusted_contact(TRIP, None, "no_response")
    assert [m["PhoneNumber"] for m in sms] == ["+27825550101", "+27825550101"]
    text = sms[1]["Message"]
    assert "asked for HELP" in text and "ND 456-789" in text and "10111" in text and "maps.google.com" in text
    assert text.isascii() and len(text) <= 306  # plain GSM text, at most 2 segments


def test_sms_is_simulated_when_disabled_or_number_not_a_mobile(aws, monkeypatch):
    sms = sent_sms(monkeypatch)
    assert notify.notify_trusted_contact(TRIP, None, "passenger_sos")["sms"]["status"] == "simulated"  # SMS_ENABLED unset
    monkeypatch.setenv("SMS_ENABLED", "true")
    demo = {**TRIP, "trusted_contact": {"name": "Demo", "phone": "000 000 0000"}}
    assert notify.notify_trusted_contact(demo, None, "passenger_sos")["sms"]["status"] == "simulated"
    assert sms == []


def test_sms_failure_never_breaks_the_alert(aws, monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "true")
    import boto3

    class Broken:
        def publish(self, **kw):
            raise RuntimeError("SMS sandbox: number not verified")
    monkeypatch.setattr(boto3, "client", lambda name, **kw: Broken())
    rec = notify.notify_trusted_contact(TRIP, None, "passenger_help")
    assert rec["sms"]["status"] == "failed" and rec["status"] in ("simulated", "paused")


def test_sms_still_sent_when_whatsapp_is_switched_off(aws, monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "true")
    sms = sent_sms(monkeypatch)
    call("PUT", "/api/ops/config", {"whatsapp_enabled": False}, headers={"x-team-code": "secret-code"})
    trip = book(safe_mode=True)
    ev = call("POST", f"/api/trips/{trip['trip_id']}/sos", {})[1]
    assert ev["notifications"][0]["status"] == "paused" and ev["notifications"][0]["sms"]["status"] == "sent"
    assert len(sms) == 1
