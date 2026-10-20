"""Meta Messenger helpers. Delivery functions raise DeliveryError unless Meta confirmed."""
import hashlib
import hmac
import logging
import os
import random

import requests

log = logging.getLogger(__name__)
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # Messenger's file attachment limit
DUAS = (
    "✨ اللهم ارزقنا راحة البال وطمأنينة القلب. ❤️",
    "🌿 اللهم يسّر لنا الخير وبارك لنا فيه. 🤍",
    "🤲 رب اشرح صدورنا ويسّر أمورنا. ❤️",
    "✨ اللهم اجعل أيامنا أهدأ وقلوبنا أطمئن. 🤍",
    "🌙 يا رب ارزقنا خيرًا يفوق توقعاتنا. ❤️",
    "🌿 اللهم بارك لنا في وقتنا وجهدنا. ❤️",
    "✨ رب زدنا علمًا وطمأنينةً وخيرًا. 🤍",
)
DUA_CHANCE = float(os.getenv("DUA_CHANCE", "0.6"))


class DeliveryError(RuntimeError):
    """Messenger did not confirm that the message/file was delivered."""


def verify_signature(body: bytes, supplied_signature) -> bool:
    secret = os.getenv("FACEBOOK_APP_SECRET", "")
    if not secret:
        return os.getenv("ALLOW_UNSIGNED_WEBHOOKS", "false").lower() == "true"
    if not supplied_signature or not supplied_signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied_signature)


def add_dua_footer(text: str, force=False) -> str:
    """Append a short dua to most substantial replies (not every one)."""
    clean = (text or "").strip()
    if any(d in clean for d in DUAS):
        return clean[:2000]
    if not force and (len(clean) < 40 or random.random() > DUA_CHANCE):
        return clean[:2000]
    return f"{clean[:1900].rstrip()}\n\n{random.choice(DUAS)}"


def _token():
    token = os.getenv("PAGE_ACCESS_TOKEN", "")
    if not token:
        raise DeliveryError("PAGE_ACCESS_TOKEN is not configured")
    return token


def send_text(recipient_id: str, text: str, dua: bool = True) -> None:
    body = add_dua_footer(text) if dua else (text or "")[:2000]
    try:
        response = requests.post(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages",
            params={"access_token": _token()},
            json={"recipient": {"id": recipient_id}, "message": {"text": body}, "messaging_type": "RESPONSE"},
            timeout=(5, 20))
    except requests.RequestException as exc:
        raise DeliveryError("Messenger request failed") from exc
    if not response.ok:
        log.error("Messenger Send API failed: HTTP %s %s", response.status_code, response.text[:300])
        raise DeliveryError(f"HTTP {response.status_code}")


def send_file_attachment(recipient_id: str, file_path: str, filename: str) -> None:
    """Upload a PDF and send it. Returns only after Meta accepted BOTH steps."""
    if os.path.getsize(file_path) > MAX_ATTACHMENT_BYTES:
        raise DeliveryError("file exceeds Messenger's 25 MB limit")
    token = _token()
    base = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me"
    try:
        with open(file_path, "rb") as fh:
            up = requests.post(
                f"{base}/message_attachments", params={"access_token": token},
                data={"message": '{"attachment":{"type":"file","payload":{"is_reusable":true}}}'},
                files={"filedata": (filename, fh, "application/pdf")}, timeout=(10, 60))
        if not up.ok:
            log.error("Messenger upload failed: HTTP %s %s", up.status_code, up.text[:300])
            raise DeliveryError(f"upload HTTP {up.status_code}")
        attachment_id = up.json().get("attachment_id")
        if not attachment_id:
            raise DeliveryError("Messenger did not return an attachment_id")
        sent = requests.post(
            f"{base}/messages", params={"access_token": token},
            json={"recipient": {"id": recipient_id}, "messaging_type": "RESPONSE",
                  "message": {"attachment": {"type": "file", "payload": {"attachment_id": attachment_id}}}},
            timeout=(5, 30))
    except (requests.RequestException, ValueError) as exc:
        raise DeliveryError("Messenger file delivery failed") from exc
    if not sent.ok:
        log.error("Messenger attachment send failed: HTTP %s %s", sent.status_code, sent.text[:300])
        raise DeliveryError(f"send HTTP {sent.status_code}")
