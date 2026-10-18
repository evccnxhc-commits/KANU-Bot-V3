"""Messenger Send API and random dua footer."""
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
    "🤲 دعاء: اللهم أعنّا على ما ينفعنا، وبارك لنا في وقتنا وجهدنا.",
)
def verify_signature(body, supplied_signature):
    secret = os.getenv("FACEBOOK_APP_SECRET", "")
    if not secret:
        return os.getenv("ALLOW_UNSIGNED_WEBHOOKS", "false").lower() == "true"
    if not supplied_signature or not supplied_signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied_signature)

def add_dua_footer(text):
    clean = (text or "").strip()
    if "🤲 دعاء:" in clean:
        return clean[:1950]
    return f"{clean}\n\n{random.choice(DUAS)}"[:1950]

def send_text(recipient_id, text):
    token = os.getenv("PAGE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("PAGE_ACCESS_TOKEN is not configured")
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    response = requests.post(url, params={"access_token":token},
        json={"recipient":{"id":recipient_id},"message":{"text":add_dua_footer(text)}},
        timeout=(5,20))
    if not response.ok:
        log.error("Messenger Send API failed: HTTP %s %s",response.status_code,response.text[:500])
    response.raise_for_status()
