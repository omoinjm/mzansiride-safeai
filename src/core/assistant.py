"""AI safety assistant on Amazon Bedrock (proposal 5.5 and 6).

- The rules engine decides THAT something happened, and the model only explains it and lists the options.
- The model is grounded in guidance.md ("approved information") via the system prompt.
- Optional Bedrock Guardrail (GUARDRAIL_ID / GUARDRAIL_VERSION env) filters harmful content.
- If the primary model is refused (e.g. model access not granted yet), MODEL_FALLBACK_ID (Amazon Nova) is tried.
- If Bedrock is unavailable, a deterministic fallback text is returned and labelled as such,
  so the safety workflow never depends on the AI being up.
"""
import os
import time
from pathlib import Path

from . import rules
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
    "web": "Format: at most 120 words. Use short paragraphs or up to 4 bullet points. Markdown bold is allowed.",
    "whatsapp": "Format: this is a WhatsApp message. At most 90 words, plain text, use *single asterisks* for bold, no markdown headings or links.",
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


def _converse(messages, channel):
    models = [m for m in (MODEL_ID, MODEL_FALLBACK_ID) if m]
    for i, model in enumerate(models):
        try:
            return _converse_with(model, messages, channel)
        except Exception as e:
            code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if i == len(models) - 1 or code not in _MODEL_REFUSED:
                raise
            log("WARN", "bedrock_model_refused", model=model, code=code, error=str(e)[:200])


def _converse_with(model, messages, channel):
    kwargs = {
        "modelId": model,
        "system": [{"text": SYSTEM_PROMPT}, {"text": CHANNEL_STYLE.get(channel, CHANNEL_STYLE["web"])}],
        "messages": messages,
        "inferenceConfig": {"maxTokens": MAX_TOKENS, "temperature": 0.2},
    }
    if os.environ.get("GUARDRAIL_ID"):
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
