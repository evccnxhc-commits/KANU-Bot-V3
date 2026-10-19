import hmac
import logging
import os
import re
import secrets
import sqlite3
import tempfile
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, render_template, render_template_string, send_from_directory, abort, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from llm import answer_with_fallback
from manga import parse_chapter_request, download_chapter_pdf
from books import handle_book_request
from messenger import send_text, send_file_attachment, verify_signature

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true",
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "kanu_users.sqlite3"))
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")


init_db()


def json_error(message, status=400):
    return jsonify({"ok": False, "error": message}), status


def csrf_valid():
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return json_error("سجّل الدخول أولًا.", 401)
        return fn(*args, **kwargs)
    return wrapped


@app.get("/")
def home():
    context = {"logged_in": bool(session.get("user_id")), "username": session.get("username")}
    if (BASE_DIR / "templates" / "index.html").is_file():
        return render_template("index.html", **context)
    if (BASE_DIR / "index.html").is_file():
        return render_template_string((BASE_DIR / "index.html").read_text(encoding="utf-8"), **context)
    return jsonify({"ok": False, "error": "واجهة الموقع غير موجودة"}), 500


def static_compat(filename):
    static_dir = BASE_DIR / "static"
    candidate = static_dir / filename
    if candidate.is_file():
        return send_from_directory(static_dir, filename)
    if "/" not in filename and filename in {"style.css", "app.js", "team-sponsor.jpg", "favicon.ico"} and (BASE_DIR / filename).is_file():
        return send_from_directory(BASE_DIR, filename)
    abort(404)


app.view_functions["static"] = static_compat


@app.get("/manga")
def manga_library():
    return render_template("manga.html", logged_in=bool(session.get("user_id")), username=session.get("username"))


@app.get("/novels")
def novel_library():
    return render_template("novels.html", logged_in=bool(session.get("user_id")), username=session.get("username"))


@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "version": "3.4.0"})


@app.get("/api/session")
def api_session():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify({"authenticated": bool(session.get("user_id")), "username": session.get("username"), "csrf_token": session["csrf_token"]})


@app.post("/api/register")
def register():
    if not csrf_valid():
        return json_error("انتهت صلاحية الطلب. حدّث الصفحة وحاول مجددًا.", 400)
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not USERNAME_RE.fullmatch(username):
        return json_error("اسم المستخدم يجب أن يكون 3–24 حرفًا إنجليزيًا أو رقمًا، ويمكن استخدام . _ -.")
    if len(password) < 10 or len(password) > 128:
        return json_error("كلمة المرور يجب أن تكون بين 10 و128 حرفًا.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return json_error("اجعل كلمة المرور تحتوي على حرف واحد ورقم واحد على الأقل.")
    try:
        with get_db() as conn:
            cur = conn.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)", (username, generate_password_hash(password)))
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return json_error("اسم المستخدم مستخدم بالفعل. اختر اسمًا آخر.", 409)
    session.clear()
    session["user_id"] = user_id
    session["username"] = username
    session["csrf_token"] = secrets.token_urlsafe(32)
    session["web_session_id"] = secrets.token_urlsafe(16)
    return jsonify({"ok": True, "username": username, "csrf_token": session["csrf_token"]}), 201


@app.post("/api/login")
def login():
    if not csrf_valid():
        return json_error("انتهت صلاحية الطلب. حدّث الصفحة وحاول مجددًا.", 400)
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    with get_db() as conn:
        user = conn.execute("SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return json_error("اسم المستخدم أو كلمة المرور غير صحيحة.", 401)
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    session["web_session_id"] = secrets.token_urlsafe(16)
    return jsonify({"ok": True, "username": user["username"], "csrf_token": session["csrf_token"]})


@app.post("/api/logout")
def logout():
    if not csrf_valid():
        return json_error("انتهت صلاحية الطلب. حدّث الصفحة وحاول مجددًا.", 400)
    session.clear()
    return jsonify({"ok": True})


@app.post("/api/chat")
@login_required
def web_chat():
    if not csrf_valid():
        return json_error("انتهت صلاحية الطلب. حدّث الصفحة وحاول مجددًا.", 400)
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return json_error("اكتب رسالتك أولًا.")
    if len(message) > 4000:
        return json_error("الرسالة طويلة جدًا. الحد الأقصى 4000 حرف.")
    sender_id = f"web:{session['user_id']}:{session.get('web_session_id', 'default')}"
    try:
        chapter = parse_chapter_request(message)
        if chapter:
            reply = (f"أفهم أنك تريد {chapter['series']} الفصل {chapter['chapter']} 📚\n\n"
                     "ميزة تنزيل الفصول من الموقع وإرسالها عبر واجهة الويب لم تُفعّل بعد. لن أدّعي أن الملف جاهز قبل تجهيزه فعليًا.")
        else:
            book_reply = handle_book_request(message, sender_id=sender_id)
            reply = book_reply if book_reply is not None else answer_with_fallback(message, sender_id=sender_id)
    except Exception:
        logging.exception("Web chat request failed")
        return json_error("صار خطأ بسيط 😅 حاول مرة أخرى بعد قليل.", 500)
    return jsonify({"ok": True, "reply": reply})


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
                        send_file_attachment(sender, pdf_path, filename=f"KANU-{series}-chapter-{chapter_number}.pdf", caption=f"تفضل، جهّزت لك {series} الفصل {chapter_number} 📚")
                    except LookupError:
                        send_text(sender, "ما لقيت هذه السلسلة في قائمة المصادر المتاحة عندي بعد. اكتب اسم السلسلة كما يظهر في الموقع أو أرسل رابطها مرة واحدة.")
                    except Exception:
                        logging.exception("Chapter retrieval or delivery failed")
                        send_text(sender, "ما قدرت أجهّز الفصل هذه المرة. قد يكون مصدر الصور تغيّر أو تعذّر الوصول إليه. جرّب مرة أخرى لاحقًا.")
                    finally:
                        if pdf_path and os.path.exists(pdf_path):
                            try: os.remove(pdf_path)
                            except OSError: logging.warning("Could not remove temporary PDF")
                    continue
                book_reply = handle_book_request(incoming, sender_id=sender)
                reply = book_reply if book_reply is not None else answer_with_fallback(incoming, sender_id=sender)
                send_text(sender, reply)
            except Exception:
                logging.exception("Failed to handle Messenger event")
                try: send_text(sender, "صار خطأ بسيط 😅 حاول مرة أخرى بعد قليل.")
                except Exception: logging.exception("Could not send fallback error message")
    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
