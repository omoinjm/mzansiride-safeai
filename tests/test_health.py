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
    health.record(wa_last_sent_at="2026-10-25T10:00:00Z", wa_last_error_at="2026-10-25T10:05:00Z")
    h = call("GET", "/api/ops/health", headers=CODE)[1]
    assert h["whatsapp"]["status"] == "degraded" and "wa-restart" in h["whatsapp"]["advice"]
    health.record(wa_last_sent_at="2026-10-25T10:06:00Z")
    assert call("GET", "/api/ops/health", headers=CODE)[1]["whatsapp"]["status"] == "ok"
