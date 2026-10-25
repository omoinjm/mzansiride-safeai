"""Trip + safety-event workflow shared by the web API and WhatsApp (channel-agnostic core)."""
import json
import os
import random
import time
from datetime import datetime

from . import assistant, drivers, fares, geo, notify, places, rules, store
from .log import log

CHECKIN_TIMEOUT_S = int(os.environ.get("CHECKIN_TIMEOUT_S", "120"))  # trip-time seconds without an answer
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I: easy to type on WhatsApp
OPEN = "awaiting_checkin"
FLEET_STALE_S = 15 * 60  # an in-progress trip without telemetry for this long drops off the live fleet view


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass


def _code():
    return "MZ" + "".join(random.choice(CODE_ALPHABET) for _ in range(4))


def get_trip(trip_id):
    trip = store.get("trips", {"trip_id": (trip_id or "").upper()})
    if not trip:
        raise NotFound(f"trip {trip_id} not found")
    return trip


def public_trip(trip, with_route=True):
    t = {k: v for k, v in trip.items() if k not in ("rules_state", "ttl", "wa_chat_id", "passenger_phone")}
    t["whatsapp_linked"] = bool(trip.get("wa_chat_id"))
    if trip.get("passenger_phone"):
        t["passenger_phone"] = notify.mask(trip["passenger_phone"])
    if trip.get("trusted_contact"):
        t["trusted_contact"] = {**trip["trusted_contact"], "phone": notify.mask(trip["trusted_contact"].get("phone"))}
    if with_route:
        t["route"] = places.get_route(trip["pickup"], trip["destination"])
    return t


def quote(pickup, destination):
    route = places.get_route(pickup, destination)
    if not route:
        raise BadRequest("Choose two different places from the list")
    return {**fares.quote(route["distance_m"], route["duration_s"]), "points": route["points"]}


def create_trip(body):
    pickup, destination = body.get("pickup"), body.get("destination")
    route = places.get_route(pickup, destination)
    if not route:
        raise BadRequest("Choose two different places from the list")
    q = fares.quote(route["distance_m"], route["duration_s"])
    riders = int(body.get("riders") or 1)
    option = next((o for o in q["options"] if o["riders"] == riders), q["options"][0])
    contact = body.get("trusted_contact") or None
    if contact and not (contact.get("phone") or "").strip():
        contact = None
    phone = (body.get("passenger_phone") or "").strip()
    if phone and not notify.msisdn(phone):
        raise BadRequest("Enter a valid WhatsApp number, e.g. 082 123 4567")
    trip = {
        "trip_id": None,
        "passenger_name": (body.get("passenger_name") or "Passenger").strip()[:40],
        "pickup": pickup,
        "destination": destination,
        "pickup_name": places.PLACES[pickup]["name"],
        "destination_name": places.PLACES[destination]["name"],
        "ride_type": option["type"],
        "riders": option["riders"],
        "fare_zar": option["fare_zar"],
        "individual_fare_zar": q["options"][0]["fare_zar"],
        "distance_km": q["distance_km"],
        "duration_min": q["duration_min"],
        "driver": drivers.public(drivers.assign_driver()),
        "status": "driver_assigned",
        "safe_mode": bool(body.get("safe_mode", False)),
        "trusted_contact": {"name": (contact.get("name") or "").strip()[:40], "phone": contact["phone"].strip()[:20]}
        if contact else None,
        "passenger_phone": phone[:20] or None,
        "created_at": notify.now_iso(),
        "events_count": 0,
        "rules_state": rules.new_state(),
        "simulated": True,
        "ttl": store.ttl_days(14),
    }
    for _ in range(5):  # retry on the (unlikely) code collision
        trip["trip_id"] = _code()
        try:
            store.table("trips").put_item(Item=store.to_ddb(trip), ConditionExpression="attribute_not_exists(trip_id)")
            break
        except store.table("trips").meta.client.exceptions.ConditionalCheckFailedException:
            continue
    log("INFO", "trip_created", trip=trip["trip_id"], route=places.route_id(pickup, destination),
        ride_type=trip["ride_type"], safe_mode=trip["safe_mode"])
    if phone:
        _link_passenger_whatsapp(trip, phone, body.get("wa_session"))
    return trip


def _link_passenger_whatsapp(trip, phone, sim_session):
    """Proactive check-ins: the passenger gets WhatsApp messages without first sending "TRIP <code>".

    Real WhatsApp only for allow-listed demo numbers (we never message strangers). Any other number is
    routed to the caller's in-browser WhatsApp simulator, or recorded as simulated when there is none.
    """
    if notify.allowlisted(phone) and notify.whatsapp_enabled():
        chat, channel = f"{notify.msisdn(phone)}@c.us", "whatsapp"
    elif sim_session:
        chat, channel = "sim:" + "".join(c for c in str(sim_session) if c.isalnum() or c == "-")[:40], "simulator"
    else:
        trip["whatsapp_channel"] = "simulated"
        store.put("trips", trip)
        return
    link_chat(chat, trip["trip_id"])
    trip.update(wa_chat_id=chat, whatsapp_channel=channel)
    update_trip(trip["trip_id"], whatsapp_channel=channel)
    notify.send_whatsapp(chat, notify.welcome_message(trip))


def update_trip(trip_id, **fields):
    trip = get_trip(trip_id)
    trip.update(fields)
    store.put("trips", trip)
    return trip


def set_safe_mode(trip_id, enabled):
    trip = update_trip(trip_id, safe_mode=bool(enabled))
    log("INFO", "safe_mode", trip=trip["trip_id"], enabled=bool(enabled))
    return trip


def set_trusted_contact(trip_id, contact):
    phone = (contact or {}).get("phone", "").strip()
    if phone and not notify.msisdn(phone):
        raise BadRequest("Enter a valid phone number, e.g. 082 123 4567")
    value = {"name": (contact.get("name") or "").strip()[:40], "phone": phone[:20]} if phone else None
    return update_trip(trip_id, trusted_contact=value)


def start_trip(trip_id):
    trip = get_trip(trip_id)
    if trip["status"] in ("driver_assigned",):
        trip.update(status="in_progress", started_at=notify.now_iso())
        store.put("trips", trip)
    return trip


def complete_trip(trip_id):
    trip = update_trip(trip_id, status="completed", completed_at=notify.now_iso())
    if trip.get("wa_chat_id"):
        notify.send_whatsapp(trip["wa_chat_id"], f"✅ Trip {trip['trip_id']} completed. Thanks for travelling safely with MzansiRide.")
    return trip


def list_events(trip_id):
    return sorted(store.query_events(trip_id), key=lambda e: e["event_id"])


def get_event(trip_id, event_id):
    ev = store.get("events", {"trip_id": trip_id, "event_id": event_id})
    if not ev:
        raise NotFound(f"event {event_id} not found")
    return ev


def _new_event(trip, kind, lat, lng, trip_ts, details, status=OPEN):
    ev = {
        "trip_id": trip["trip_id"],
        "event_id": f"{int(time.time() * 1000)}-{kind}",
        "type": kind,
        "status": status,
        "created_at": notify.now_iso(),
        "trip_ts": trip_ts,
        "lat": lat,
        "lng": lng,
        "details": details or {},
        "notifications": [],
        "simulated": True,
        "ttl": store.ttl_days(14),
    }
    store.put("events", ev)
    trip["events_count"] = int(trip.get("events_count") or 0) + 1
    return ev


def telemetry(trip_id, tick):
    """One simulated position reading. Applies the rules (only in Safe Journey Mode) and escalation timeouts."""
    started = time.time()
    trip = get_trip(trip_id)
    if trip["status"] in ("completed", "cancelled"):
        raise BadRequest("Trip has ended")
    if trip["status"] == "driver_assigned":
        trip.update(status="in_progress", started_at=notify.now_iso())
    try:
        tick = {"lat": float(tick["lat"]), "lng": float(tick["lng"]), "ts": float(tick["ts"])}
    except (KeyError, TypeError, ValueError):
        raise BadRequest("lat, lng and ts are required numbers")
    prev = trip.get("last_position") or {}
    if prev.get("ts") is not None and tick["ts"] > float(prev["ts"]):
        metres = geo.haversine((float(prev["lat"]), float(prev["lng"])), (tick["lat"], tick["lng"]))
        tick["speed_kmh"] = round(metres / (tick["ts"] - float(prev["ts"])) * 3.6)
    trip["last_position"] = {**tick, "at": notify.now_iso()}

    new_events, escalated = [], []
    if trip.get("safe_mode"):
        route = places.get_route(trip["pickup"], trip["destination"])
        state, detected = rules.evaluate(trip.get("rules_state"), tick, route["points"])
        trip["rules_state"] = state
        for d in detected:
            ev = _new_event(trip, d["type"], d["lat"], d["lng"], d["trip_ts"], d["details"])
            new_events.append(ev)
            log("INFO", "safety_event", trip=trip["trip_id"], type=ev["type"], event_id=ev["event_id"],
                details=ev["details"])
        # Escalate open check-ins the passenger hasn't answered in time.
        for ev in (list_events(trip["trip_id"]) if not detected else []):
            if ev["status"] == OPEN and ev.get("trip_ts") is not None and tick["ts"] - ev["trip_ts"] >= CHECKIN_TIMEOUT_S:
                escalated.append(_escalate(trip, ev, "no_response"))
    store.put("trips", trip)

    if trip.get("wa_chat_id"):
        for ev in new_events:
            queue_whatsapp_prompt(trip, ev)

    open_events = [e for e in list_events(trip["trip_id"]) if e["status"] == OPEN] if (new_events or escalated) else []
    return {
        "trip": {"trip_id": trip["trip_id"], "status": trip["status"], "safe_mode": trip.get("safe_mode")},
        "new_events": new_events,
        "escalated": escalated,
        "open_events": open_events,
        "server_ms": round((time.time() - started) * 1000),
    }


def queue_whatsapp_prompt(trip, ev):
    """Send the check-in prompt (with an AI explanation) to the linked WhatsApp chat."""
    chat = trip["wa_chat_id"]
    if chat.startswith("sim:"):
        # The simulator outbox resolves this marker lazily (see whatsapp_prompt_text), keeping telemetry fast.
        notify._sim_outbox_append(chat, json.dumps({"prompt": [trip["trip_id"], ev["event_id"]]}))
    elif notify.whatsapp_enabled():
        import boto3

        boto3.client("lambda").invoke(
            FunctionName=os.environ["WHATSAPP_FUNCTION"], InvocationType="Event",
            Payload=json.dumps({"action": "checkin_prompt", "trip_id": trip["trip_id"], "event_id": ev["event_id"]}).encode(),
        )
    _set_pending(chat, trip["trip_id"], ev["event_id"])


def whatsapp_prompt_text(trip_id, event_id):
    trip, ev = get_trip(trip_id), get_event(trip_id, event_id)
    ai = explain(trip_id, event_id, channel="whatsapp")
    return notify.checkin_prompt(trip, ev, ai["text"])


def explain(trip_id, event_id, channel="web"):
    """AI explanation of an event. Cached on the event per channel so repeated views don't re-bill Bedrock."""
    ev = get_event(trip_id, event_id)
    cache = ev.get("ai") or {}
    if channel in cache:
        return cache[channel]
    trip = get_trip(trip_id)
    result = assistant.explain_event(ev, trip, channel=channel)
    if result["source"] != "fallback":
        cache[channel] = result
        ev["ai"] = cache
        store.put("events", ev)
    return result


def _escalate(trip, ev, reason):
    ev["status"] = "escalated"
    ev["escalation_reason"] = reason
    ev["escalated_at"] = notify.now_iso()
    ev.setdefault("notifications", []).append(notify.notify_trusted_contact(trip, ev, reason))
    ev["triage"] = assistant.triage(trip, ev, reason)
    store.put("events", ev)
    log("INFO", "event_escalated", trip=trip["trip_id"], event_id=ev["event_id"], reason=reason)
    if trip.get("wa_chat_id") and reason == "no_response":
        notify.send_whatsapp(trip["wa_chat_id"], "We didn't hear back from you, so your trusted contact has been notified. "
                                                 "Reply 1 if you are OK. In danger? Call 10111 or 112.")
    return ev


def checkin(trip_id, event_id, response, channel="web", prompt_ms=None):
    if response not in ("ok", "help"):
        raise BadRequest("response must be 'ok' or 'help'")
    trip, ev = get_trip(trip_id), get_event(trip_id, event_id)
    ev["response"] = response
    ev["response_channel"] = channel
    ev["responded_at"] = notify.now_iso()
    if prompt_ms is not None:
        try:
            ev["prompt_ms"] = int(prompt_ms)
        except (TypeError, ValueError):
            pass
    if response == "ok":
        # "I'm OK" also closes an escalation (e.g. they answered late); the contact is told nothing new.
        ev["status"] = "resolved_ok"
        store.put("events", ev)
    elif ev["status"] != "escalated":
        _escalate(trip, ev, "passenger_help")
    else:
        store.put("events", ev)
    if trip.get("wa_chat_id"):
        _set_pending(trip["wa_chat_id"], trip["trip_id"], None)
    log("INFO", "checkin", trip=trip_id, event_id=event_id, response=response, channel=channel, prompt_ms=prompt_ms)
    return ev


def sos(trip_id, channel="web", reason="passenger_sos"):
    """Manual SOS / share trip: recorded as an event and the trusted contact is notified straight away."""
    trip = get_trip(trip_id)
    pos = trip.get("last_position") or {}
    kind = "SOS" if reason == "passenger_sos" else "TRIP_SHARED"
    ev = _new_event(trip, kind, pos.get("lat"), pos.get("lng"), pos.get("ts"), {"channel": channel},
                    status="escalated" if kind == "SOS" else "info")
    ev["notifications"] = [notify.notify_trusted_contact(trip, ev, reason)]
    if kind == "SOS":
        ev["triage"] = assistant.triage(trip, ev, reason)
    store.put("events", ev)
    store.put("trips", trip)
    log("INFO", "sos" if kind == "SOS" else "trip_shared", trip=trip_id, channel=channel)
    return ev


# ---------- WhatsApp chat <-> trip links ----------

def link_chat(chat_id, trip_id):
    trip = get_trip(trip_id)
    if trip["status"] in ("completed", "cancelled"):
        raise BadRequest(f"Trip {trip['trip_id']} has already ended")
    old = trip.get("wa_chat_id")
    if old and old != chat_id:
        store.delete("whatsapp", {"pk": f"chat#{old}"})
    trip["wa_chat_id"] = chat_id
    store.put("trips", trip)
    store.put("whatsapp", {"pk": f"chat#{chat_id}", "trip_id": trip["trip_id"], "linked_at": notify.now_iso(),
                           "pending_event_id": None, "ttl": store.ttl_days(2)})
    log("INFO", "whatsapp_linked", trip=trip["trip_id"], chat=notify.mask(chat_id))
    return trip


def chat_link(chat_id):
    return store.get("whatsapp", {"pk": f"chat#{chat_id}"})


def unlink_chat(chat_id):
    link = chat_link(chat_id)
    if link:
        store.delete("whatsapp", {"pk": f"chat#{chat_id}"})
        try:
            trip = get_trip(link["trip_id"])
            if trip.get("wa_chat_id") == chat_id:
                trip.pop("wa_chat_id", None)
                store.put("trips", trip)
        except NotFound:
            pass
    return link


def _set_pending(chat_id, trip_id, event_id):
    link = chat_link(chat_id) or {"pk": f"chat#{chat_id}", "trip_id": trip_id, "ttl": store.ttl_days(2)}
    link["pending_event_id"] = event_id
    store.put("whatsapp", link)


# ---------- operator dashboard ----------

def acknowledge(trip_id, event_id, action=None):
    """The operator takes ownership (e.g. "Called driver") of this alert and any other escalated one on the trip.

    Alerts raised after this still turn the trip red again.
    """
    ev = get_event(trip_id, event_id)
    ack = {"at": notify.now_iso(), "action": (action or "Acknowledged").strip()[:120]}
    for e in list_events(trip_id):
        if e["event_id"] == event_id or (e["status"] == "escalated" and not e.get("operator_ack")):
            e["operator_ack"] = ack
            store.put("events", e)
            if e["event_id"] == event_id:
                ev = e
    log("INFO", "operator_ack", trip=trip_id, event_id=event_id)
    return ev


def _risk(trip, events):
    """green = normal, amber = waiting for the passenger, red = escalated and nobody has picked it up yet."""
    if any(e["status"] == "escalated" and not e.get("operator_ack") for e in events):
        return "red"
    if any(e["status"] == OPEN for e in events):
        return "amber"
    if any(e["status"] == "escalated" for e in events):
        return "handled"
    return "green"


def _fleet(trips, events):
    by_trip = {}
    for e in events:
        by_trip.setdefault(e["trip_id"], []).append(e)
    now = time.time()
    fleet = []
    for t in trips:
        pos = t.get("last_position") or {}
        if t.get("status") != "in_progress" or not pos.get("at"):
            continue
        if now - datetime.fromisoformat(pos["at"]).timestamp() > FLEET_STALE_S:
            continue
        evs = sorted(by_trip.get(t["trip_id"], []), key=lambda e: e["event_id"])
        alerts = [e for e in evs if e["type"] != "TRIP_SHARED"]
        latest = alerts[-1] if alerts else None
        triaged = next((e for e in reversed(alerts) if e.get("triage")), None)
        fleet.append({
            "trip_id": t["trip_id"],
            "passenger_name": t.get("passenger_name"),
            "pickup_name": t.get("pickup_name"),
            "destination_name": t.get("destination_name"),
            "driver": t.get("driver"),
            "safe_mode": t.get("safe_mode"),
            "whatsapp_channel": t.get("whatsapp_channel") or ("whatsapp" if t.get("wa_chat_id") else None),
            "position": {k: pos.get(k) for k in ("lat", "lng", "ts", "speed_kmh", "at")},
            "risk": _risk(t, alerts),
            "latest_event": {k: v for k, v in latest.items() if k not in ("ttl", "ai")} if latest else None,
            "triage": {**triaged["triage"], "event_id": triaged["event_id"], "operator_ack": triaged.get("operator_ack")}
            if triaged else None,
        })
    order = {"red": 0, "amber": 1, "handled": 2, "green": 3}
    return sorted(fleet, key=lambda f: (order[f["risk"]], f["trip_id"]))

def dashboard():
    trips = sorted(store.scan("trips"), key=lambda t: t.get("created_at", ""), reverse=True)[:100]
    events = sorted(store.scan("events", limit=1000), key=lambda e: e["event_id"], reverse=True)
    by_type, by_status, prompt_ms = {}, {}, []
    for e in events:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        if e.get("prompt_ms"):
            prompt_ms.append(e["prompt_ms"])
    responses = {"ok": 0, "help": 0, "no_response": 0}
    for e in events:
        if e.get("response") in responses:
            responses[e["response"]] += 1
        elif e.get("escalation_reason") == "no_response":
            responses["no_response"] += 1
    notifications = [n for e in events for n in e.get("notifications") or []]
    fleet = _fleet(trips, events)
    return {
        "fleet": fleet,
        "summary": {
            "trips": len(trips),
            "active": len(fleet),
            "at_risk": sum(1 for f in fleet if f["risk"] in ("red", "amber")),
            "trips_safe_mode": sum(1 for t in trips if t.get("safe_mode")),
            "events": len(events),
            "events_by_type": by_type,
            "events_by_status": by_status,
            "responses": responses,
            "notifications": len(notifications),
            "avg_prompt_ms": round(sum(prompt_ms) / len(prompt_ms)) if prompt_ms else None,
        },
        "trips": [public_trip(t, with_route=False) for t in trips],
        "events": [{k: v for k, v in e.items() if k != "ttl"} for e in events[:200]],
    }
