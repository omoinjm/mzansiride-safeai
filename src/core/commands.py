"""WhatsApp conversation logic, channel-agnostic: used by the real OpenWA webhook and the web simulator.

handle(text, chat_id) -> list of reply strings.
"""
import re

from . import assistant, drivers, trips
from .log import log

MENU = (
    "👋 *MzansiRide SafeAI*: travel safety on WhatsApp, no app or mobile data bundle needed.\n\n"
    "*CHECK <plate or name>*: look up a driver, e.g. CHECK CA 123-456\n"
    "*TRIP <code>*: link this chat to your trip for safety check-ins\n"
    "*STATUS*: your linked trip\n"
    "*SOS*: alert your trusted contact now\n"
    "*1* / *2*: answer a check-in (OK / need help), or just tell me what's happening\n"
    "Or just describe your situation and our AI safety assistant will guide you.\n\n"
    "In danger? Call *10111* or *112*. (Prototype: simulated trips and drivers.)"
)

GREETINGS = {"hi", "hello", "hey", "help", "menu", "start", "sawubona", "dumela", "hallo", "molo", "howzit"}


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower().replace("’", "'")).strip(" .!")


def handle(text, chat_id):
    t = _norm(text)
    if not t:
        return ["Sorry, I can only read text messages for now. Send *HELP* for the menu."]
    link = trips.chat_link(chat_id)
    pending = link.get("pending_event_id") if link else None

    # An open check-in takes priority: a stressed passenger typing "help" must escalate, not get a menu.
    # Anything typed while a check-in is open is read as the answer (1/2, or their own words via the AI).
    if pending and not (t in GREETINGS - {"help"} or re.match(r"^(check|verify|driver|plate|trip|link)\s", t)
                        or t in ("status", "sos", "stop", "unlink")):
        r = trips.reply(link["trip_id"], pending, text, channel="whatsapp")
        if r["intent"] == "ok":
            heard = "" if r["source"] == "rules" else f"Got it: _{r['reason']}_. "
            return [f"👍 {heard}Glad you're OK. The alert is closed. I'll keep watching the trip."]
        if r["intent"] == "help":
            n = (r["event"].get("notifications") or [{}])[-1]
            return [f"🚨 Understood. Your trusted contact ({n.get('to_name', 'contact')}) and our safety team are "
                    "being alerted with your trip and last location.\nIf you are in danger call *10111* or *112* now. "
                    "If it's safe, ask to stop at a busy public place."]
        return ["Just to be sure: reply *1* if you're safe, or *2* if you need help. "
                "If we don't hear back, your trusted contact will be alerted."]

    if t in GREETINGS:
        return [MENU]

    m = re.match(r"^(check|verify|driver|plate)\s+(.+)$", t)
    if m:
        result = drivers.lookup(m.group(2))
        log("INFO", "driver_lookup", verdict=result["verdict"], channel="whatsapp")
        return [drivers.format_lookup(result)]

    m = re.match(r"^(trip|link)\s+([a-z0-9]{4,8})$", t)
    if m:
        try:
            trip = trips.link_chat(chat_id, m.group(2).upper())
        except (trips.NotFound, trips.BadRequest) as e:
            return [f"❌ {e}. Check the trip code shown in the MzansiRide app."]
        d = trip["driver"]
        mode = "ON ✅" if trip.get("safe_mode") else "OFF (turn it on in the app for check-ins)"
        return [
            f"🔗 Linked to trip *{trip['trip_id']}*\n{trip['pickup_name']} → {trip['destination_name']}\n"
            f"Driver: {d['name']}, {d['colour']} {d['vehicle']} *{d['plate']}*\nSafe Journey Mode: {mode}\n\n"
            "Before you get in, check that the plate and car match. I'll message you here if the trip stops "
            "unexpectedly or leaves the route."
        ]

    if t in ("stop", "unlink"):
        trips.unlink_chat(chat_id)
        return ["Unlinked. You won't get check-ins for that trip here anymore. Send *HELP* for the menu."]

    if t == "status":
        if not link:
            return ["No trip linked. Send *TRIP <code>* (the code is shown in the app)."]
        trip = trips.get_trip(link["trip_id"])
        open_n = sum(1 for e in trips.list_events(trip["trip_id"]) if e["status"] == trips.OPEN)
        return [f"Trip *{trip['trip_id']}*: {trip['status'].replace('_', ' ')}. Safe Journey Mode "
                f"{'on' if trip.get('safe_mode') else 'off'}. Open check-ins: {open_n}."]

    if t == "sos":
        if not link:
            return ["🚨 If you are in danger call *10111* or *112* now.\nLink your trip with *TRIP <code>* so SOS can alert your trusted contact."]
        ev = trips.sos(link["trip_id"], channel="whatsapp")
        n = ev["notifications"][0]
        sent = "notified" if n["status"] not in ("no_contact_set",) else "NOT notified (no trusted contact set)"
        return [f"🚨 SOS recorded. Your trusted contact ({n['to_name']}) has been {sent}.\n"
                "If you are in danger call *10111* or *112* now."]

    if t in ("1", "2"):
        return ["There's no open check-in right now. Send *HELP* for the menu."]

    trip = trips.get_trip(link["trip_id"]) if link else None
    reply = assistant.chat(text, trip=trip, channel="whatsapp")
    log("INFO", "assistant_reply", channel="whatsapp", source=reply["source"])
    return [reply["text"]]
