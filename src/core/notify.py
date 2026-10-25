"""Outbound messages: trusted-contact notifications and WhatsApp check-in prompts.

Only the `whatsapp` Lambda holds the OpenWA credentials, so other code asks it to send by
invoking it asynchronously ({"action": "send", ...}). The real WhatsApp path is used only when:
  - WhatsApp is enabled (WHATSAPP_FUNCTION set), AND
  - the recipient either messaged us first (a linked chat) or is on the demo allow-list
    (WA_ALLOWLIST, comma-separated MSISDNs). This avoids messaging strangers (abuse + ban risk).
Everything else is recorded as SIMULATED, which is what the web UI and dashboard show.
Chats whose id starts with "sim:" belong to the in-browser WhatsApp simulator and go to its outbox.
"""
import json
import os
import re
import time
from datetime import datetime, timezone

from . import store
from .log import log


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def msisdn(phone):
    """'082 123 4567' / '+27 82 123 4567' -> '27821234567'. Returns '' if it doesn't look like a number."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0") and len(digits) == 10:
        digits = "27" + digits[1:]
    return digits if 10 <= len(digits) <= 15 else ""


def mask(phone):
    d = msisdn(phone) or re.sub(r"\D", "", phone or "")
    return f"+{d[:4]}•••{d[-3:]}" if len(d) >= 7 else "•••"


def allowlisted(phone):
    allow = {msisdn(p) for p in os.environ.get("WA_ALLOWLIST", "").split(",") if p.strip()}
    return bool(msisdn(phone)) and msisdn(phone) in allow


def whatsapp_enabled():
    return bool(os.environ.get("WHATSAPP_FUNCTION"))


def send_whatsapp(chat_id, text):
    """Queue a WhatsApp message. Returns a delivery status string."""
    if chat_id.startswith("sim:"):
        _sim_outbox_append(chat_id, text)
        return "delivered_simulator"
    if not whatsapp_enabled():
        log("INFO", "whatsapp_simulated", chat=mask(chat_id))
        return "simulated"
    import boto3

    boto3.client("lambda").invoke(
        FunctionName=os.environ["WHATSAPP_FUNCTION"],
        InvocationType="Event",
        Payload=json.dumps({"action": "send", "chat_id": chat_id, "text": text}).encode(),
    )
    log("INFO", "whatsapp_queued", chat=mask(chat_id))
    return "queued_whatsapp"


def _sim_outbox_append(chat_id, text):
    key = {"pk": f"outbox#{chat_id}"}
    item = store.get("whatsapp", key) or {**key, "messages": []}
    item["messages"] = (item.get("messages") or [])[-20:] + [{"text": text, "at": now_iso()}]
    item["ttl"] = store.ttl_days(1)
    store.put("whatsapp", item)


def sim_outbox_pop(chat_id):
    key = {"pk": f"outbox#{chat_id}"}
    item = store.get("whatsapp", key)
    if not item:
        return []
    store.delete("whatsapp", key)
    return item.get("messages") or []


CONTACT_LEAD = {
    "passenger_help": "asked for HELP",
    "no_response": "did not answer a safety check-in",
    "passenger_sos": "sent an SOS",
    "share_trip": "shared their trip with you",
}


def contact_message(trip, event, reason):
    """Short and actionable: who, what, which car, where, what to do."""
    d = trip.get("driver") or {}
    pos = (event or {}).get("lat"), (event or {}).get("lng")
    if pos[0] is None and trip.get("last_position"):
        pos = trip["last_position"].get("lat"), trip["last_position"].get("lng")
    where = f"https://maps.google.com/?q={pos[0]:.5f},{pos[1]:.5f}" if pos[0] is not None else "unknown"
    name = trip.get("passenger_name", "A passenger")
    if reason == "share_trip":
        return (f"📍 {name} shared a trip with you: {trip.get('pickup_name')} → {trip.get('destination_name')}.\n"
                f"Car: {d.get('plate')} ({d.get('colour', '')} {d.get('vehicle', '')})\nLive: {where}")
    return (f"🚨 *{name} {CONTACT_LEAD.get(reason, reason)}* on a ride.\n"
            f"Car: *{d.get('plate')}*, {d.get('colour', '')} {d.get('vehicle', '')} ({d.get('name')})\n"
            f"Last seen: {where}\n"
            "Call them now. If you think they're in danger, call 10111. (MzansiRide demo)")


def notify_trusted_contact(trip, event, reason):
    """Returns the notification record that is stored on the event and shown in the UI."""
    contact = trip.get("trusted_contact") or {}
    phone = contact.get("phone", "")
    text = contact_message(trip, event, reason)
    record = {
        "to_name": contact.get("name") or "Trusted contact",
        "to": mask(phone) if phone else "not set",
        "reason": reason,
        "at": now_iso(),
        "text": text,
    }
    if not phone:
        record.update(channel="none", status="no_contact_set")
    elif allowlisted(phone) and whatsapp_enabled():
        record.update(channel="whatsapp", status=send_whatsapp(f"{msisdn(phone)}@c.us", text))
    else:
        record.update(channel="whatsapp", status="simulated")
    log("INFO", "contact_notified", trip=trip["trip_id"], reason=reason, status=record["status"],
        channel=record["channel"])
    return record


NOTICED = {
    "PROLONGED_STOP": "has stopped",
    "ROUTE_DEVIATION": "has left the route",
}


def first_name(trip):
    name = (trip.get("passenger_name") or "").split()
    return name[0] if name and name[0] != "Passenger" else "there"


def checkin_prompt(trip, event, explanation=None):
    """The WhatsApp check-in: one question, two answers. Readable in two seconds."""
    return (f"⚠️ {first_name(trip)}, your trip {NOTICED.get(event.get('type'), 'looks unusual')}. *Are you safe?*\n"
            "Reply *1* = Safe   *2* = Help")


def welcome_message(trip):
    d = trip.get("driver") or {}
    return (f"✅ Safe Journey is on: {trip.get('destination_name')}, car *{d.get('plate', '')}*.\n"
            "If anything looks wrong, we'll message you here.")


def epoch():
    return int(time.time())
