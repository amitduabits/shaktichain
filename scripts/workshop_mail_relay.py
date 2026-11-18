"""Relay S3EID workshop exit tickets to the instructor through Resend.

Resend's unverified sandbox delivers only to the account address. This
process reads RESEND_API_KEY from the environment and never prints it.
Run: RESEND_API_KEY=... python scripts/workshop_mail_relay.py
"""
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Resend's unverified sandbox delivers only to the account inbox.
# amit.dua@pilani.bits-pilani.ac.in is rejected until a domain is verified.
ALLOWED_TO = "mail.amitdua@gmail.com"
FROM = "Shakti-Chain Workshop <onboarding@resend.dev>"
HOST = "127.0.0.1"
PORT = 8788
MAX_BODY = 100_000
WINDOW_S = 60
MAX_PER_WINDOW = 8

recent = {}


def client_key(handler):
    forwarded = handler.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:80]
    return handler.client_address[0]


def allowed_rate(key):
    now = time.time()
    stamps = [t for t in recent.get(key, []) if now - t < WINDOW_S]
    if len(stamps) >= MAX_PER_WINDOW:
        recent[key] = stamps
        return False
    stamps.append(now)
    recent[key] = stamps
    return True


def clip(value, limit):
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def message_text(work):
    reflections = work.get("reflections") if isinstance(work.get("reflections"), dict) else {}
    kept = {}
    for key, value in list(reflections.items())[:24]:
        text = clip(value, 4000)
        if text:
            kept[clip(str(key), 80)] = text
    solved = work.get("solved") if isinstance(work.get("solved"), list) else []
    body = {
        "name": clip(work.get("name"), 80) or "(no name)",
        "sentAt": clip(work.get("sentAt"), 40),
        "currentTopic": work.get("currentTopic") if isinstance(work.get("currentTopic"), int) else None,
        "solved": [clip(str(item), 80) for item in solved[:24]],
        "reflections": kept,
        "course": clip(work.get("course"), 120),
    }
    return json.dumps(body, indent=2)[:12000]


def send_resend(text, name):
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        raise RuntimeError("RESEND_API_KEY is not set")
    subject = "S3EID workshop exit ticket"
    if name:
        subject = f"S3EID workshop exit ticket: {name}"
    payload = json.dumps({
        "from": FROM,
        "to": [ALLOWED_TO],
        "subject": subject[:120],
        "text": text,
    }).encode()
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "shaktichain-workshop-mail",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"Resend returned {error.code}: {detail}") from None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except Exception as error:
            with open(os.path.join(os.environ.get("TEMP", "."), "workshop-mail-error.txt"), "a", encoding="utf-8") as handle:
                handle.write(repr(error) + "\n")
            raise

    def log_message(self, fmt, *args):
        return

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def reply(self, status, payload):
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            self.reply(200, {"ok": True, "to": ALLOWED_TO})
            return
        self.reply(404, {"error": "Not found"})

    def do_POST(self):
        if self.path.split("?")[0] not in ("/workshop-mail", "/"):
            self.reply(404, {"error": "Not found"})
            return
        if not allowed_rate(client_key(self)):
            self.reply(429, {"error": "Too many exit tickets from this network. Wait a minute, or use Export my work."})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > MAX_BODY:
            self.reply(413, {"error": "Exit ticket is empty or too large. Shorten the reflections and use Export my work."})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, ValueError):
            self.reply(400, {"error": "Expected a JSON exit ticket"})
            return
        work = payload.get("work") if isinstance(payload, dict) else None
        if not isinstance(work, dict):
            self.reply(400, {"error": "Missing work"})
            return
        name = clip(work.get("name"), 80)
        try:
            result = send_resend(message_text(work), name)
        except RuntimeError as error:
            self.reply(502, {"error": str(error)})
            return
        self.reply(200, {"ok": True, "to": ALLOWED_TO, "id": result.get("id")})


def main():
    if not os.environ.get("RESEND_API_KEY", "").strip():
        raise SystemExit("Set RESEND_API_KEY before starting the relay.")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"workshop mail relay on http://{HOST}:{PORT}/workshop-mail -> {ALLOWED_TO}")
    server.serve_forever()


if __name__ == "__main__":
    main()
