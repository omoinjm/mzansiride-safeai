"""AI safety assistant on Amazon Bedrock (proposal 5.5 and 6).

- The rules engine decides THAT something happened, and the model only explains it and lists the options.
- The model is grounded in guidance.md ("approved information") via the system prompt.
- Optional Bedrock Guardrail (GUARDRAIL_ID / GUARDRAIL_VERSION env) filters harmful content.
- If the primary model is refused (e.g. model access not granted yet), MODEL_FALLBACK_ID (Amazon Nova) is tried.
- If Bedrock is unavailable, a deterministic fallback text is returned and labelled as such,
  so the safety workflow never depends on the AI being up.
"""
import json
import os
import re
import time
from pathlib import Path

from . import health, rules
from .log import log

GUIDANCE = (Path(__file__).parent / "guidance.md").read_text()
MODEL_ID = os.environ.get("MODEL_ID", "eu.anthropic.claude-haiku-5-5")
MODEL_FALLBACK_ID = os.environ.get("MODEL_FALLBACK_ID", "eu.amazon.nova-lite-v1:0")
# Errors that mean "this model can't be used here", not "Bedrock is down": try the fallback model.
_MODEL_REFUSED = {"AccessDeniedException", "ResourceNotFoundException", "ValidationException"}
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "500"))

SYSTEM_PROMPT = f"""You are the MzansiRide SafeAI safety assistant inside a ride-sharing prototype for South Africa.
You help passengers understand safety alerts and their options during a trip.

Rules you must always follow:
- Use ONLY the approved guidance below for facts about the app, procedures and phone numbers. Never invent phone numbers, features or policies.
- An alert is a check-in prompt, not proof of danger. Never accuse or blame the driver, never speculate about criminal intent, never predict crime, and never claim to know whether the passenger is safe.
- Mention possible harmless reasons briefly and neutrally, then focus on the passenger's options.
- If the passenger says they are in danger, are being threatened, or are hurt: tell them first to call 10111 or 112, and to press "I need help" (or send SOS on WhatsApp) so their trusted contact is alerted. Keep it short.
- You do not replace emergency services, and you cannot call anyone yourself.
- Be warm, calm and brief. Use plain English that a stressed person can read in 10 seconds. You may add a short phrase in isiZulu, Sesotho or Afrikaans only if the passenger writes in that language.
- Off-topic requests: politely say you can only help with trip safety and the app.
- Trips, drivers and alerts in this prototype are simulated demo data. Say so if asked.

<approved_guidance>
{GUIDANCE}
</approved_guidance>"""

CHANNEL_STYLE = {
    "web": "Format: at most 60 words. Start with the single most important action in bold, then up to 3 short bullet "
           "points. Markdown bold is allowed. The reader may be scared and in a moving car: be brief.",
    "whatsapp": "Format: a WhatsApp message of at most 35 words, in 1 to 3 short lines. Start with the most important "
                "action. Plain text, *single asterisks* for bold, no headings, lists or links. The reader may be scared: be brief.",
}

_client = None


def _bedrock():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config

        _client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "eu-west-1"),
            config=Config(read_timeout=20, connect_timeout=3, retries={"max_attempts": 2, "mode": "standard"}),
        )
    return _client


def _trip_context(trip):
    if not trip:
        return "No active trip."
    d = trip.get("driver") or {}
    return (
        f"Trip {trip.get('trip_id')} from {trip.get('pickup_name')} to {trip.get('destination_name')}, "
        f"status {trip.get('status')}, Safe Journey Mode {'on' if trip.get('safe_mode') else 'off'}. "
        f"Driver {d.get('name', 'unknown')}, vehicle {d.get('vehicle', '')} {d.get('plate', '')} (demo data). "
        f"Trusted contact: {'set' if trip.get('trusted_contact') else 'not set'}."
    )


def _converse(messages, channel, system=None, max_tokens=None, guard=True):
    models = [m for m in (MODEL_ID, MODEL_FALLBACK_ID) if m]
    for i, model in enumerate(models):
        try:
            out = _converse_with(model, messages, channel, system, max_tokens, guard)
            health.record({"ai_calls": 1, "ai_via_fallback": int(i > 0)}, ai_last_model=model, ai_last_at=health._now())
            return out
        except Exception as e:
            code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if i == len(models) - 1 or code not in _MODEL_REFUSED:
                health.record({"ai_calls": 1, "ai_errors": 1}, ai_last_error=code or type(e).__name__)
                raise
            log("WARN", "bedrock_model_refused", model=model, code=code, error=str(e)[:200])


def _converse_with(model, messages, channel, system=None, max_tokens=None, guard=True):
    kwargs = {
        "modelId": model,
        "system": [{"text": system}] if system else
        [{"text": SYSTEM_PROMPT}, {"text": CHANNEL_STYLE.get(channel, CHANNEL_STYLE["web"])}],
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens or MAX_TOKENS, "temperature": 0.2},
    }
    if guard and os.environ.get("GUARDRAIL_ID"):
        kwargs["guardrailConfig"] = {
            "guardrailIdentifier": os.environ["GUARDRAIL_ID"],
            "guardrailVersion": os.environ.get("GUARDRAIL_VERSION", "DRAFT"),
        }
    started = time.time()
    resp = _bedrock().converse(**kwargs)
    text = "".join(c.get("text", "") for c in resp["output"]["message"]["content"]).strip()
    usage = resp.get("usage", {})
    log("INFO", "bedrock", model=model, channel=channel, stop=resp.get("stopReason"),
        ms=round((time.time() - started) * 1000), in_tokens=usage.get("inputTokens"),
        out_tokens=usage.get("outputTokens"))
    source = "guardrail" if resp.get("stopReason") == "guardrail_intervened" else "bedrock"
    return {"text": text, "source": source, "model": model}


def fallback_explanation(event):
    return (
        f"{rules.describe(event)} This can have a normal reason, like traffic or a road closure. "
        "Please check in: tap \"I'm OK\" if all is well, or \"I need help\" to alert your trusted contact. "
        "If you are in danger, call 10111 or 112."
    )


def explain_event(event, trip=None, channel="web"):
    prompt = (
        f"Safety alert raised by the rules engine: {event['type']}. Facts: {rules.describe(event)} "
        f"Details: {event.get('details')}. Context: {_trip_context(trip)}\n"
        "Explain to the passenger in plain language why the app is asking them to check in, mention that "
        "there may be a normal reason, and list their options in this app."
    )
    try:
        return _converse([{"role": "user", "content": [{"text": prompt}]}], channel)
    except Exception as e:  # never let the AI break the safety workflow
        log("WARN", "bedrock_fallback", error=str(e)[:300], kind="explain")
        return {"text": fallback_explanation(event), "source": "fallback", "model": None}


TRIAGE_PROMPT = """You are the fleet safety AI for MzansiRide SafeAI, an e-hailing operator's safety dashboard in South Africa.
Write ONE sentence (at most 30 words) telling the fleet manager what to do next about this trip.
Rules: start with the trip code; state the facts neutrally; recommend a concrete operator action (call the passenger,
call the driver, contact the trusted contact, escalate to SAPS on 10111 if the passenger is unreachable or asked for help).
Never accuse the driver or speculate about crime. The safety score is context, not evidence. Plain text only."""

TRIAGE_REASONS = {
    "passenger_help": "the passenger replied that they need help",
    "no_response": "the passenger did not answer the check-in",
    "passenger_sos": "the passenger pressed SOS",
}


def _triage_facts(trip, event, reason):
    d = trip.get("driver") or {}
    pos = trip.get("last_position") or {}
    return (
        f"Trip {trip['trip_id']} ({trip.get('pickup_name')} to {trip.get('destination_name')}). "
        f"Alert: {rules.describe(event) if event.get('type') in ('PROLONGED_STOP', 'ROUTE_DEVIATION') else event.get('type')}. "
        f"Escalated because {TRIAGE_REASONS.get(reason, reason)}. "
        f"Check-in channel: {'WhatsApp' if trip.get('wa_chat_id') else 'app only'}. "
        f"Driver {d.get('name')}, safety score {d.get('safety_score', 'n/a')}/100, rating {d.get('rating')}, "
        f"registry status {d.get('status')}, start-of-ride Face ID check "
        f"{(trip.get('driver_check') or {}).get('status', 'not done')} (simulated). "
        f"Last speed {pos.get('speed_kmh', 'unknown')} km/h. "
        f"Trusted contact {'notified' if trip.get('trusted_contact') else 'not set'}."
    )


def fallback_triage(trip, event, reason):
    what = rules.describe(event) if event.get("type") in ("PROLONGED_STOP", "ROUTE_DEVIATION") else "SOS received."
    return (f"Trip {trip['trip_id']}: {what.rstrip('.')}; {TRIAGE_REASONS.get(reason, reason)}. "
            "Call the passenger and driver now; if unreachable, escalate to SAPS (10111).")


def triage(trip, event, reason):
    """One-sentence next action for the operator when an alert escalates (shown on the fleet dashboard)."""
    facts = _triage_facts(trip, event, reason)
    try:
        return _converse([{"role": "user", "content": [{"text": facts}]}], "triage",
                         system=TRIAGE_PROMPT, max_tokens=120)
    except Exception as e:
        log("WARN", "bedrock_fallback", error=str(e)[:300], kind="triage")
        return {"text": fallback_triage(trip, event, reason), "source": "fallback", "model": None}


# ---------- passenger replies to a check-in, in their own words ----------

CHECKIN_REPLY_PROMPT = """A ride-share passenger was asked "Are you safe?" after a safety alert on their trip.
Classify their reply. Answer with JSON only: {"intent": "ok" | "help" | "unclear", "reason": "<max 12 words>"}
- "ok": they clearly say they are safe or explain a harmless reason (detour, traffic, fuel, stopping for a friend).
- "help": any sign of danger, fear, threat, injury, being held, the driver refusing to stop, or a request for help.
- "unclear": anything else, mixed signals, jokes, or not about their safety.
When in doubt between ok and anything else, choose "unclear". Never guess "ok"."""

# Deterministic guard rails around the model: obvious danger is "help" without asking the AI, and the
# model can never turn a reply containing these words into "ok".
DANGER = re.compile(r"\b(help|knife|gun|weapon|scared|afraid|hurt|attack|rape|kidnap|locked|won'?t (stop|let)|"
                    r"not safe|unsafe|danger|threat|police|emergency|sos)\b")
OK_EXACT = {"1", "ok", "okay", "im ok", "i'm ok", "i am ok", "fine", "safe", "yes", "all good", "im fine", "i'm fine"}
HELP_EXACT = {"2", "need help", "i need help", "help me", "not ok", "no", "help"}


def classify_checkin_reply(text, trip=None, event=None):
    """{"intent": ok|help|unclear, "reason", "source", "model"}. Unclear never closes an alert."""
    t = re.sub(r"\s+", " ", (text or "").strip().lower().replace("’", "'")).strip(" .!")
    if t in HELP_EXACT or DANGER.search(t):
        return {"intent": "help", "reason": "asked for help" if t in HELP_EXACT else "mentions danger",
                "source": "rules", "model": None}
    if t in OK_EXACT:
        return {"intent": "ok", "reason": "said they are OK", "source": "rules", "model": None}
    alert = rules.describe(event) if event and event.get("type") in ("PROLONGED_STOP", "ROUTE_DEVIATION") else ""
    try:
        out = _converse([{"role": "user", "content": [{"text": f"Alert: {alert}\nPassenger reply: {text[:500]}"}]}],
                        "checkin_reply", system=CHECKIN_REPLY_PROMPT, max_tokens=80)
        data = json.loads(re.search(r"\{.*\}", out["text"], re.S).group(0))
        intent = data.get("intent") if data.get("intent") in ("ok", "help", "unclear") else "unclear"
        return {"intent": intent, "reason": str(data.get("reason") or "")[:100], "source": out["source"],
                "model": out["model"]}
    except Exception as e:
        log("WARN", "checkin_reply_unclassified", error=str(e)[:200])
        return {"intent": "unclear", "reason": "could not understand the reply", "source": "fallback", "model": None}


# ---------- number plate from a photo ----------

PLATE_PROMPT = """You read vehicle number plates from photos for a ride-share safety check in South Africa.
Reply with ONLY the registration text on the plate exactly as written (letters, digits, spaces, hyphens),
e.g. "CA 123-456" or "JK 45 PL GP". If no plate is clearly readable, reply NONE.
Do not describe people or anything else in the image."""
IMAGE_FORMATS = {"image/jpeg": "jpeg", "image/jpg": "jpeg", "image/png": "png", "image/webp": "webp"}


def read_plate(image_bytes, mime):
    """{"plate": str|None, "source", "model"}. The image is sent to Bedrock and never stored."""
    fmt = IMAGE_FORMATS.get((mime or "").lower())
    if not fmt:
        raise ValueError("Send a JPEG, PNG or WebP photo")
    msgs = [{"role": "user", "content": [{"image": {"format": fmt, "source": {"bytes": image_bytes}}},
                                         {"text": "What does the number plate say?"}]}]
    try:
        # No Guardrail here: it filters text, and the prompt only asks for plate characters.
        out = _converse(msgs, "plate_photo", system=PLATE_PROMPT, max_tokens=30, guard=False)
    except Exception as e:
        log("WARN", "bedrock_fallback", error=str(e)[:300], kind="plate_photo")
        return {"plate": None, "source": "fallback", "model": None}
    text = out["text"].strip().strip('"').upper()
    plate = None if not text or "NONE" in text or len(text) > 16 else text
    return {"plate": plate, "source": out["source"], "model": out["model"]}


def chat(message, trip=None, history=None, channel="web"):
    message = (message or "").strip()[:1000]
    msgs = []
    for turn in (history or [])[-6:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = str(turn.get("text", ""))[:1000]
        if not text:
            continue
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"][0]["text"] += "\n" + text
        else:
            msgs.append({"role": role, "content": [{"text": text}]})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    user_text = f"[Context: {_trip_context(trip)}]\n{message}"
    if msgs and msgs[-1]["role"] == "user":
        msgs[-1]["content"][0]["text"] += "\n" + user_text
    else:
        msgs.append({"role": "user", "content": [{"text": user_text}]})
    try:
        return _converse(msgs, channel)
    except Exception as e:
        log("WARN", "bedrock_fallback", error=str(e)[:300], kind="chat")
        return {
            "text": "Sorry, the AI assistant is unavailable right now. If you are in danger call 10111 or 112. "
                    "You can still use the check-in buttons and Share trip.",
            "source": "fallback",
            "model": None,
        }
