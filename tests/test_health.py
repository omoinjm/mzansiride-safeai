"""The Fleet page's system health panel."""
from botocore.exceptions import ClientError

from core import assistant, health, notify
from test_trips_api import call

CODE = {"x-team-code": "secret-code"}


def test_health_needs_team_code(aws):
    assert call("GET", "/api/ops/health")[0] == 401


def test_health_counts_messages_ai_and_whatsapp_state(aws, monkeypatch):
    trip = {"trip_id": "MZTEST", "passenger_name": "Thandi", "driver": {}, "trusted_contact": {"name": "Mom", "phone": "082 555 0101"}}
    notify.notify_trusted_contact(trip, None, "passenger_sos")  # simulated (no gateway in tests)
    health.record({"wa_sent": 2}, wa_last_sent_at="2026-10-25T10:00:00Z")

    class Refused:
        def converse(self, **kw):
            if kw["modelId"] == "primary":
                raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "Converse")
            return {"output": {"message": {"content": [{"text": "hi"}]}}, "stopReason": "end_turn", "usage": {}}
    monkeypatch.undo()  # use the real _converse (conftest stubs it)
    monkeypatch.setattr(assistant, "_client", Refused())
    monkeypatch.setattr(assistant, "MODEL_ID", "primary")
    monkeypatch.setattr(assistant, "MODEL_FALLBACK_ID", "backup")
    assistant.chat("hello")

    status, h = call("GET", "/api/ops/health", headers=CODE)
    assert status == 200
    assert h["messages_today"]["contact_alerts_simulated"] == 1 and h["messages_today"]["whatsapp_sent"] == 2
    assert h["ai"]["calls_today"] == 1 and h["ai"]["via_fallback_model"] == 1 and h["ai"]["last_model"] == "backup"
    assert h["whatsapp"]["status"] == "not_configured"


def test_whatsapp_degraded_when_last_send_failed(aws, monkeypatch):
    monkeypatch.setenv("WHATSAPP_FUNCTION", "wa-fn")
    import time
    now = lambda m: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + m * 60))  # noqa: E731
    health.record(wa_last_sent_at=now(-10), wa_last_error_at=now(-5))
    h = call("GET", "/api/ops/health", headers=CODE)[1]
    assert h["whatsapp"]["status"] == "degraded" and "wa-restart" in h["whatsapp"]["advice"]
    health.record(wa_last_sent_at=now(-1))
    assert call("GET", "/api/ops/health", headers=CODE)[1]["whatsapp"]["status"] == "ok"
    health.record(wa_last_sent_at=now(-60), wa_last_error_at=now(-30))  # an old failure doesn't count
    assert call("GET", "/api/ops/health", headers=CODE)[1]["whatsapp"]["status"] == "ok"


def test_unknown_number_is_not_a_gateway_failure(aws, monkeypatch):
    import io
    import urllib.error
    from whatsapp import handler, openwa

    def reject(chat, text):
        raise urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(b""))
    monkeypatch.setattr(openwa, "send_text", reject)
    handler.handler({"action": "send", "chat_id": "27820000000@c.us", "text": "hi"}, None)  # no exception
    m = call("GET", "/api/ops/health", headers=CODE)[1]["messages_today"]
    assert m["whatsapp_undeliverable"] == 1 and m["whatsapp_failed"] == 0


def test_scheduled_check_publishes_metrics(aws, monkeypatch):
    from api import handler
    sent = []

    class FakeCw:
        def put_metric_data(self, **kw):
            sent.append(kw)
    import boto3
    monkeypatch.setattr(boto3, "client", lambda name, **kw: FakeCw())
    m = handler.handler({"action": "health_check"}, None)
    assert m == {"WhatsAppHealthy": 1, "AIHealthy": 1, "SmsHealthy": 1, "HealthCheckRan": 1}
    assert sent[0]["Namespace"] == "MzansiRide/Health" and len(sent[0]["MetricData"]) == 4

    import time
    health.record(sms_last_error_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    monkeypatch.setenv("WHATSAPP_FUNCTION", "wa-fn")
    health.record(wa_last_error_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    m = handler.handler({"action": "health_check"}, None)
    assert m["SmsHealthy"] == 0 and m["WhatsAppHealthy"] == 0
    call("PUT", "/api/ops/config", {"whatsapp_enabled": False}, headers=CODE)  # paused is not an outage
    assert handler.handler({"action": "health_check"}, None)["WhatsAppHealthy"] == 1
