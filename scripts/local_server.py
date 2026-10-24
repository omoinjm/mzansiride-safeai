"""Run the whole app locally: the built React app + the real API Lambda code against in-memory DynamoDB.

Uses:
  - development without AWS:          make local      (then open http://localhost:8077)
  - BACKUP DEMO if the venue Wi-Fi or AWS is down (only the map tiles need internet).

The AI assistant uses Amazon Bedrock when AWS credentials are available (--bedrock), otherwise the
built-in rules-based fallback text, which is clearly labelled in the UI.
"""
import argparse
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"
sys.path.insert(0, str(ROOT / "src"))


def setup_tables():
    import boto3

    ddb = boto3.client("dynamodb", region_name="eu-west-1")

    def mk(name, pk, sk=None):
        keys = [{"AttributeName": pk, "KeyType": "HASH"}] + ([{"AttributeName": sk, "KeyType": "RANGE"}] if sk else [])
        attrs = [{"AttributeName": pk, "AttributeType": "S"}] + ([{"AttributeName": sk, "AttributeType": "S"}] if sk else [])
        ddb.create_table(TableName=name, KeySchema=keys, AttributeDefinitions=attrs, BillingMode="PAY_PER_REQUEST")

    mk("local-trips", "trip_id")
    mk("local-events", "trip_id", "event_id")
    mk("local-drivers", "driver_id")
    mk("local-wa", "pk")
    from core import drivers, store

    for d in drivers.SEED:
        store.put("drivers", d)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter console
        pass

    def _api(self, method):
        from api import handler as api_handler

        url = urlsplit(self.path)
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length).decode() if length else None
        event = {
            "rawPath": url.path,
            "requestContext": {"http": {"method": method}},
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "queryStringParameters": {k: v[0] for k, v in parse_qs(url.query).items()} or None,
            "body": body,
        }
        resp = api_handler.handler(event, None)
        self.send_response(resp["statusCode"])
        for k, v in resp["headers"].items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(resp["body"].encode())

    def _static(self):
        path = urlsplit(self.path).path
        f = (DIST / path.lstrip("/")).resolve()
        if not str(f).startswith(str(DIST)) or not f.is_file():
            f = DIST / "index.html"  # SPA fallback, like the CloudFront function
        self.send_response(200)
        self.send_header("content-type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.end_headers()
        self.wfile.write(f.read_bytes())

    def do_GET(self):
        self._api("GET") if self.path.startswith("/api/") else self._static()

    def do_POST(self):
        self._api("POST")

    def do_PUT(self):
        self._api("PUT")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--bedrock", action="store_true", help="call real Amazon Bedrock (needs AWS credentials)")
    args = ap.parse_args()

    os.environ.update({
        "AWS_REGION": "eu-west-1", "TRIPS_TABLE": "local-trips", "EVENTS_TABLE": "local-events",
        "DRIVERS_TABLE": "local-drivers", "WHATSAPP_TABLE": "local-wa",
        "TEAM_CODE": os.environ.get("TEAM_CODE", "local"),
    })
    from moto import mock_aws

    bedrock_env = {}
    if args.bedrock:
        # moto intercepts every boto3 call, so give Bedrock its own real session created before mocking.
        import boto3

        # Resolve credentials now: inside the mock, moto replaces the environment credentials.
        creds = boto3.session.Session().get_credentials().get_frozen_credentials()
        bedrock_env["client"] = boto3.client(
            "bedrock-runtime", region_name="eu-west-1", aws_access_key_id=creds.access_key,
            aws_secret_access_key=creds.secret_key, aws_session_token=creds.token,
        )
    with mock_aws():
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
        setup_tables()
        from core import assistant

        if args.bedrock:
            assistant._client = bedrock_env["client"]
        else:
            def offline(*a, **k):
                raise RuntimeError("offline mode: Bedrock disabled")
            assistant._converse = offline
        if not DIST.exists():
            print("web/dist missing: run `make web` first", file=sys.stderr)
        print(f"MzansiRide SafeAI (local) on http://localhost:{args.port}  ·  dashboard team code: {os.environ['TEAM_CODE']}"
              f"  ·  AI: {'Amazon Bedrock' if args.bedrock else 'offline fallback'}")
        ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
