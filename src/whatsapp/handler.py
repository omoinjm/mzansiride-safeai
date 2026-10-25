"""WhatsApp channel (OpenWA gateway).

Two entry points in one function:
1. HTTP webhook from OpenWA (POST /whatsapp/webhook): verify the HMAC signature, drop duplicates,
   then hand the message to an async invocation of this same function and answer 200 at once.
   OpenWA times out webhooks after 10 s and retries; Bedrock can take a few seconds.
2. Async actions (invoked by this function or the API Lambda):
   {"action": "process", "chat_id", "text"}      run the command/assistant logic and reply
   {"action": "send", "chat_id", "text"}         send one message
   {"action": "checkin_prompt", "trip_id", "event_id"}   AI-explained check-in prompt to the linked chat
"""
import base64
import json
import time

import boto3

from core import commands, notify, store, trips
from core.log import log
from whatsapp import openwa


def _ok(body=None, status=200):
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body or {"ok": True})}


def _send(chat_id, text):
    try:
        openwa.send_text(chat_id, text)
        log("INFO", "whatsapp_sent", chat=notify.mask(chat_id), chars=len(text))
    except Exception as e:
        log("ERROR", "whatsapp_send_failed", chat=notify.mask(chat_id), error=str(e)[:300])
        raise


def handle_action(event):
    action = event["action"]
    if action == "send":
        _send(event["chat_id"], event["text"])
    elif action == "checkin_prompt":
        trip = trips.get_trip(event["trip_id"])
        if trip.get("wa_chat_id"):
            _send(trip["wa_chat_id"], trips.whatsapp_prompt_text(event["trip_id"], event["event_id"]))
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
    chat_id = data.get("chatId") or data.get("from")
    text = data.get("body") if data.get("type", "text") == "text" else ""

    key = payload.get("idempotencyKey") or data.get("id")
    if key and not store.put_once("whatsapp", {"pk": f"dedupe#{key}", "ttl": store.ttl_days(1)}):
        log("INFO", "webhook_duplicate")
        return _ok()

    boto3.client("lambda").invoke(
        FunctionName=context.function_name,
        InvocationType="Event",
        Payload=json.dumps({"action": "process", "chat_id": chat_id, "text": text or ""}).encode(),
    )
    log("INFO", "webhook_received", chat=notify.mask(chat_id), type=data.get("type"))
    return _ok()


def handler(event, context):
    if "action" in event:
        return handle_action(event)
    return handle_webhook(event, context)
