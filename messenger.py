"""Messenger Send API, signature validation, and consistent random dua footer."""
import hashlib
import hmac
import logging
import os
import random
import requests

log = logging.getLogger(__name__)
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")

DUAS = (
    "🤲 دعاء: اللهم يسّر لنا الخير حيث كان، وبارك لنا فيه.",
    "🤲 دعاء: رب اشرح صدورنا ويسّر أمورنا.",
    "🤲 دعاء: اللهم ارزقنا راحة البال وطمأنينة القلب.",
    "🤲 دعاء: رب زدنا علمًا، وافتح لنا أبواب الفهم والخير.",
    "🤲 دعاء: اللهم اجعل يومنا مليئًا بالخير والبركة.",
    "🤲 دعاء: أستغفر الله العظيم وأتوب إليه.",
    "🤲 دعاء: اللهم أعنّا على ما ينفعنا، وبارك في وقتنا وجهدنا.",
    "🤲 دعاء: يا رب، اكتب لنا الخير واصرف عنا ما يؤذينا.",
)

def verify_signature(body: bytes, supplied_signature: str | None) -> bool:
    secret = os.getenv("FACEBOOK_APP_SECRET", "")
    if not secret:
        if os.getenv("ALLOW_UNSIGNED_WEBHOOKS", "false").lower() == "true":
            log.warning("Webhook signature verification disabled by explicit setting")
            return True
        return False
    if not supplied_signature or not supplied_signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied_signature)

def add_dua_footer(text: str) -> str:
    """Attach one random short dua to every outgoing text response."""
    clean = (text or "").strip()
    # Avoid duplicate footers if a caller already included one.
    if "🤲 دعاء:" in clean or "🤲 دعاء -" in clean:
        return clean[:1850]
    return f"{clean}\n\n{random.choice(DUAS)}"[:1900]

def send_text(recipient_id: str, text: str) -> None:
    token = os.getenv("PAGE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("PAGE_ACCESS_TOKEN is not configured")
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    final_text = add_dua_footer(text)
    response = requests.post(
        url, params={"access_token": token},
        json={"recipient": {"id": recipient_id}, "message": {"text": final_text}},
        timeout=(5, 20))
    if not response.ok:
        log.error("Messenger Send API failed: HTTP %s %s",
                  response.status_code, response.text[:500])
    response.raise_for_status()
