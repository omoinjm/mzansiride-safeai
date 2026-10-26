"""System health for the Fleet page: is WhatsApp working, which AI model is answering, what was sent today,
and how many Lambda errors in the last hour. Counts and status only, never raw logs or phone numbers.

Recording is best-effort: a failed health write must never break a check-in or an alert.
"""
import os
import time
import urllib.request

from . import store
from .log import log

STATE = "health#state"
RECENT_S = 15 * 60  # a gateway failure older than this (with no send since) no longer marks WhatsApp degraded


def _day():
    return "health#" + time.strftime("%Y%m%d", time.gmtime())


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def record(counts=None, **last):
    """Add to today's counters and/or set "last seen" fields, e.g. record({"wa_sent": 1}, wa_last_sent_at=...)."""
    try:
        t = store.table("whatsapp")
        if counts:
            names = {f"#c{i}": k for i, k in enumerate(counts)}
            vals = {f":c{i}": v for i, v in enumerate(counts.values())}
            t.update_item(Key={"pk": _day()},
                          UpdateExpression="ADD " + ", ".join(f"#c{i} :c{i}" for i in range(len(counts)))
                          + " SET #ttl = if_not_exists(#ttl, :ttl)",
                          ExpressionAttributeNames={**names, "#ttl": "ttl"},
                          ExpressionAttributeValues={**vals, ":ttl": store.ttl_days(3)})
        if last:
            names = {f"#s{i}": k for i, k in enumerate(last)}
            vals = {f":s{i}": str(v)[:200] for i, v in enumerate(last.values())}
            t.update_item(Key={"pk": STATE}, UpdateExpression="SET " + ", ".join(f"#s{i} = :s{i}" for i in range(len(last))),
                          ExpressionAttributeNames=names, ExpressionAttributeValues=vals)
    except Exception as e:  # health is diagnostics only
        log("WARN", "health_record_failed", error=str(e)[:200])


def _ping_gateway():
    url = os.environ.get("OPENWA_HEALTH_URL")
    if not url:
        return None
    started = time.time()
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return {"ok": r.status == 200, "ms": round((time.time() - started) * 1000)}
    except Exception as e:
        return {"ok": False, "ms": None, "error": str(e)[:120]}


def _lambda_errors_last_hour():
    names = {"api": os.environ.get("AWS_LAMBDA_FUNCTION_NAME"), "whatsapp": os.environ.get("WHATSAPP_FUNCTION")}
    try:
        import boto3

        cw = boto3.client("cloudwatch")
        out = {}
        for key, fn in names.items():
            if not fn:
                continue
            pts = cw.get_metric_statistics(Namespace="AWS/Lambda", MetricName="Errors",
                                           Dimensions=[{"Name": "FunctionName", "Value": fn}],
                                           StartTime=time.time() - 3600, EndTime=time.time(), Period=3600,
                                           Statistics=["Sum"])["Datapoints"]
            out[key] = int(sum(p["Sum"] for p in pts))
        return out
    except Exception as e:
        log("WARN", "health_metrics_failed", error=str(e)[:200])
        return None


def _whatsapp_status(state, ping):
    from . import notify

    if notify.whatsapp_paused():
        return "paused", "WhatsApp is switched off on the Fleet page."
    if not os.environ.get("WHATSAPP_FUNCTION"):
        return "not_configured", "WhatsApp isn't connected in this environment (the simulator is used)."
    if ping and not ping["ok"]:
        return "down", "The WhatsApp gateway isn't answering. Check the EC2 instance, then run make wa-status."
    last_ok, last_err = state.get("wa_last_sent_at", ""), state.get("wa_last_error_at", "")
    recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - RECENT_S))
    if last_err and last_err > last_ok and last_err >= recent:
        return "degraded", "The last send failed. If it keeps failing, run make wa-restart (keeps the login)."
    return "ok", "Sending and receiving normally."


def snapshot():
    from . import assistant  # model names

    day = store.get("whatsapp", {"pk": _day()}) or {}
    state = store.get("whatsapp", {"pk": STATE}) or {}
    n = lambda k: int(day.get(k) or 0)  # noqa: E731
    ping = _ping_gateway()
    status, advice = _whatsapp_status(state, ping)
    calls = n("ai_calls")
    return {
        "checked_at": _now(),
        "whatsapp": {
            "status": status, "advice": advice, "gateway": ping,
            "last_sent_at": state.get("wa_last_sent_at"), "last_received_at": state.get("wa_last_inbound_at"),
            "last_error_at": state.get("wa_last_error_at"), "last_error": state.get("wa_last_error"),
        },
        "ai": {
            "primary_model": assistant.MODEL_ID, "fallback_model": assistant.MODEL_FALLBACK_ID,
            "last_model": state.get("ai_last_model"), "last_at": state.get("ai_last_at"),
            "calls_today": calls, "via_fallback_model": n("ai_via_fallback"), "rules_fallback": n("ai_errors"),
            "status": "ok" if calls == 0 or n("ai_errors") < max(1, calls // 5) else "degraded",
        },
        "messages_today": {
            "whatsapp_sent": n("wa_sent"), "whatsapp_failed": n("wa_failed"), "whatsapp_received": n("wa_received"),
            "whatsapp_undeliverable": n("wa_undeliverable"),
            "sms_sent": n("sms_sent"), "sms_failed": n("sms_failed"),
            "contact_alerts_whatsapp": n("contact_whatsapp"), "contact_alerts_simulated": n("contact_simulated"),
            "contact_alerts_rate_limited": n("contact_rate_limited"),
        },
        "errors_last_hour": _lambda_errors_last_hour(),
        "dashboard_url": os.environ.get("DASHBOARD_URL"),
    }
