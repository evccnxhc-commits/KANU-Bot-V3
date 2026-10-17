import hmac
import logging
import os
from flask import Flask, jsonify, request
from llm import answer_with_fallback
from manga import parse_chapter_request, get_chapter_status
from messenger import send_text, verify_signature

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
app = Flask(__name__)

@app.get("/")
def health():
    return jsonify({"service": "KANU Bot V3", "status": "ok"})

@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "version": "3.0.0"})

@app.get("/webhook")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")
    expected = os.getenv("VERIFY_TOKEN", "")
    if mode == "subscribe" and expected and hmac.compare_digest(token or "", expected):
        return challenge, 200
    return "Webhook verification failed", 403

@app.post("/webhook")
def receive_webhook():
    body = request.get_data()
    if not verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        return "Invalid signature", 403
    payload = request.get_json(silent=True) or {}
    if payload.get("object") != "page":
        return jsonify({"ok": True, "ignored": True}), 200
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            sender = (event.get("sender") or {}).get("id")
            message = event.get("message") or {}
            text = (message.get("text") or "").strip()
            if not sender or not text or message.get("is_echo"):
                continue
            try:
                chapter = parse_chapter_request(text)
                reply = (get_chapter_status(chapter["series"], chapter["chapter"])
                         if chapter else answer_with_fallback(text, sender_id=sender))
                send_text(sender, reply)
            except Exception:
                logging.exception("Failed to handle Messenger event")
                try:
                    send_text(sender, "صار خطأ بسيط 😅 حاول مرة أخرى بعد قليل.")
                except Exception:
                    logging.exception("Could not send fallback error message")
    return jsonify({"ok": True}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
