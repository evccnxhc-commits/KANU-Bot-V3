import hmac
import logging
import os
import tempfile
from flask import Flask, jsonify, request
from llm import answer_with_fallback
from manga import parse_chapter_request, download_chapter_pdf
from books import handle_book_request
from messenger import send_text, send_file_attachment, verify_signature

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
app = Flask(__name__)

@app.get("/")
def health():
    return jsonify({"service": "KANU Bot V3", "status": "ok"})

@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "version": "3.3.0"})

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
            incoming = (message.get("text") or "").strip()
            if not sender or not incoming or message.get("is_echo"):
                continue
            try:
                chapter = parse_chapter_request(incoming)
                if chapter:
                    series, chapter_number = chapter["series"], chapter["chapter"]
                    send_text(sender, f"تمام، أبحث لك عن {series} الفصل {chapter_number} 📚")
                    pdf_path = None
                    try:
                        pdf_path = download_chapter_pdf(series, chapter_number)
                        send_file_attachment(
                            sender, pdf_path,
                            filename=f"KANU-{series}-chapter-{chapter_number}.pdf",
                            caption=f"تفضل، جهّزت لك {series} الفصل {chapter_number} 📚"
                        )
                    except LookupError:
                        send_text(sender, "ما لقيت هذه السلسلة في قائمة المصادر المتاحة عندي بعد. اكتب اسم السلسلة كما يظهر في الموقع أو أرسل رابطها مرة واحدة.")
                    except Exception:
                        logging.exception("Chapter retrieval or delivery failed")
                        send_text(sender, "ما قدرت أجهّز الفصل هذه المرة. قد يكون مصدر الصور تغيّر أو تعذّر الوصول إليه. جرّب مرة أخرى لاحقًا.")
                    finally:
                        if pdf_path and os.path.exists(pdf_path):
                            try:
                                os.remove(pdf_path)
                            except OSError:
                                logging.warning("Could not remove temporary PDF")
                    continue

                book_reply = handle_book_request(incoming, sender_id=sender)
                reply = book_reply if book_reply is not None else answer_with_fallback(incoming, sender_id=sender)
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
