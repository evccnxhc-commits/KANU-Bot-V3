"""KANU Bot V3 -- Flask app: chat UI, manga/novel libraries, Messenger webhook."""
import hmac
import logging
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, session
from jinja2 import TemplateNotFound
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import catalog
import db
import manga
import sources
from books import handle_book_request
from llm import answer_detailed
from messenger import DeliveryError, add_dua_footer, send_file_attachment, send_text, verify_signature

VERSION = "3.7.0"
SITE_URL = "https://kanu-bot-v3.onrender.com/"
BASE_DIR = Path(__file__).resolve().parent

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("kanu")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
if not os.getenv("SECRET_KEY"):
    log.warning("SECRET_KEY is not set: sessions will be invalidated on every restart. Set it in Render.")
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    MESSENGER_SYNC=False,
)
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
db.init_db()
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="messenger")


# --------------------------------------------------------------------------- helpers
def json_error(message, status=400, **extra):
    return jsonify({"ok": False, "error": message, **extra}), status


def csrf_valid():
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


CSRF_MSG = "انتهت صلاحية الجلسة. حدّث الصفحة وحاول مجددًا."


def api(fn):
    """State-changing JSON endpoint: CSRF required."""
    @wraps(fn)
    def wrapped(*a, **kw):
        if not csrf_valid():
            return json_error(CSRF_MSG, 400)
        return fn(*a, **kw)
    return wrapped


def login_required(fn):
    @wraps(fn)
    def wrapped(*a, **kw):
        if not session.get("user_id"):
            return json_error("سجّل الدخول أولًا.", 401)
        return fn(*a, **kw)
    return wrapped


_attempts = {}
MAX_ATTEMPTS, WINDOW = 8, 600


def _attempt_key(username):
    return (request.remote_addr or "?", username.lower())


def throttled(key):
    now = time.time()
    _attempts[key] = [t for t in _attempts.get(key, []) if now - t < WINDOW]
    return len(_attempts[key]) >= MAX_ATTEMPTS


def page_context():
    return {"logged_in": bool(session.get("user_id")), "username": session.get("username"), "version": VERSION}


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if request.path.startswith("/api/") or request.path == "/health":
        resp.headers["Cache-Control"] = "no-store"
    return resp


# --------------------------------------------------------------------------- errors
def wants_json():
    return request.path.startswith("/api/") or request.path == "/webhook"


def render_error(status, title, message):
    if wants_json():
        return json_error(message, status)
    try:
        return render_template("error.html", status=status, title=title, message=message, **page_context()), status
    except Exception:  # even the error template may be what is missing
        return (f"<!doctype html><meta charset=utf-8><body dir=rtl style='font-family:sans-serif;padding:2rem'>"
                f"<h1>{status}</h1><p>{message}</p><p><a href='/'>العودة</a></p>"), status


@app.errorhandler(TemplateNotFound)
def on_template_missing(exc):
    log.error("Template missing: %s (is the templates/ folder uploaded to the repository?)", exc.name)
    return render_error(500, "ملف واجهة مفقود",
                        f"ملف القالب «{exc.name}» غير موجود على الخادم. تأكد أن مجلد templates كاملًا موجود في المستودع.")


@app.errorhandler(HTTPException)
def on_http_error(exc):
    messages = {404: "الصفحة غير موجودة.", 405: "هذه الطريقة غير مسموحة.", 413: "الطلب كبير جدًا."}
    return render_error(exc.code or 500, exc.name, messages.get(exc.code, exc.description or "حدث خطأ."))


@app.errorhandler(Exception)
def on_unexpected(exc):
    log.exception("Unhandled error on %s", request.path)
    return render_error(500, "خطأ داخلي", "حدث خطأ غير متوقع في الخادم. جرّب مرة أخرى بعد قليل.")


# --------------------------------------------------------------------------- pages
@app.get("/")
def home():
    return render_template("chat.html", **page_context())


def _library(kind):
    items = catalog.get_items(kind)
    return render_template("library.html", kind=kind, items=items, categories=catalog.categories(items),
                           demo_mode=catalog.show_demo(), **page_context())


@app.get("/manga")
def manga_library():
    return _library("manga")


@app.get("/novels")
def novel_library():
    return _library("novels")


def _detail(kind, slug):
    item = catalog.get_item(kind, slug)
    if not item:
        abort(404)
    return render_template("detail.html", kind=kind, item=item, **page_context())


@app.get("/manga/<slug>")
def manga_detail(slug):
    return _detail("manga", slug)


@app.get("/novels/<slug>")
def novel_detail(slug):
    return _detail("novels", slug)


@app.get("/health")
def health_check():
    try:
        with db.connect() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except sqlite3.Error:
        db_ok = False
    templates_ok = all((BASE_DIR / "templates" / n).is_file() for n in ("base.html", "chat.html", "library.html", "detail.html", "error.html"))
    return jsonify({
        "status": "ok" if db_ok and templates_ok else "degraded",
        "version": VERSION, "database": db_ok, "templates": templates_ok,
        "ai_providers_configured": any(os.getenv(k) for k in ("GROQ_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY")),
        "messenger_configured": all(os.getenv(k) for k in ("VERIFY_TOKEN", "PAGE_ACCESS_TOKEN", "FACEBOOK_APP_SECRET")),
        "database_path_configured": bool(os.getenv("DATABASE_PATH")),
    })


# --------------------------------------------------------------------------- auth API
@app.get("/api/session")
def api_session():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify({"authenticated": bool(session.get("user_id")), "username": session.get("username"), "csrf_token": session["csrf_token"]})


def _start_session(user_id, username):
    session.clear()
    session.permanent = True
    session.update(user_id=user_id, username=username, csrf_token=secrets.token_urlsafe(32))


@app.post("/api/register")
@api
def register():
    data = request.get_json(silent=True) or {}
    username, password = str(data.get("username", "")).strip(), str(data.get("password", ""))
    if not USERNAME_RE.fullmatch(username):
        return json_error("اسم المستخدم يجب أن يكون 3–24 حرفًا إنجليزيًا أو رقمًا، ويمكن استخدام . _ -")
    if not 10 <= len(password) <= 128:
        return json_error("كلمة المرور يجب أن تكون بين 10 و128 حرفًا.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return json_error("اجعل كلمة المرور تحتوي على حرف واحد ورقم واحد على الأقل.")
    try:
        with db.connect() as conn:
            user_id = conn.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)",
                                   (username, generate_password_hash(password))).lastrowid
    except sqlite3.IntegrityError:
        return json_error("اسم المستخدم مستخدم بالفعل. اختر اسمًا آخر.", 409)
    _start_session(user_id, username)
    return jsonify({"ok": True, "username": username, "csrf_token": session["csrf_token"]}), 201


@app.post("/api/login")
@api
def login():
    data = request.get_json(silent=True) or {}
    username, password = str(data.get("username", "")).strip()[:64], str(data.get("password", ""))[:256]
    key = _attempt_key(username)
    if throttled(key):
        return json_error("محاولات كثيرة. انتظر بضع دقائق ثم حاول مجددًا.", 429)
    with db.connect() as conn:
        user = conn.execute("SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        _attempts.setdefault(key, []).append(time.time())
        return json_error("اسم المستخدم أو كلمة المرور غير صحيحة.", 401)
    _attempts.pop(key, None)
    _start_session(user["id"], user["username"])
    return jsonify({"ok": True, "username": user["username"], "csrf_token": session["csrf_token"]})


@app.post("/api/logout")
@api
def logout():
    session.clear()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- conversations API
@app.get("/api/conversations")
@login_required
def conversations_list():
    return jsonify({"ok": True, "conversations": db.list_conversations(session["user_id"])})


@app.post("/api/conversations")
@api
@login_required
def conversations_new():
    return jsonify({"ok": True, "id": db.create_conversation(session["user_id"])}), 201


@app.get("/api/conversations/<int:conv_id>")
@login_required
def conversation_get(conv_id):
    conv = db.get_conversation(session["user_id"], conv_id)
    if not conv:
        return json_error("المحادثة غير موجودة.", 404)
    return jsonify({"ok": True, "conversation": conv, "messages": db.get_messages(conv_id)})


@app.delete("/api/conversations/<int:conv_id>")
@api
@login_required
def conversation_delete(conv_id):
    if not db.delete_conversation(session["user_id"], conv_id):
        return json_error("المحادثة غير موجودة.", 404)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- chat
def _norm(text):
    return unicodedata.normalize("NFKC", text or "").lower().translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"}))


def site_link_reply(text):
    n = _norm(text)
    asks_link = re.search(r"رابط|موقع|link|url|website|site|وين|فين|اين|where", n)
    about_kanu = re.search(r"kanu|كانو|البوت|بوت|bot", n)
    if asks_link and about_kanu and len(n.split()) <= 12:
        return f"موقع KANU والبوت هنا:\n{SITE_URL}"
    return None


WEB_CHAPTER_MSG = ("فهمت أنك تريد {series} الفصل {chapter}. تنزيل الفصول وإرسالها من واجهة الويب غير مفعّل حاليًا، "
                   "ولن أدّعي أن ملفًا جاهز قبل أن أجهّزه فعلًا. يمكنك طلبه عبر صفحة KANU على Messenger.")


def local_intent(text, sender_id):
    """Replies KANU can give without the AI provider. Returns text or None."""
    chapter = manga.parse_chapter_request(text)
    if chapter:
        return WEB_CHAPTER_MSG.format(**chapter)
    link = site_link_reply(text)
    if link:
        return link
    return handle_book_request(text, sender_id=sender_id)


@app.post("/api/chat")
@api
@login_required
def web_chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return json_error("اكتب رسالتك أولًا.")
    if len(message) > 4000:
        return json_error("الرسالة طويلة جدًا. الحد الأقصى 4000 حرف.")
    user_id = session["user_id"]
    conv_id = data.get("conversation_id")
    if conv_id:
        try:
            conv = db.get_conversation(user_id, int(conv_id))
        except (TypeError, ValueError):
            conv = None
        if not conv:
            return json_error("المحادثة غير موجودة.", 404)
        conv_id = conv["id"]
    else:
        conv_id = db.create_conversation(user_id, message[:40])
    prior = db.get_messages(conv_id, limit=10)
    retry = bool(data.get("retry")) and prior and prior[-1]["role"] == "user" and prior[-1]["content"] == message
    user_msg = prior[-1] if retry else db.add_message(conv_id, "user", message)
    if len(prior) == 0:
        db.set_title(conv_id, message[:40])
    history = [{"role": m["role"], "content": m["content"]} for m in (prior[:-1] if retry else prior)]
    sender_id = f"web:{user_id}:{conv_id}"
    try:
        reply = local_intent(message, sender_id)
        if reply is None:
            reply, status = answer_detailed(message, sender_id, history=history)
            if status != "ok":
                return json_error(reply, 503, conversation_id=conv_id, user_message=user_msg, retryable=True)
            reply = add_dua_footer(reply)
    except Exception:
        log.exception("Web chat request failed")
        return json_error("صار خطأ غير متوقع. حاول مرة أخرى بعد قليل.", 500, conversation_id=conv_id, user_message=user_msg, retryable=True)
    bot_msg = db.add_message(conv_id, "assistant", reply)
    return jsonify({"ok": True, "conversation_id": conv_id, "user_message": user_msg, "message": bot_msg})


# --------------------------------------------------------------------------- library API (live source probes)
@app.get("/api/source-check/<kind>/<slug>")
def source_check(kind, slug):
    item = catalog.get_item(kind, slug) if kind in catalog.KINDS else None
    if not item:
        return json_error("العمل غير موجود.", 404)
    if not item.get("source_url"):
        return jsonify({"ok": True, "state": "none", "message": "لا يوجد مصدر مُعدّ لهذا العمل."})
    return jsonify({"ok": True, **sources.check_source(item["source_url"])})


@app.get("/api/manga/<slug>/chapters")
def manga_chapters(slug):
    item = catalog.get_item("manga", slug)
    if not item or not item.get("source_url"):
        return json_error("لا يوجد مصدر مُعدّ لهذا العمل.", 404)
    try:
        chapters = manga.list_chapters(item["source_url"])
    except sources.SourceError as exc:
        return jsonify({"ok": False, "state": exc.code, "error": exc.message_ar, "chapters": []})
    if not chapters:
        return jsonify({"ok": False, "state": "empty", "error": "فتحت صفحة المصدر لكن لم أجد قائمة فصول قابلة للقراءة (قد تُحمَّل ديناميكيًا).", "chapters": []})
    return jsonify({"ok": True, "state": "ok", "chapters": chapters[:500]})


# --------------------------------------------------------------------------- Messenger
@app.get("/webhook")
def verify_webhook():
    expected = os.getenv("VERIFY_TOKEN", "")
    if request.args.get("hub.mode") == "subscribe" and expected and hmac.compare_digest(request.args.get("hub.verify_token") or "", expected):
        return request.args.get("hub.challenge", ""), 200
    return "Webhook verification failed", 403


def handle_messenger_text(sender, incoming):
    """Process one Messenger text. Never reports delivery success before Meta confirms it."""
    try:
        chapter = manga.parse_chapter_request(incoming)
        if chapter:
            series, number = chapter["series"], chapter["chapter"]
            send_text(sender, f"تمام، أبحث لك عن {series} الفصل {number}.", dua=False)
            pdf_path = None
            try:
                try:
                    pdf_path = manga.download_chapter_pdf(series, number)
                except Exception as exc:  # preparation failed: explain precisely
                    if not isinstance(exc, (manga.SeriesNotConfigured, manga.ChapterNotFound, manga.NoImagesFound, sources.SourceError)):
                        log.exception("Chapter preparation failed")
                    send_text(sender, manga.describe_failure(exc, series, number), dua=False)
                    return
                try:
                    send_file_attachment(sender, pdf_path, filename=f"KANU-{series}-chapter-{number}.pdf")
                except DeliveryError:
                    log.exception("Chapter PDF was prepared but delivery failed")
                    send_text(sender, "جهّزت الملف لكن Messenger لم يؤكد استلامه، فلا أستطيع القول إنه وصلك. جرّب الطلب مرة ثانية.", dua=False)
                    return
                send_text(sender, f"تم إرسال {series} الفصل {number} (أكّد Messenger الإرسال).")
            finally:
                if pdf_path and os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except OSError:
                        log.warning("Could not remove temporary PDF")
            return
        reply = local_intent(incoming, sender)
        if reply is None:
            reply, status = answer_detailed(incoming, sender)
            if status == "ok":
                send_text(sender, reply)
            else:
                send_text(sender, reply, dua=False)
            return
        send_text(sender, reply)
    except Exception:
        log.exception("Failed to handle Messenger event")
        try:
            send_text(sender, "صار خطأ بسيط. حاول مرة أخرى بعد قليل.", dua=False)
        except Exception:
            log.exception("Could not send fallback error message")


@app.post("/webhook")
def receive_webhook():
    body = request.get_data()
    if not verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        return "Invalid signature", 403
    payload = request.get_json(silent=True) or {}
    if payload.get("object") != "page":
        return jsonify({"ok": True, "ignored": True}), 200
    accepted = duplicates = 0
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            sender = (event.get("sender") or {}).get("id")
            message = event.get("message") or {}
            text = (message.get("text") or "").strip()
            if not sender or not text or message.get("is_echo"):
                continue
            mid = message.get("mid") or (f"{sender}:{event.get('timestamp')}" if event.get("timestamp") else None)
            if not db.claim_event(mid):
                duplicates += 1
                continue
            accepted += 1
            # Reply to Meta immediately; slow work (AI, PDF) must not block the webhook,
            # otherwise Meta times out and re-delivers the same message.
            if app.config["MESSENGER_SYNC"]:
                handle_messenger_text(sender, text)
            else:
                _executor.submit(handle_messenger_text, sender, text)
    return jsonify({"ok": True, "accepted": accepted, "duplicates": duplicates}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
