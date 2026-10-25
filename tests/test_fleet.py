"""Proactive WhatsApp check-ins at booking, AI triage on escalation, and the operator fleet view."""
from core import assistant
from test_trips_api import book, call, stop_for

CODE = {"x-team-code": "secret-code"}


def outbox(session):
    return [m["text"] for m in call("GET", "/api/whatsapp/outbox", qs={"session": session})[1]["messages"]]


def test_booking_with_whatsapp_number_links_without_trip_code(aws):
    trip = book(safe_mode=True, passenger_phone="082 555 0199", wa_session="fleet1")
    assert trip["whatsapp_linked"] and trip["whatsapp_channel"] == "simulator"
    assert "0199" not in trip["passenger_phone"]
    welcome = outbox("fleet1")
    assert len(welcome) == 1 and "Safe Journey is on" in welcome[0] and trip["driver"]["plate"] in welcome[0]

    stop_for(trip["trip_id"], 200)
    prompt = outbox("fleet1")
    assert "Face ID" in prompt[0]  # start-of-ride driver check (simulated)
    assert len(prompt) == 2 and "Thandi, your trip has stopped. *Are you safe?*" in prompt[1]
    assert "*2* = Help" in prompt[1]


def test_invalid_passenger_number_rejected(aws):
    status, body = call("POST", "/api/trips", {"pickup": "rosebank", "destination": "sandton", "passenger_phone": "12"})
    assert status == 400


def test_no_response_escalation_gets_ai_triage_and_turns_fleet_red(aws, monkeypatch):
    tid = book(safe_mode=True)["trip_id"]
    results = stop_for(tid, 200 + 135)  # stop raises a check-in, then 2+ minutes with no answer
    escalated = [e for r in results for e in r["escalated"]]
    assert escalated and escalated[0]["triage"]["text"] == "AI says (triage)"

    status, dash = call("GET", "/api/dashboard", headers=CODE)
    row = next(f for f in dash["fleet"] if f["trip_id"] == tid)
    assert row["risk"] == "red" and row["triage"]["text"] == "AI says (triage)"
    assert row["position"]["speed_kmh"] == 0
    assert dash["summary"]["at_risk"] >= 1

    ev_id = row["triage"]["event_id"]
    assert call("POST", f"/api/trips/{tid}/events/{ev_id}/ack", {"action": "Called driver"})[0] == 401
    status, ev = call("POST", f"/api/trips/{tid}/events/{ev_id}/ack", {"action": "Called driver"}, headers=CODE)
    assert status == 200 and ev["operator_ack"]["action"] == "Called driver"
    row = next(f for f in call("GET", "/api/dashboard", headers=CODE)[1]["fleet"] if f["trip_id"] == tid)
    assert row["risk"] == "handled"


def test_open_checkin_is_amber_and_normal_trip_green(aws):
    calm = book(safe_mode=True)["trip_id"]
    call("POST", f"/api/trips/{calm}/telemetry", {"lat": -26.146, "lng": 28.044, "ts": 0})
    waiting = book(safe_mode=True)["trip_id"]
    stop_for(waiting, 200)
    fleet = {f["trip_id"]: f["risk"] for f in call("GET", "/api/dashboard", headers=CODE)[1]["fleet"]}
    assert fleet[calm] == "green" and fleet[waiting] == "amber"


def test_triage_fallback_is_actionable(aws, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bedrock down")
    monkeypatch.setattr(assistant, "_converse", boom)
    trip = {"trip_id": "MZTEST", "driver": {"name": "Sipho"}}
    out = assistant.triage(trip, {"type": "PROLONGED_STOP", "details": {"stationary_s": 300}}, "no_response")
    assert out["source"] == "fallback" and out["text"].startswith("Trip MZTEST") and "10111" in out["text"]


def test_triage_prompt_forbids_blame():
    assert "Never accuse the driver" in assistant.TRIAGE_PROMPT
