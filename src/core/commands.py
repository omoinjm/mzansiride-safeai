"""WhatsApp conversation logic, channel-agnostic: used by the real OpenWA webhook and the web simulator.

handle(text, chat_id) -> list of reply strings.
"""
import re

from . import assistant, drivers, trips
from .log import log

MENU = (
    "👋 *MzansiRide SafeAI*\n"
    "*CHECK* + plate: check a driver\n"
    "*TRIP* + code: get check-ins here\n"
    "*SOS*: alert your trusted contact\n"
    "Or just tell me what's wrong.\n"
    "Danger? Call *10111*. (demo)"
)

GREETINGS = {"hi", "hello", "hey", "help", "menu", "start", "sawubona", "dumela", "hallo", "molo", "howzit"}


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower().replace("’", "'")).strip(" .!")


def handle(text, chat_id):
    t = _norm(text)
    if not t:
        return ["I can only read text. Send *HELP* for the menu."]
    link = trips.chat_link(chat_id)
    pending = link.get("pending_event_id") if link else None

    # An open check-in takes priority: a stressed passenger typing "help" must escalate, not get a menu.
    # Anything typed while a check-in is open is read as the answer (1/2, or their own words via the AI).
    if pending and not (t in GREETINGS - {"help"} or re.match(r"^(check|verify|driver|plate|trip|link)\s", t)
                        or t in ("status", "sos", "stop", "unlink")):
        r = trips.reply(link["trip_id"], pending, text, channel="whatsapp")
        if r["intent"] == "ok":
            heard = "" if r["source"] == "rules" else f" (_{r['reason']}_)"
            return [f"👍 Glad you're safe{heard}. Alert closed."]
        if r["intent"] == "help":
            n = (r["event"].get("notifications") or [{}])[-1]
            return [f"🚨 Alerting {n.get('to_name', 'your contact')} and our safety team now.\nDanger? Call *10111*."]
        return ["Reply *1* = Safe   *2* = Help"]

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
            return [f"❌ {e}. Check the code in the app."]
        d = trip["driver"]
        mode = "ON ✅" if trip.get("safe_mode") else "OFF (turn it on in the app for check-ins)"
        return [f"🔗 Linked to trip *{trip['trip_id']}* ({trip['destination_name']}).\n"
                f"Car: *{d['plate']}*, {d['colour']} {d['vehicle']}. Check it matches before you get in."
                + ("" if trip.get("safe_mode") else "\nTurn on Safe Journey in the app for check-ins.")]

    if t in ("stop", "unlink"):
        trips.unlink_chat(chat_id)
        return ["Unlinked. No more check-ins here."]

    if t == "status":
        if not link:
            return ["No trip linked. Send *TRIP* + the code from the app."]
        trip = trips.get_trip(link["trip_id"])
        open_n = sum(1 for e in trips.list_events(trip["trip_id"]) if e["status"] == trips.OPEN)
        return [f"Trip *{trip['trip_id']}*: {trip['status'].replace('_', ' ')}. "
                f"Safe Journey {'on' if trip.get('safe_mode') else 'off'}. Open check-ins: {open_n}."]

    if t == "sos":
        if not link:
            return ["🚨 In danger? Call *10111* now.\nSend *TRIP* + code so SOS can alert your contact."]
        ev = trips.sos(link["trip_id"], channel="whatsapp")
        n = ev["notifications"][0]
        if n["status"] == "no_contact_set":
            return ["🚨 SOS recorded, but no trusted contact is set. Call *10111* now."]
        return [f"🚨 SOS sent to {n['to_name']}. Danger? Call *10111* now."]

    if t in ("1", "2"):
        return ["No open check-in. Send *HELP* for the menu."]

    trip = trips.get_trip(link["trip_id"]) if link else None
    reply = assistant.chat(text, trip=trip, channel="whatsapp")
    log("INFO", "assistant_reply", channel="whatsapp", source=reply["source"])
    return [reply["text"]]
