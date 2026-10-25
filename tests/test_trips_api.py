import json

from core import commands, places, trips

ROUTE = places.get_route("rosebank", "sandton")["points"]


def call(method, path, body=None, headers=None, qs=None):
    from api import handler
    ev = {"rawPath": path, "requestContext": {"http": {"method": method}}, "headers": headers or {},
          "queryStringParameters": qs, "body": json.dumps(body) if body is not None else None}
    r = handler.handler(ev, None)
    return r["statusCode"], json.loads(r["body"])


def book(**extra):
    body = {"pickup": "rosebank", "destination": "sandton", "passenger_name": "Thandi",
            "trusted_contact": {"name": "Mom", "phone": "082 555 0101"}, **extra}
    status, trip = call("POST", "/api/trips", body)
    assert status == 200, trip
    return trip


def stop_for(trip_id, seconds, start_ts=0, step=15):
    p = ROUTE[len(ROUTE) // 2]
    out = []
    for ts in range(start_ts, start_ts + seconds + step, step):
        out.append(call("POST", f"/api/trips/{trip_id}/telemetry", {"lat": p[0], "lng": p[1], "ts": ts})[1])
    return out


def test_health_and_places(aws):
    assert call("GET", "/api/health")[1]["ok"]
    assert len(call("GET", "/api/places")[1]["places"]) == len(places.PLACES)
    assert call("GET", "/api/nope")[0] == 404


def test_quote_rejects_same_place(aws):
    status, body = call("POST", "/api/quote", {"pickup": "wits", "destination": "wits"})
    assert status == 400


def test_book_returns_driver_route_and_masks_phone(aws):
    trip = book()
    assert trip["trip_id"].startswith("MZ") and len(trip["trip_id"]) == 6
    assert trip["driver"]["status"] == "active"
    assert len(trip["route"]["points"]) > 5
    assert "555" not in trip["trusted_contact"]["phone"]


def test_no_events_without_safe_mode(aws):
    trip = book()
    results = stop_for(trip["trip_id"], 300)
    assert all(not r["new_events"] for r in results)


def test_full_journey_prolonged_stop_ok(aws):
    trip = book()
    tid = trip["trip_id"]
    assert call("POST", f"/api/trips/{tid}/safe-mode", {"enabled": True})[1]["safe_mode"] is True
    results = stop_for(tid, 200)
    events = [e for r in results for e in r["new_events"]]
    assert [e["type"] for e in events] == ["PROLONGED_STOP"]
    ev = events[0]
    status, ai = call("POST", f"/api/trips/{tid}/events/{ev['event_id']}/explain", {})
    assert status == 200 and ai["source"] == "bedrock"
    status, done = call("POST", f"/api/trips/{tid}/events/{ev['event_id']}/checkin", {"response": "ok", "prompt_ms": 420})
    assert done["status"] == "resolved_ok" and done["notifications"] == []
    # explanation is cached on the event
    call("POST", f"/api/trips/{tid}/events/{ev['event_id']}/explain", {})
    assert len(aws["bedrock_calls"]) == 1


def test_need_help_notifies_contact(aws):
    tid = book(safe_mode=True)["trip_id"]
    ev = [e for r in stop_for(tid, 200) for e in r["new_events"]][0]
    status, done = call("POST", f"/api/trips/{tid}/events/{ev['event_id']}/checkin", {"response": "help"})
    assert done["status"] == "escalated" and done["escalation_reason"] == "passenger_help"
    n = done["notifications"][0]
    assert n["status"] == "simulated" and "10111" in n["text"] and "Thandi" in n["text"]


def test_no_response_escalates_after_timeout(aws):
    tid = book(safe_mode=True)["trip_id"]
    results = stop_for(tid, 200 + trips.CHECKIN_TIMEOUT_S + 30)
    escalated = [e for r in results for e in r["escalated"]]
    assert len(escalated) == 1 and escalated[0]["escalation_reason"] == "no_response"


def test_dashboard_requires_team_code(aws):
    book()
    assert call("GET", "/api/dashboard")[0] == 401
    status, body = call("GET", "/api/dashboard", headers={"x-team-code": "secret-code"})
    assert status == 200 and body["summary"]["trips"] == 1


def test_sos_and_share(aws):
    tid = book()["trip_id"]
    assert call("POST", f"/api/trips/{tid}/sos", {})[1]["type"] == "SOS"
    assert call("POST", f"/api/trips/{tid}/sos", {"share": True})[1]["type"] == "TRIP_SHARED"


def test_assistant_endpoint(aws):
    status, body = call("POST", "/api/assistant", {"message": "Why did my trip stop?", "history": [
        {"role": "assistant", "text": "hi"}, {"role": "user", "text": "a"}, {"role": "user", "text": "b"}]})
    assert status == 200 and body["source"] == "bedrock"
    msgs = aws["bedrock_calls"][-1]["messages"]
    assert msgs[0]["role"] == "user" and all(a["role"] != b["role"] for a, b in zip(msgs, msgs[1:]))


def test_assistant_fallback_when_bedrock_down(aws, monkeypatch):
    from core import assistant
    def boom(*a, **k):
        raise RuntimeError("AccessDenied")
    monkeypatch.setattr(assistant, "_converse", boom)
    r = assistant.explain_event({"type": "ROUTE_DEVIATION", "details": {"deviation_m": 400}})
    assert r["source"] == "fallback" and "10111" in r["text"]


def test_system_prompt_has_guardrails():
    from core.assistant import SYSTEM_PROMPT
    for phrase in ("Never accuse or blame the driver", "10111", "do not replace emergency services", "approved guidance"):
        assert phrase.lower() in SYSTEM_PROMPT.lower()


# ---------- WhatsApp conversation (via the simulator endpoint) ----------

def wa(text, session="test1"):
    status, body = call("POST", "/api/whatsapp/simulate", {"session": session, "text": text})
    assert status == 200, body
    return "\n".join(body["replies"])


def test_whatsapp_menu_and_check(aws):
    assert "CHECK" in wa("hi")
    assert "Registered driver" in wa("check CA 123-456")
    assert "Caution" in wa("CHECK bx33kkgp")
    assert "No record" in wa("check ZZ 11 ZZ GP")


def test_whatsapp_link_prompt_and_reply(aws):
    tid = book(safe_mode=True)["trip_id"]
    assert "Linked to trip" in wa(f"trip {tid.lower()}")
    stop_for(tid, 200)
    status, out = call("GET", "/api/whatsapp/outbox", qs={"session": "test1"})
    assert len(out["messages"]) == 2 and "Face ID" in out["messages"][0]["text"]
    assert "Reply *1*" in out["messages"][1]["text"]
    assert "alerting mom" in wa("help").lower()  # "help" during an open check-in escalates
    assert "No open check-in" in wa("1")


def test_whatsapp_free_text_goes_to_ai(aws):
    assert wa("The driver is asking for extra cash, what do I do?") == "AI says (whatsapp)"


def test_whatsapp_bad_trip_code(aws):
    assert "not found" in wa("trip ABCD")


def test_whatsapp_sos_without_link(aws):
    assert "10111" in wa("sos")
