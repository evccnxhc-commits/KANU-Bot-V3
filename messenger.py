"""Minimal Facebook Messenger Send API and webhook signature verification."""
import hashlib
import hmac
import logging
import os
import requests

log = logging.getLogger(__name__)
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")

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

def send_text(recipient_id: str, text: str) -> None:
    token = os.getenv("PAGE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("PAGE_ACCESS_TOKEN is not configured")
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    response = requests.post(
        url, params={"access_token": token},
        json={"recipient": {"id": recipient_id}, "message": {"text": text[:2000]}},
        timeout=(5, 20))
    if not response.ok:
        log.error("Messenger Send API failed: HTTP %s %s",
                  response.status_code, response.text[:500])
    response.raise_for_status()
