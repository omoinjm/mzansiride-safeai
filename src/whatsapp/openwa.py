"""Minimal OpenWA (github.com/rmyndharis/OpenWA) REST client + webhook signature check.

Credentials live in SSM Parameter Store (SecureString) under OPENWA_PARAM_PREFIX:
  base_url, api_key, session_id, webhook_secret
They are read once per Lambda container.
"""
import hashlib
import hmac
import json
import os
import urllib.request

_params = None


def params():
    global _params
    if _params is None:
        import boto3

        prefix = os.environ.get("OPENWA_PARAM_PREFIX", "/mzansiride/openwa/")
        resp = boto3.client("ssm").get_parameters_by_path(Path=prefix, WithDecryption=True)
        _params = {p["Name"][len(prefix):]: p["Value"] for p in resp["Parameters"]}
    return _params


def verify_signature(raw_body: bytes, header: str, secret: str) -> bool:
    """X-OpenWA-Signature: sha256=<hex HMAC-SHA256 of the raw body>."""
    if not secret or not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.strip())


def send_text(chat_id: str, text: str) -> dict:
    p = params()
    url = f"{p['base_url'].rstrip('/')}/api/sessions/{p['session_id']}/messages/send-text"
    req = urllib.request.Request(
        url,
        data=json.dumps({"chatId": chat_id, "text": text}).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": p["api_key"]},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read() or b"{}")
