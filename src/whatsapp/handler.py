"""WhatsApp channel (OpenWA gateway).

Two entry points in one function:
1. HTTP webhook from OpenWA (POST /whatsapp/webhook): verify the HMAC signature, drop duplicates,
   then hand the message to an async invocation of this same function and answer 200 at once.
   OpenWA times out webhooks after 10 s and retries; Bedrock can take a few seconds.
2. Async actions (invoked by this function or the API Lambda):
   {"action": "process", "chat_id", "text"}      run the command/assistant logic and reply
   {"action": "send", "chat_id", "text"}         send one message
   {"action": "checkin_prompt", "trip_id", "event_id"}   AI-explained check-in prompt to the linked chat
   {"action": "photo", "chat_id", "image"?, "mime"?}       plate photo -> registry check (image only if inline)
"""
import base64
import json
import time
import urllib.error

import boto3

from core import commands, drivers, health, notify, store, trips
from core.log import log
from whatsapp import openwa


def _ok(body=None, status=200):
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body or {"ok": True})}


# WhatsApp's privacy IDs: incoming chats can arrive as "<lid>@lid" instead of "<phone>@c.us". Trips are linked
# to "<phone>@c.us" when the passenger gives their number at booking, so incoming @lid chats are mapped back
# to the phone chat: from a phone field in the webhook if OpenWA sends one, else from a mapping we learn when
# a send to "<phone>@c.us" comes back with a "<lid>@lid" message id.
PHONE_FIELDS = ("phone", "senderPhone", "fromPhone", "phoneNumber")


def _remember_lid(chat_id, resp):
    msg_id = str((resp or {}).get("messageId") or (resp or {}).get("id") or "")
    if chat_id.endswith("@c.us") and "@lid" in msg_id:
        lid = msg_id.split("@lid")[0].split("_")[-1]
        store.put("whatsapp", {"pk": f"lid#{lid}", "chat": chat_id, "ttl": store.ttl_days(30)})


def _phone_chat(chat_id, data):
    if not chat_id or not chat_id.endswith("@lid"):
        return chat_id
    contact = data.get("contact") or data.get("sender") or {}
    for field in PHONE_FIELDS:
        phone = notify.msisdn(str(data.get(field) or contact.get(field) or contact.get("number") or ""))
        if phone:
            return f"{phone}@c.us"
    known = store.get("whatsapp", {"pk": f"lid#{chat_id.split('@')[0]}"})
    return known["chat"] if known else chat_id


MAX_INLINE_IMAGE = 240_000  # async Lambda payloads are capped at 256 KB


def _inline_image(data):
    """(base64, mime) if the webhook carries the image itself, else (None, None)."""
    media = data.get("media") if isinstance(data.get("media"), dict) else {}
    b64 = media.get("data") or data.get("mediaData") or data.get("base64")
    mime = media.get("mimetype") or data.get("mimetype") or data.get("mediaMimetype") or "image/jpeg"
    if isinstance(b64, str) and b64.startswith("data:"):
        mime, b64 = b64[5:].split(";", 1)[0], b64.split(",", 1)[-1]
    return (b64, mime) if isinstance(b64, str) and 0 < len(b64) <= MAX_INLINE_IMAGE else (None, None)


def _send(chat_id, text):
    try:
        _remember_lid(chat_id, openwa.send_text(chat_id, text))
        health.record({"wa_sent": 1}, wa_last_sent_at=health._now())
        log("INFO", "whatsapp_sent", chat=notify.mask(chat_id), chars=len(text))
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500:
            # The gateway is fine; this recipient can't be reached (e.g. the number isn't on WhatsApp).
            health.record({"wa_undeliverable": 1})
            log("WARN", "whatsapp_undeliverable", chat=notify.mask(chat_id), error=str(e)[:200])
            return
        _gateway_failed(chat_id, e)
        raise
    except Exception as e:
        _gateway_failed(chat_id, e)
        raise


def _gateway_failed(chat_id, e):
    health.record({"wa_failed": 1}, wa_last_error_at=health._now(), wa_last_error=type(e).__name__ + ": " + str(e)[:100])
    log("ERROR", "whatsapp_send_failed", chat=notify.mask(chat_id), error=str(e)[:300])


def handle_action(event):
    action = event["action"]
    if action == "send":
        _send(event["chat_id"], event["text"])
    elif action == "checkin_prompt":
        trip = trips.get_trip(event["trip_id"])
        if trip.get("wa_chat_id"):
            _send(trip["wa_chat_id"], trips.whatsapp_prompt_text(event["trip_id"], event["event_id"]))
    elif action == "photo":
        if not event.get("image"):
            _send(event["chat_id"], "📷 I can't read photos on WhatsApp yet. Type the plate instead: *CHECK CA 123-456*, "
                                    "or use *Check plate from a photo* in the MzansiRide app.")
        else:
            r = drivers.photo_check(base64.b64decode(event["image"]), event.get("mime") or "image/jpeg")
            _send(event["chat_id"], (f"📷 I read the plate as *{r['plate']}*.\n\n" + drivers.format_lookup(r["lookup"]))
                  if r["plate"] else r["advice"])
            log("INFO", "plate_photo", read=bool(r["plate"]), channel="whatsapp")
    elif action == "process":
        started = time.time()
        replies = commands.handle(event["text"], event["chat_id"])
        for r in replies:
            _send(event["chat_id"], r)
        log("INFO", "whatsapp_processed", chat=notify.mask(event["chat_id"]), ms=round((time.time() - started) * 1000))
    return {"ok": True}


def handle_webhook(event, context):
    raw = event.get("body") or ""
    raw_bytes = base64.b64decode(raw) if event.get("isBase64Encoded") else raw.encode()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if not openwa.verify_signature(raw_bytes, headers.get("x-openwa-signature", ""), openwa.params().get("webhook_secret", "")):
        log("WARN", "webhook_bad_signature")
        return _ok({"error": "bad signature"}, 401)

    payload = json.loads(raw_bytes or b"{}")
    if payload.get("event") != "message.received":
        if payload.get("event", "").startswith("session."):
            log("INFO", "openwa_session", kind=payload.get("event"), status=(payload.get("data") or {}).get("status"))
        return _ok()
    data = payload.get("data") or {}
    if data.get("fromMe") or data.get("isGroup") or data.get("kind", "individual") != "individual":
        return _ok()
    raw_chat = data.get("chatId") or data.get("from")
    chat_id = _phone_chat(raw_chat, data)
    if raw_chat != chat_id or raw_chat.endswith("@lid"):
        log("INFO", "webhook_lid", mapped=raw_chat != chat_id, keys=sorted(data))
    text = data.get("body") if data.get("type", "text") == "text" else ""
    if data.get("type") == "image":
        image, mime = _inline_image(data)
        log("INFO", "webhook_image", keys=sorted(data), inline=bool(image))
        key = payload.get("idempotencyKey") or data.get("id")
        if key and not store.put_once("whatsapp", {"pk": f"dedupe#{key}", "ttl": store.ttl_days(1)}):
            return _ok()
        boto3.client("lambda").invoke(
            FunctionName=context.function_name, InvocationType="Event",
            Payload=json.dumps({"action": "photo", "chat_id": chat_id, "image": image, "mime": mime}).encode())
        return _ok()

    key = payload.get("idempotencyKey") or data.get("id")
    if key and not store.put_once("whatsapp", {"pk": f"dedupe#{key}", "ttl": store.ttl_days(1)}):
        log("INFO", "webhook_duplicate")
        return _ok()

    boto3.client("lambda").invoke(
        FunctionName=context.function_name,
        InvocationType="Event",
        Payload=json.dumps({"action": "process", "chat_id": chat_id, "text": text or ""}).encode(),
    )
    health.record({"wa_received": 1}, wa_last_inbound_at=health._now())
    log("INFO", "webhook_received", chat=notify.mask(chat_id), type=data.get("type"))
    return _ok()


def handler(event, context):
    if "action" in event:
        return handle_action(event)
    return handle_webhook(event, context)
