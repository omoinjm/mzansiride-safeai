"""Outbound messages: trusted-contact notifications and WhatsApp check-in prompts.

Only the `whatsapp` Lambda holds the OpenWA credentials, so other code asks it to send by
invoking it asynchronously ({"action": "send", ...}). The real WhatsApp path is used only when:
  - WhatsApp is enabled (WHATSAPP_FUNCTION set), AND
  - unsolicited sends (trusted-contact alerts, the first message to a passenger's number) are under a
    rate limit per number and per day: the public demo can message any number, so this caps abuse
    and protects the bot's WhatsApp number from being restricted.
Everything else is recorded as SIMULATED, which is what the web UI and dashboard show.
Chats whose id starts with "sim:" belong to the in-browser WhatsApp simulator and go to its outbox.
"""
import json
import os
import re
import time
from datetime import datetime, timezone

from . import health, store
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


PER_NUMBER_PER_HOUR = int(os.environ.get("WA_LIMIT_PER_NUMBER_HOUR", "20"))
PER_DAY = int(os.environ.get("WA_LIMIT_PER_DAY", "500"))


def _count(pk, hours):
    """Atomic counter in the whatsapp table (expires on its own). Returns the new value."""
    resp = store.table("whatsapp").update_item(
        Key={"pk": pk}, UpdateExpression="ADD n :one SET #t = if_not_exists(#t, :ttl)",
        ExpressionAttributeNames={"#t": "ttl"},
        ExpressionAttributeValues={":one": 1, ":ttl": int(time.time()) + hours * 3600}, ReturnValues="UPDATED_NEW")
    return int(resp["Attributes"]["n"])


def take_send_quota(phone):
    """Spend one unsolicited message to this number; False when over the hourly or daily limit."""
    hour, day = time.strftime("%Y%m%d%H", time.gmtime()), time.strftime("%Y%m%d", time.gmtime())
    ok = _count(f"rate#{msisdn(phone)}#{hour}", 2) <= PER_NUMBER_PER_HOUR and _count(f"rate#all#{day}", 48) <= PER_DAY
    if not ok:
        log("WARN", "whatsapp_rate_limited", to=mask(phone))
    return ok


def deliverable(phone):
    """Could this be a real WhatsApp number? South African numbers must be mobiles (06x/07x/08x); the demo
    fleet and tests use 000-prefixed numbers, which never are, so they are never messaged for real."""
    d = msisdn(phone)
    return bool(d) and (not d.startswith("27") or (len(d) == 11 and d[2] in "678"))


def contact_delivery(phone):
    """How alerts to this number are delivered: real WhatsApp, or recorded as simulated."""
    return "whatsapp" if deliverable(phone) and whatsapp_enabled() else "simulated"


OPS_KEY = {"pk": "config#ops"}
_ops_cache = {}  # {"item": dict, "at": epoch}; the switch is read at most every OPS_CACHE_S per Lambda container
OPS_CACHE_S = 20


def ops_item(fresh=False):
    """The operator settings item (Fleet page): wait window, WhatsApp switch. Cached briefly."""
    if fresh or time.time() - _ops_cache.get("at", 0) > OPS_CACHE_S:
        _ops_cache.update(item=store.get("whatsapp", OPS_KEY) or {}, at=time.time())
    return _ops_cache["item"]


def whatsapp_paused():
    """The operator switched WhatsApp off on the Fleet page: no WhatsApp sends, links, prompts or replies."""
    return ops_item().get("whatsapp_enabled") is False


def whatsapp_configured():
    return bool(os.environ.get("WHATSAPP_FUNCTION"))


def whatsapp_enabled():
    """Real WhatsApp can be used: the gateway is configured and the operator hasn't paused it."""
    return whatsapp_configured() and not whatsapp_paused()


def send_whatsapp(chat_id, text):
    """Queue a WhatsApp message. Returns a delivery status string."""
    if whatsapp_paused():
        log("INFO", "whatsapp_paused", chat=mask(chat_id))
        return "paused"
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
    elif whatsapp_paused():
        record.update(channel="whatsapp", status="paused")
    elif contact_delivery(phone) == "whatsapp":
        status = send_whatsapp(f"{msisdn(phone)}@c.us", text) if take_send_quota(phone) else "rate_limited"
        record.update(channel="whatsapp", status=status)
    else:
        record.update(channel="whatsapp", status="simulated")
    kind = {"simulated": "simulated", "rate_limited": "rate_limited", "no_contact_set": "none",
            "paused": "paused"}.get(record["status"], "whatsapp")
    health.record({f"contact_{kind}": 1})
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
