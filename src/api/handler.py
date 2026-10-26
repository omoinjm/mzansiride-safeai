"""Web JSON API (API Gateway HTTP API, payload v2) for the React app. All routes live under /api."""
import base64
import hmac
import json
import os
import re
import time
import traceback

from core import assistant, commands, drivers, health, notify, places, trips
from core.log import log

TEAM_CODE = os.environ.get("TEAM_CODE", "")


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(body, default=str),
    }


def _body(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        raise trips.BadRequest("Body must be JSON")


def _require_team_code(event):
    given = (event.get("headers") or {}).get("x-team-code", "")
    if not TEAM_CODE or not hmac.compare_digest(given.encode(), TEAM_CODE.encode()):
        raise PermissionError("Team code required")


def config(event, body):
    return {
        "whatsapp": {
            "enabled": notify.whatsapp_enabled(),
            "paused": notify.whatsapp_paused(),
            "number": os.environ.get("WA_NUMBER", ""),
        },
        "model": assistant.MODEL_ID,
        "guardrail": bool(os.environ.get("GUARDRAIL_ID")),
        "checkin_timeout_s": trips.get_ops_config()["checkin_timeout_s"],
        "region": os.environ.get("AWS_REGION"),
    }


def assistant_chat(event, body):
    trip = None
    if body.get("trip_id"):
        try:
            trip = trips.get_trip(body["trip_id"])
        except trips.NotFound:
            pass
    if not (body.get("message") or "").strip():
        raise trips.BadRequest("message is required")
    return assistant.chat(body["message"], trip=trip, history=body.get("history"), channel="web")


class Paused(Exception):
    pass


def _require_whatsapp_on():
    if notify.whatsapp_paused():
        raise Paused("WhatsApp is paused by the operator")


def wa_simulate(event, body):
    _require_whatsapp_on()
    chat = "sim:" + re.sub(r"[^a-zA-Z0-9-]", "", str(body.get("session", "")))[:40]
    if chat == "sim:":
        raise trips.BadRequest("session is required")
    replies = commands.handle(str(body.get("text", ""))[:1000], chat)
    return {"chat_id": chat, "replies": replies}


def wa_outbox(event, body):
    _require_whatsapp_on()
    qs = event.get("queryStringParameters") or {}
    chat = "sim:" + re.sub(r"[^a-zA-Z0-9-]", "", qs.get("session", ""))[:40]
    out = []
    for m in notify.sim_outbox_pop(chat):
        text = m["text"]
        if text.startswith('{"prompt"'):
            trip_id, event_id = json.loads(text)["prompt"]
            text = trips.whatsapp_prompt_text(trip_id, event_id)
        out.append({"text": text, "at": m["at"]})
    return {"messages": out}


def dashboard(event, body):
    _require_team_code(event)
    return trips.dashboard()


MAX_PHOTO_BYTES = 3 * 1024 * 1024


def photo_check(event, body):
    try:
        image = base64.b64decode(body.get("image") or "", validate=True)
    except ValueError:
        raise trips.BadRequest("image must be base64")
    if not image or len(image) > MAX_PHOTO_BYTES:
        raise trips.BadRequest("Send a photo smaller than 3 MB")
    try:
        result = drivers.photo_check(image, body.get("mime"))
    except ValueError as e:
        raise trips.BadRequest(str(e))
    log("INFO", "plate_photo", read=bool(result["plate"]), verdict=(result["lookup"] or {}).get("verdict"),
        channel="web")
    return result


def ops_health(event, body):
    _require_team_code(event)
    return health.snapshot()


def ops_config(event, body):
    _require_team_code(event)
    method = event["requestContext"]["http"]["method"]
    return trips.set_ops_config(body) if method == "PUT" else trips.get_ops_config()


def acknowledge(event, body, trip, ev):
    _require_team_code(event)
    return trips.acknowledge(trip.upper(), ev, body.get("action"))


ROUTES = [
    ("GET", r"/api/health", lambda e, b: {"ok": True, "service": "mzansiride-api"}),
    ("GET", r"/api/config", config),
    ("GET", r"/api/places", lambda e, b: {"places": places.public_places()}),
    ("POST", r"/api/quote", lambda e, b: trips.quote(b.get("pickup"), b.get("destination"))),
    ("POST", r"/api/trips", lambda e, b: trips.public_trip(trips.create_trip(b))),
    ("GET", r"/api/trips/(?P<trip>[A-Za-z0-9]+)", lambda e, b, trip: {
        **trips.public_trip(trips.get_trip(trip)), "events": trips.list_events(trip.upper())}),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/start", lambda e, b, trip: trips.public_trip(trips.start_trip(trip))),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/complete", lambda e, b, trip: trips.public_trip(trips.complete_trip(trip))),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/safe-mode",
     lambda e, b, trip: trips.public_trip(trips.set_safe_mode(trip, b.get("enabled", True)))),
    ("PUT", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/trusted-contact",
     lambda e, b, trip: trips.public_trip(trips.set_trusted_contact(trip, b))),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/telemetry", lambda e, b, trip: trips.telemetry(trip.upper(), b)),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/sos",
     lambda e, b, trip: trips.sos(trip.upper(), channel="web",
                                  reason="share_trip" if b.get("share") else "passenger_sos")),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/events/(?P<ev>[A-Za-z0-9_-]+)/checkin",
     lambda e, b, trip, ev: trips.checkin(trip.upper(), ev, b.get("response"), channel="web", prompt_ms=b.get("prompt_ms"))),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/events/(?P<ev>[A-Za-z0-9_-]+)/explain",
     lambda e, b, trip, ev: trips.explain(trip.upper(), ev, channel="web")),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/events/(?P<ev>[A-Za-z0-9_-]+)/ack", acknowledge),
    ("POST", r"/api/trips/(?P<trip>[A-Za-z0-9]+)/events/(?P<ev>[A-Za-z0-9_-]+)/reply",
     lambda e, b, trip, ev: trips.reply(trip.upper(), ev, b.get("text"), channel="web")),
    ("GET", r"/api/ops/config", ops_config),
    ("GET", r"/api/ops/health", ops_health),
    ("PUT", r"/api/ops/config", ops_config),
    ("POST", r"/api/drivers/photo-check", photo_check),
    ("GET", r"/api/drivers/lookup", lambda e, b: drivers.lookup((e.get("queryStringParameters") or {}).get("q", ""))),
    ("POST", r"/api/assistant", assistant_chat),
    ("POST", r"/api/whatsapp/simulate", wa_simulate),
    ("GET", r"/api/whatsapp/outbox", wa_outbox),
    ("GET", r"/api/dashboard", dashboard),
]


def handler(event, context):
    if event.get("action") == "health_check":  # EventBridge schedule, not HTTP
        return health.check_and_publish()
    started = time.time()
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    status = 500
    try:
        for m, pattern, fn in ROUTES:
            match = re.fullmatch(pattern, path)
            if match and m == method:
                result = fn(event, _body(event) if method in ("POST", "PUT") else {}, **match.groupdict())
                status = 200
                return _resp(200, result)
        status = 404
        return _resp(404, {"error": "Not found"})
    except trips.NotFound as e:
        status = 404
        return _resp(404, {"error": str(e)})
    except trips.BadRequest as e:
        status = 400
        return _resp(400, {"error": str(e)})
    except Paused as e:
        status = 409
        return _resp(409, {"error": str(e)})
    except PermissionError as e:
        status = 401
        return _resp(401, {"error": str(e)})
    except Exception as e:
        log("ERROR", "api_error", path=path, error=str(e), trace=traceback.format_exc()[-1500:])
        return _resp(500, {"error": "Internal error"})
    finally:
        log("INFO", "request", method=method, path=path, status=status, ms=round((time.time() - started) * 1000))
