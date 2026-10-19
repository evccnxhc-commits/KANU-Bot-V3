"""Meta Messenger API helpers and a lightly decorated random dua footer."""
import hashlib
import hmac
import logging
import os
import random
import requests

log = logging.getLogger(__name__)
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")
DUAS = (
    "✨ اللهم ارزقنا راحة البال وطمأنينة القلب. ❤️",
    "🌿 اللهم يسّر لنا الخير وبارك لنا فيه. 🤍",
    "🤲 رب اشرح صدورنا ويسّر أمورنا. ❤️",
    "✨ اللهم اجعل أيامنا أهدأ وقلوبنا أطمئن. 🤍",
    "🌙 يا رب ارزقنا خيرًا يفوق توقعاتنا. ❤️",
    "🤍 أستغفر الله العظيم وأتوب إليه.",
    "🌿 اللهم بارك لنا في وقتنا وجهدنا. ❤️",
    "✨ رب زدنا علمًا وطمأنينةً وخيرًا. 🤍",
)

def verify_signature(body: bytes, supplied_signature: str | None) -> bool:
    secret = os.getenv("FACEBOOK_APP_SECRET", "")
    if not secret:
        return os.getenv("ALLOW_UNSIGNED_WEBHOOKS", "false").lower() == "true"
    if not supplied_signature or not supplied_signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied_signature)

def add_dua_footer(text: str) -> str:
    """Append exactly one lightly decorated dua, without the word 'دعاء'."""
    clean = (text or "").strip()
    lines = clean.splitlines()
    if lines and ("دعاء:" in lines[-1] or "دعاء -" in lines[-1]):
        lines.pop()
        clean = "\n".join(lines).rstrip()
    if lines and any(phrase in lines[-1] for phrase in (
        "اللهم ارزقنا راحة البال", "اللهم يسّر لنا الخير", "رب اشرح صدورنا",
        "اللهم اجعل أيامنا", "يا رب ارزقنا خيرًا", "أستغفر الله العظيم",
        "اللهم بارك لنا", "رب زدنا علمًا"
    )):
        lines.pop()
        clean = "\n".join(lines).rstrip()
    return f"{clean}\n\n{random.choice(DUAS)}"[:1950]

def send_text(recipient_id: str, text: str) -> None:
    token = os.getenv("PAGE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("PAGE_ACCESS_TOKEN is not configured")
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    response = requests.post(
        url, params={"access_token": token},
        json={"recipient": {"id": recipient_id},
              "message": {"text": add_dua_footer(text)[:2000]}},
        timeout=(5, 20))
    if not response.ok:
        log.error("Messenger Send API failed: HTTP %s %s", response.status_code, response.text[:500])
    response.raise_for_status()

def send_file_attachment(recipient_id: str, file_path: str, filename: str, caption: str = "") -> None:
    """Upload a file as a Messenger attachment, then send its attachment ID."""
    token = os.getenv("PAGE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("PAGE_ACCESS_TOKEN is not configured")
    upload_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/message_attachments"
    with open(file_path, "rb") as fh:
        response = requests.post(
            upload_url, params={"access_token": token},
            data={"message": '{"attachment":{"type":"file","payload":{"is_reusable":true}}}'},
            files={"filedata": (filename, fh, "application/pdf")},
            timeout=(10, 60))
    response.raise_for_status()
    attachment_id = response.json().get("attachment_id")
    if not attachment_id:
        raise RuntimeError("Messenger did not return an attachment_id")
    message = {"attachment": {"type": "file", "payload": {"attachment_id": attachment_id}}}
    if caption:
        # Send caption separately so it also gets the footer.
        send_text(recipient_id, caption)
    send_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    sent = requests.post(send_url, params={"access_token": token},
        json={"recipient": {"id": recipient_id}, "message": message}, timeout=(5, 30))
    if not sent.ok:
        log.error("Messenger attachment send failed: HTTP %s %s", sent.status_code, sent.text[:500])
    sent.raise_for_status()
