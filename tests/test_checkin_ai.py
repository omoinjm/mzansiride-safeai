"""Free-text check-in replies, the no-answer ladder, the simulated Face ID check and the plate photo check."""
import base64
import json

from core import assistant, drivers, trips
from test_trips_api import book, call, stop_for, wa

CODE = {"x-team-code": "secret-code"}


def model_says(monkeypatch, intent, reason="took a detour"):
    calls = []

    def fake(messages, channel, **kw):
        calls.append(channel)
        return {"text": json.dumps({"intent": intent, "reason": reason}), "source": "bedrock", "model": "m"}
    monkeypatch.setattr(assistant, "_converse", fake)
    return calls


def open_checkin(**extra):
    trip = book(safe_mode=True, **extra)
    out = stop_for(trip["trip_id"], 200)
    ev = next(e for r in out for e in r["new_events"])
    return trip["trip_id"], ev["event_id"]


# ---------- classifier ----------

def test_obvious_replies_and_danger_skip_the_model(monkeypatch):
    calls = model_says(monkeypatch, "ok")
    assert assistant.classify_checkin_reply("1")["intent"] == "ok"
    assert assistant.classify_checkin_reply("2")["intent"] == "help"
    # The model would say "ok", but danger words always win.
    assert assistant.classify_checkin_reply("we're fine but he has a knife")["intent"] == "help"
    assert assistant.classify_checkin_reply("The driver won't stop the car")["intent"] == "help"
    assert calls == []


def test_free_text_uses_the_model(monkeypatch):
    calls = model_says(monkeypatch, "ok", "detour, still going to Sandton")
    out = assistant.classify_checkin_reply("we took a different road, still going to Sandton")
    assert out == {"intent": "ok", "reason": "detour, still going to Sandton", "source": "bedrock", "model": "m"}
    assert calls == ["checkin_reply"]


def test_model_failure_or_garbage_is_unclear(monkeypatch):
    monkeypatch.setattr(assistant, "_converse", lambda *a, **k: {"text": "sure!", "source": "bedrock", "model": "m"})
    assert assistant.classify_checkin_reply("hmm maybe")["intent"] == "unclear"

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(assistant, "_converse", boom)
    assert assistant.classify_checkin_reply("hmm maybe")["intent"] == "unclear"


# ---------- replies change the alert ----------

def test_web_free_text_ok_closes_and_keeps_the_words(aws, monkeypatch):
    tid, ev = open_checkin()
    model_says(monkeypatch, "ok", "detour, same destination")
    status, out = call("POST", f"/api/trips/{tid}/events/{ev}/reply", {"text": "Took a detour, still going to Sandton"})
    assert status == 200 and out["intent"] == "ok"
    assert out["event"]["status"] == "resolved_ok"
    assert out["event"]["response_text"] == "Took a detour, still going to Sandton"
    assert out["event"]["response_reason"] == "detour, same destination"


def test_unclear_reply_never_closes(aws, monkeypatch):
    tid, ev = open_checkin()
    model_says(monkeypatch, "unclear", "not sure")
    out = call("POST", f"/api/trips/{tid}/events/{ev}/reply", {"text": "lol what"})[1]
    assert out["intent"] == "unclear" and out["event"]["status"] == trips.OPEN
    assert out["event"]["unclear_replies"][0]["text"] == "lol what"


def test_whatsapp_free_text_answers(aws, monkeypatch):
    tid, _ = open_checkin()
    assert "Linked to trip" in wa(f"trip {tid}", session="ft")  # picks up the check-in that is already open

    model_says(monkeypatch, "unclear")
    assert "Reply *1*" in wa("maybe", session="ft")
    model_says(monkeypatch, "ok", "stopped for fuel")
    assert "stopped for fuel" in wa("we're just getting petrol", session="ft")
    assert trips.chat_link("sim:ft")["pending_event_id"] is None


def test_whatsapp_danger_escalates_without_ai(aws, monkeypatch):
    tid, ev = open_checkin()
    wa(f"trip {tid}", session="dz")
    calls = model_says(monkeypatch, "ok")
    assert "Alerting" in wa("he locked the doors", session="dz")
    assert trips.get_event(tid, ev)["status"] == "escalated" and calls[-1] == "triage"


# ---------- no-answer ladder ----------

def test_ops_config_needs_team_code_and_validates(aws):
    assert call("GET", "/api/ops/config")[0] == 401
    assert call("PUT", "/api/ops/config", {"checkin_timeout_s": 30}, headers=CODE)[0] == 400
    assert call("PUT", "/api/ops/config", {"checkin_timeout_s": 300}, headers=CODE)[1] == {"checkin_timeout_s": 300}
    assert call("GET", "/api/config")[1]["checkin_timeout_s"] == 300


def test_reminder_at_half_window_then_escalation(aws):
    call("PUT", "/api/ops/config", {"checkin_timeout_s": 240}, headers=CODE)
    tid = book(safe_mode=True)["trip_id"]
    out = stop_for(tid, 200 + 135)  # alert at ~180 s, half window (120 s) passes, full window (240 s) not yet
    assert [e for r in out for e in r["reminded"]] and not [e for r in out for e in r["escalated"]]
    ev = next(e for e in trips.list_events(tid) if e["type"] == "PROLONGED_STOP")
    assert ev["reminded_at"] and ev["status"] == trips.OPEN

    out = stop_for(tid, 150, start_ts=345)
    assert [e for r in out for e in r["escalated"]]


# ---------- simulated Face ID ----------

def test_driver_face_id_check_at_start(aws, monkeypatch):
    unenrolled = next(d for d in drivers.SEED if d["status"] == "active" and not d["biometric_enrolled"])
    monkeypatch.setattr(drivers, "assign_driver", lambda: dict(unenrolled))
    tid = book()["trip_id"]
    trip = call("POST", f"/api/trips/{tid}/start")[1]
    assert trip["driver_check"]["status"] == "not_verified" and trip["driver_check"]["simulated"]

    enrolled = next(d for d in drivers.SEED if d["biometric_enrolled"])
    monkeypatch.setattr(drivers, "assign_driver", lambda: dict(enrolled))
    tid = book()["trip_id"]
    assert call("POST", f"/api/trips/{tid}/start")[1]["driver_check"]["status"] == "verified"


# ---------- plate photo ----------

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 100).decode()


def test_photo_check_reads_plate_and_looks_it_up(aws, monkeypatch):
    monkeypatch.setattr(assistant, "_converse", lambda *a, **k: {"text": "bx 33 kk gp", "source": "bedrock", "model": "m"})
    status, out = call("POST", "/api/drivers/photo-check", {"image": PNG, "mime": "image/png"})
    assert status == 200 and out["plate"] == "BX 33 KK GP" and out["lookup"]["verdict"] == "caution"
    assert out["stored"] is False


def test_photo_check_unreadable_and_bad_input(aws, monkeypatch):
    monkeypatch.setattr(assistant, "_converse", lambda *a, **k: {"text": "NONE", "source": "bedrock", "model": "m"})
    out = call("POST", "/api/drivers/photo-check", {"image": PNG, "mime": "image/png"})[1]
    assert out["plate"] is None and "CHECK" in out["advice"]
    assert call("POST", "/api/drivers/photo-check", {"image": "!!", "mime": "image/png"})[0] == 400
    assert call("POST", "/api/drivers/photo-check", {"image": PNG, "mime": "image/gif"})[0] == 400
    big = base64.b64encode(b"0" * (3 * 1024 * 1024 + 1)).decode()
    assert call("POST", "/api/drivers/photo-check", {"image": big, "mime": "image/png"})[0] == 400


# ---------- short messages + help after an automatic escalation ----------

def test_help_after_auto_escalation_still_alerts_the_contact(aws, monkeypatch):
    model_says(monkeypatch, "ok")
    tid = book(safe_mode=True)["trip_id"]
    stop_for(tid, 200 + 135)  # check-in, then no reply: escalated for no_response, contact told once
    ev = next(e for e in trips.list_events(tid) if e["type"] == "PROLONGED_STOP")
    assert ev["status"] == "escalated" and len(ev["notifications"]) == 1

    out = call("POST", f"/api/trips/{tid}/events/{ev['event_id']}/reply", {"text": "help"})[1]
    reasons = [n["reason"] for n in out["event"]["notifications"]]
    assert reasons == ["no_response", "passenger_help"]  # the contact hears that they asked for help
    assert "asked for HELP" in out["event"]["notifications"][-1]["text"]
    # a second "help" doesn't spam the contact
    out = call("POST", f"/api/trips/{tid}/events/{ev['event_id']}/reply", {"text": "2"})[1]
    assert len(out["event"]["notifications"]) == 2


def test_whatsapp_messages_are_short(aws, monkeypatch):
    from core import notify
    model_says(monkeypatch, "ok")
    trip = book(safe_mode=True, passenger_phone="082 555 0199", wa_session="short")
    stop_for(trip["trip_id"], 200 + 135)
    sent = [m["text"] for m in call("GET", "/api/whatsapp/outbox", qs={"session": "short"})[1]["messages"]]
    sent += [wa(t, session="short") for t in ("hi", "check CA 123-456", "check BX 33 KK GP", "2", "sos")]
    ev = trips.list_events(trip["trip_id"])[0]
    sent.append(notify.contact_message(trips.get_trip(trip["trip_id"]), ev, "passenger_help"))
    for text in sent:
        lines = [l for l in text.splitlines() if l.strip()]
        assert len(lines) <= 6 and all(len(l) <= 120 for l in lines), text
        assert len(text) <= 260, text
    check_in = next(t for t in sent if "Are you safe?" in t)
    assert len(check_in) <= 90 and check_in.count("\n") <= 1


def test_contact_delivery_is_shown_and_whatsapp_reply_is_honest(aws, monkeypatch):
    model_says(monkeypatch, "ok")
    trip = book(safe_mode=True)  # WhatsApp isn't connected in tests: contact alerts are simulated
    assert trip["trusted_contact"]["delivery"] == "simulated"
    stop_for(trip["trip_id"], 200)
    wa(f"trip {trip['trip_id']}", session="hon")
    reply = wa("2", session="hon")
    assert "Mom" not in reply.split("\n")[0] and "simulated" in reply
    monkeypatch.setenv("WHATSAPP_FUNCTION", "wa-fn")
    assert call("GET", f"/api/trips/{trip['trip_id']}")[1]["trusted_contact"]["delivery"] == "whatsapp"
