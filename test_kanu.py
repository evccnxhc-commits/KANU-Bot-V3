"""Local tests. No network is used: external HTTP is replaced by fakes.
Run:  python -m unittest discover -s tests -v
These prove local behaviour only -- not live Render, Meta, AI-provider or source-site access.
"""
import hashlib
import hmac
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp()
os.environ.update(DATABASE_PATH=os.path.join(TMP, "t.sqlite3"), COOKIE_SECURE="false", SECRET_KEY="t" * 40,
                  FACEBOOK_APP_SECRET="appsecret", VERIFY_TOKEN="vt", PAGE_ACCESS_TOKEN="pat", DUA_CHANCE="0")
for k in ("GROQ_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY", "KANU_SHOW_DEMO"):
    os.environ.pop(k, None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as appmod  # noqa: E402
import books  # noqa: E402
import catalog  # noqa: E402
import db  # noqa: E402
import manga  # noqa: E402
import messenger  # noqa: E402
import sources  # noqa: E402
from PIL import Image  # noqa: E402

appmod.app.config["MESSENGER_SYNC"] = True
appmod.app.config["TESTING"] = False  # exercise the real error handlers


class FakeResp:
    def __init__(self, status=200, text="", content=b"", url="https://x.test/"):
        self.status_code, self.text, self.content, self.url = status, text, content, url
        self.ok = status < 400

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, n):
        yield self.content

    def close(self):
        pass

    def json(self):
        return json.loads(self.text)


def png_bytes(color="white"):
    buf = io.BytesIO()
    Image.new("RGB", (200, 300), color).save(buf, "PNG")
    return buf.getvalue()


class Client:
    """Test client that keeps the CSRF token."""
    def __init__(self):
        self.c = appmod.app.test_client()
        self.csrf = self.c.get("/api/session").get_json()["csrf_token"]

    def post(self, url, body=None, csrf=True, method="post"):
        h = {"X-CSRF-Token": self.csrf} if csrf else {}
        r = getattr(self.c, method)(url, json=body if body is not None else {}, headers=h)
        j = r.get_json(silent=True)
        if j and j.get("csrf_token"):
            self.csrf = j["csrf_token"]
        return r

    def register(self, name, pw="Password123x"):
        return self.post("/api/register", {"username": name, "password": pw})


class Base(unittest.TestCase):
    def setUp(self):
        appmod._attempts.clear()
        books._last = None


class TestPages(Base):
    def test_main_pages_render(self):
        c = appmod.app.test_client()
        for path in ("/", "/manga", "/novels", "/manga/nano-machine", "/novels/ikadoli-mamlakat-al-balagha"):
            r = c.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn("dir=\"rtl\"", r.get_data(as_text=True))

    def test_health(self):
        j = appmod.app.test_client().get("/health").get_json()
        self.assertEqual(j["status"], "ok")
        self.assertTrue(j["templates"] and j["database"])

    def test_static_assets(self):
        c = appmod.app.test_client()
        for p in ("/static/style.css", "/static/chat.js", "/static/library.js", "/static/team-sponsor.jpg"):
            self.assertEqual(c.get(p).status_code, 200, p)

    def test_404_is_friendly(self):
        c = appmod.app.test_client()
        r = c.get("/nope")
        self.assertEqual(r.status_code, 404)
        self.assertIn("الصفحة غير موجودة", r.get_data(as_text=True))
        self.assertEqual(c.get("/manga/zzz").status_code, 404)
        j = c.get("/api/nope").get_json()
        self.assertFalse(j["ok"])

    def test_missing_templates_gives_clear_message_not_blank_page(self):
        """Regression for the original bug: /manga returned a bare 500 when templates/ was absent."""
        from jinja2 import FileSystemLoader
        env = appmod.app.jinja_env
        original = env.loader
        try:
            env.loader = FileSystemLoader("/nonexistent")
            env.cache.clear()
            r = appmod.app.test_client().get("/manga")
        finally:
            env.loader = original
            env.cache.clear()
        self.assertEqual(r.status_code, 500)
        self.assertIn("templates", r.get_data(as_text=True))

    def test_security_headers(self):
        r = appmod.app.test_client().get("/")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("script-src 'self'", r.headers["Content-Security-Policy"])
        self.assertNotIn("<script>", r.get_data(as_text=True).replace("<script src", ""))  # no inline scripts (CSP)


class TestCatalog(Base):
    def test_demo_hidden_by_default_and_badged_when_enabled(self):
        self.assertTrue(all(not i.get("demo") for i in catalog.get_items("manga")))
        html = appmod.app.test_client().get("/manga").get_data(as_text=True)
        self.assertNotIn("عرض تجريبي", html)
        with mock.patch.dict(os.environ, {"KANU_SHOW_DEMO": "true"}):
            html = appmod.app.test_client().get("/manga").get_data(as_text=True)
        self.assertIn("عرض تجريبي", html)

    def test_no_fake_cover_images(self):
        html = appmod.app.test_client().get("/manga").get_data(as_text=True)
        self.assertIn("بلا غلاف", html)
        self.assertNotIn("<img src=\"https://", html)


class TestAuth(Base):
    def test_csrf_required(self):
        c = Client()
        self.assertEqual(c.post("/api/register", {"username": "abc_1", "password": "Password123x"}, csrf=False).status_code, 400)

    def test_register_validation_login_logout(self):
        c = Client()
        self.assertEqual(c.register("ab").status_code, 400)
        self.assertEqual(c.register("good_user", "short1").status_code, 400)
        self.assertEqual(c.register("good_user", "onlyletterspw").status_code, 400)
        self.assertEqual(c.register("auth_user").status_code, 201)
        self.assertTrue(c.c.get("/api/session").get_json()["authenticated"])
        self.assertEqual(c.register("auth_user").status_code, 409)
        self.assertEqual(c.post("/api/logout").status_code, 200)
        self.assertFalse(c.c.get("/api/session").get_json()["authenticated"])
        c2 = Client()
        self.assertEqual(c2.post("/api/login", {"username": "auth_user", "password": "wrongpass123"}).status_code, 401)
        self.assertEqual(c2.post("/api/login", {"username": "AUTH_USER", "password": "Password123x"}).status_code, 200)

    def test_passwords_are_hashed(self):
        Client().register("hash_user", "Password123x")
        with db.connect() as conn:
            h = conn.execute("SELECT password_hash FROM users WHERE username='hash_user'").fetchone()[0]
        self.assertNotIn("Password123x", h)
        self.assertTrue(h.startswith(("scrypt:", "pbkdf2:")))

    def test_login_throttle(self):
        c = Client()
        c.register("thr_user")
        c.post("/api/logout")
        c.csrf = c.c.get("/api/session").get_json()["csrf_token"]  # the page reloads its session after logout
        codes = [c.post("/api/login", {"username": "thr_user", "password": "badbadbad1"}).status_code for _ in range(9)]
        self.assertEqual(codes[:8], [401] * 8)
        self.assertEqual(codes[8], 429)


class TestChat(Base):
    def user(self, name):
        c = Client()
        self.assertEqual(c.register(name).status_code, 201)
        return c

    def test_requires_login(self):
        c = Client()
        self.assertEqual(c.post("/api/chat", {"message": "hi"}).status_code, 401)

    def test_chat_persists_and_lists_and_isolated(self):
        c = self.user("chat_a")
        with mock.patch.object(appmod, "answer_detailed", return_value=("أهلًا بك في KANU", "ok")):
            r = c.post("/api/chat", {"message": "مرحبا KANU كيف الحال؟"})
        self.assertEqual(r.status_code, 200)
        cid = r.get_json()["conversation_id"]
        self.assertEqual(r.get_json()["message"]["content"], "أهلًا بك في KANU")
        convs = c.c.get("/api/conversations").get_json()["conversations"]
        self.assertEqual([x["id"] for x in convs], [cid])
        msgs = c.c.get(f"/api/conversations/{cid}").get_json()["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])
        other = self.user("chat_b")
        self.assertEqual(other.c.get(f"/api/conversations/{cid}").status_code, 404)
        self.assertEqual(other.post(f"/api/conversations/{cid}", method="delete").status_code, 404)
        self.assertEqual(c.post(f"/api/conversations/{cid}", method="delete").status_code, 200)

    def test_provider_failure_shows_error_not_fake_answer(self):
        c = self.user("chat_fail")
        with mock.patch.object(appmod, "answer_detailed", return_value=("تعذّر الحصول على رد", "all_failed")):
            r = c.post("/api/chat", {"message": "سؤال"})
            self.assertEqual(r.status_code, 503)
            j = r.get_json()
            self.assertTrue(j["retryable"])
            cid = j["conversation_id"]
            r2 = c.post("/api/chat", {"message": "سؤال", "conversation_id": cid, "retry": True})
        self.assertEqual(r2.status_code, 503)
        msgs = c.c.get(f"/api/conversations/{cid}").get_json()["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user"], "failed answers must not be stored; retry must not duplicate the user message")

    def test_no_provider_configured_is_reported(self):
        c = self.user("chat_nokey")
        r = c.post("/api/chat", {"message": "سؤال عادي عن الطقس"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("مفاتيح", r.get_json()["error"])

    def test_real_llm_module_reports_all_failed(self):
        import llm, requests
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "k"}), mock.patch.object(llm.requests, "post", side_effect=requests.ConnectionError("x")):
            text, status = llm.answer_detailed("hi", "s1", history=[])
        self.assertEqual(status, "all_failed")

    def test_site_link_question(self):
        c = self.user("chat_link")
        for q in ("وين رابط موقع KANU؟", "ما هو رابط البوت؟"):
            r = c.post("/api/chat", {"message": q})
            self.assertEqual(r.status_code, 200, q)
            self.assertIn("https://kanu-bot-v3.onrender.com/", r.get_json()["message"]["content"])

    def test_web_chapter_request_is_honest(self):
        c = self.user("chat_ch")
        r = c.post("/api/chat", {"message": "هل تقدر ترسل لي فصول مانهوا نانو ميشل فصل 3؟"})
        body = r.get_json()["message"]["content"]
        self.assertIn("غير مفعّل", body)
        for claim in ("تم إرسال", "تفضل", "جهّزت", "أرسلت"):
            self.assertNotIn(claim, body)

    def test_writing_help_is_not_hijacked_by_book_flow(self):
        c = self.user("chat_book")
        with mock.patch.object(appmod, "answer_detailed", return_value=("طبعًا", "ok")) as m:
            r = c.post("/api/chat", {"message": "ساعدني في كتابة رسالة"})
        self.assertEqual(r.status_code, 200)
        m.assert_called_once()

    def test_message_limits(self):
        c = self.user("chat_lim")
        self.assertEqual(c.post("/api/chat", {"message": "   "}).status_code, 400)
        self.assertEqual(c.post("/api/chat", {"message": "x" * 4001}).status_code, 400)


class TestParser(Base):
    def test_arabic_and_english_requests(self):
        cases = {
            "هل تقدر ترسل لي فصول مانهوا نانو ميشل فصل 3؟": ("نانو ميشل", "3"),
            "نانو ميشل الفصل 3": ("نانو ميشل", "3"),
            "تقدر تجيب لي نانو ميشل فصل 12": ("نانو ميشل", "12"),
            "فصل 3 من نانو ميشل": ("نانو ميشل", "3"),
            "اعطني الفصل ٥ من nano machine": ("nano machine", "5"),
            "nano machine chapter 3": ("nano machine", "3"),
            "can you send me nano machine chapter 3?": ("nano machine", "3"),
            "nano machine #7": ("nano machine", "7"),
            "nano machine chapter 10.5": ("nano machine", "10.5"),
        }
        for text, (series, ch) in cases.items():
            got = manga.parse_chapter_request(text)
            self.assertIsNotNone(got, text)
            self.assertEqual((got["series"], got["chapter"]), (series, ch), text)

    def test_non_requests_are_ignored(self):
        for text in ("مرحبا كيف حالك", "اشرح لي الفصل 3 من كتاب الفيزياء بالتفصيل وماذا يتضمن", "what is chapter", ""):
            self.assertIsNone(manga.parse_chapter_request(text), text)

    def test_books_intent(self):
        for t in ("ساعدني في كتابة رسالة", "ما رأيك في أفضل كتاب للبرمجة؟", "اشرح لي pdf"):
            self.assertIsNone(books.handle_book_request(t, sender_id="bk"), t)
        self.assertIn("اسم الرواية", books.handle_book_request("تقدر تجيب لي رواية؟", sender_id="bk2"))
        self.assertIn("bo.afedne.com", books.handle_book_request("رواية ايكادولي", sender_id="bk3"))
        self.assertNotIn("http", books.handle_book_request("روايه آرسس", sender_id="bk4"))  # never invents a link


class TestSources(Base):
    def setUp(self):
        super().setUp()
        sources._robots_cache.clear()

    def _get(self, routes):
        def fake(url, **kw):
            for key, resp in routes.items():
                if url.endswith(key):
                    return resp
            return FakeResp(404)
        return fake

    def test_403_is_reported_not_bypassed(self):
        calls = []
        def fake(url, **kw):
            calls.append((url, kw.get("headers", {}).get("User-Agent")))
            return FakeResp(404) if url.endswith("robots.txt") else FakeResp(403)
        with mock.patch.object(sources.requests, "get", side_effect=fake):
            with self.assertRaises(sources.SourceBlocked):
                sources.fetch("https://blocked.test/page")
            state = sources.check_source("https://blocked.test/page")
        self.assertEqual(state["state"], "blocked")
        self.assertTrue(all(ua.startswith("KANU-Bot-V3") for _, ua in calls), "must keep its honest user agent")

    def test_robots_disallow_respected(self):
        routes = {"robots.txt": FakeResp(200, "User-agent: *\nDisallow: /private\n"), "/private/x": FakeResp(200, "secret")}
        with mock.patch.object(sources.requests, "get", side_effect=self._get(routes)):
            with self.assertRaises(sources.SourceDisallowed):
                sources.fetch("https://ok.test/private/x")

    def test_unreachable_and_not_found(self):
        import requests
        with mock.patch.object(sources.requests, "get", side_effect=requests.ConnectionError("down")):
            self.assertEqual(sources.check_source("https://down.test/")["state"], "unreachable")
        routes = {"robots.txt": FakeResp(404)}
        with mock.patch.object(sources.requests, "get", side_effect=self._get(routes)):
            self.assertEqual(sources.check_source("https://ok.test/missing")["state"], "not_found")

    def test_source_check_endpoint(self):
        c = appmod.app.test_client()
        with mock.patch.object(appmod.sources, "check_source", return_value={"state": "blocked", "message": "m"}):
            j = c.get("/api/source-check/manga/nano-machine").get_json()
        self.assertEqual(j["state"], "blocked")
        self.assertEqual(c.get("/api/source-check/manga/unknown").status_code, 404)
        self.assertEqual(c.get("/api/source-check/evil/x").status_code, 404)


SERIES_HTML = '<a href="/series/nm-lkim9hef/chapter/3-aaa">الفصل 3</a><a href="/series/nm-lkim9hef/chapter/323-r7te8j8g">الفصل 323</a><a href="/series/nm-lkim9hef/chapter/10-bbb">chapter 10</a><a href="/about">x</a>'
CHAPTER_HTML = '<img src="/logo.png" class="logo"><img data-src="https://cdn.test/1.png"><img data-src="https://cdn.test/2.png">'


def manga_fetch(url, stream=False, referer=None):
    if url.endswith("nm-lkim9hef"):
        return FakeResp(200, SERIES_HTML, url=url)
    if "/chapter/3-aaa" in url:
        return FakeResp(200, CHAPTER_HTML, url=url)
    if url.startswith("https://cdn.test/"):
        return FakeResp(200, content=png_bytes("white" if url.endswith("1.png") else "black"), url=url)
    raise sources.SourceNotFound(url)


class TestManga(Base):
    def test_chapter_listing_sorted(self):
        with mock.patch.object(sources, "fetch", side_effect=manga_fetch):
            chapters = manga.list_chapters("https://mangawy.org/series/nm-lkim9hef")
        self.assertEqual([c["number"] for c in chapters], ["323", "10", "3"])

    def test_real_pdf_is_built(self):
        with mock.patch.object(sources, "fetch", side_effect=manga_fetch):
            path = manga.download_chapter_pdf("نانو ميشل", "3")
        try:
            data = Path(path).read_bytes()
            self.assertTrue(data.startswith(b"%PDF"))
            self.assertGreater(len(data), 1024)
        finally:
            os.remove(path)

    def test_failures_are_typed(self):
        with mock.patch.object(sources, "fetch", side_effect=manga_fetch):
            with self.assertRaises(manga.ChapterNotFound):
                manga.download_chapter_pdf("nano machine", "999")
            with self.assertRaises(manga.SeriesNotConfigured):
                manga.download_chapter_pdf("unknown series", "1")
        with mock.patch.object(sources, "fetch", side_effect=sources.SourceBlocked("HTTP 403")):
            with self.assertRaises(sources.SourceBlocked):
                manga.download_chapter_pdf("nano machine", "3")

    def test_chapters_endpoint_reports_block(self):
        with mock.patch.object(appmod.manga, "list_chapters", side_effect=sources.SourceBlocked("403")):
            j = appmod.app.test_client().get("/api/manga/nano-machine/chapters").get_json()
        self.assertFalse(j["ok"])
        self.assertEqual(j["state"], "blocked")


def sign(body):
    return "sha256=" + hmac.new(b"appsecret", body, hashlib.sha256).hexdigest()


def fb_event(mid, text, sender="U1"):
    return {"object": "page", "entry": [{"messaging": [{"sender": {"id": sender}, "timestamp": 1, "message": {"mid": mid, "text": text}}]}]}


class TestMessenger(Base):
    def post_hook(self, payload, signed=True):
        body = json.dumps(payload).encode()
        h = {"X-Hub-Signature-256": sign(body)} if signed else {}
        return appmod.app.test_client().post("/webhook", data=body, headers={**h, "Content-Type": "application/json"})

    def test_verification(self):
        c = appmod.app.test_client()
        ok = c.get("/webhook?hub.mode=subscribe&hub.verify_token=vt&hub.challenge=123")
        self.assertEqual((ok.status_code, ok.get_data(as_text=True)), (200, "123"))
        self.assertEqual(c.get("/webhook?hub.mode=subscribe&hub.verify_token=bad&hub.challenge=1").status_code, 403)

    def test_signature_enforced(self):
        self.assertEqual(self.post_hook(fb_event("m-sig", "hi"), signed=False).status_code, 403)
        with mock.patch.object(appmod, "handle_messenger_text"):
            self.assertEqual(self.post_hook(fb_event("m-sig2", "hi")).status_code, 200)

    def test_duplicate_events_processed_once_but_new_ones_pass(self):
        with mock.patch.object(appmod, "handle_messenger_text") as h:
            r1 = self.post_hook(fb_event("m-dup", "a")).get_json()
            r2 = self.post_hook(fb_event("m-dup", "a")).get_json()
            r3 = self.post_hook(fb_event("m-new", "a")).get_json()
        self.assertEqual((r1["accepted"], r2["accepted"], r2["duplicates"], r3["accepted"]), (1, 0, 1, 1))
        self.assertEqual(h.call_count, 2)

    def test_echo_and_non_text_ignored(self):
        payload = {"object": "page", "entry": [{"messaging": [
            {"sender": {"id": "U"}, "message": {"mid": "e1", "text": "x", "is_echo": True}},
            {"sender": {"id": "U"}, "delivery": {"mids": ["m"]}}]}]}
        with mock.patch.object(appmod, "handle_messenger_text") as h:
            self.assertEqual(self.post_hook(payload).status_code, 200)
        h.assert_not_called()

    def test_webhook_replies_before_slow_work(self):
        appmod.app.config["MESSENGER_SYNC"] = False
        try:
            with mock.patch.object(appmod._executor, "submit") as sub:
                r = self.post_hook(fb_event("m-async", "hello"))
            self.assertEqual(r.status_code, 200)
            sub.assert_called_once()
        finally:
            appmod.app.config["MESSENGER_SYNC"] = True

    def run_flow(self, text="نانو ميشل الفصل 3", prepare=None, deliver=None):
        sent = []
        with mock.patch.object(appmod, "send_text", side_effect=lambda r, t, dua=True: sent.append(t)), \
             mock.patch.object(appmod, "send_file_attachment", side_effect=deliver or (lambda *a, **k: sent.append("<FILE>"))), \
             mock.patch.object(appmod.manga, "download_chapter_pdf", side_effect=prepare):
            appmod.handle_messenger_text("U9", text)
        return sent

    def make_pdf(self, *a):
        fd, p = tempfile.mkstemp(suffix=".pdf")
        os.write(fd, b"%PDF-1.4 " + b"x" * 2000)
        os.close(fd)
        return p

    def test_success_flow_confirms_only_after_file_sent(self):
        sent = self.run_flow(prepare=self.make_pdf)
        self.assertEqual([s if s == "<FILE>" else "text" for s in sent], ["text", "<FILE>", "text"])
        self.assertIn("تم إرسال", sent[-1])

    def test_delivery_failure_is_not_reported_as_success(self):
        def boom(*a, **k):
            raise messenger.DeliveryError("HTTP 400")
        sent = self.run_flow(prepare=self.make_pdf, deliver=boom)
        self.assertFalse(any("تم إرسال" in s for s in sent))
        self.assertTrue(any("لم يؤكد" in s for s in sent))

    def test_preparation_failure_blocked_source(self):
        def blocked(*a):
            raise sources.SourceBlocked("HTTP 403")
        sent = self.run_flow(prepare=blocked)
        self.assertIn("لن يحاول KANU تجاوز حمايته", sent[-1])
        self.assertNotIn("<FILE>", sent)
        self.assertFalse(any("تم إرسال" in s for s in sent))

    def test_temp_pdf_removed(self):
        paths = []
        def prep(*a):
            p = self.make_pdf(); paths.append(p); return p
        self.run_flow(prepare=prep)
        self.assertFalse(os.path.exists(paths[0]))

    def test_plain_chat_goes_to_ai(self):
        sent = []
        with mock.patch.object(appmod, "send_text", side_effect=lambda r, t, dua=True: sent.append(t)), \
             mock.patch.object(appmod, "answer_detailed", return_value=("رد", "ok")):
            appmod.handle_messenger_text("U8", "مرحبا")
        self.assertEqual(sent, ["رد"])

    def test_send_file_checks_both_steps(self):
        p = self.make_pdf()
        calls = []
        def post(url, **kw):
            calls.append(url)
            if url.endswith("message_attachments"):
                return FakeResp(200, json.dumps({"attachment_id": "A1"}))
            return FakeResp(400, "bad")
        try:
            with mock.patch.object(messenger.requests, "post", side_effect=post):
                with self.assertRaises(messenger.DeliveryError):
                    messenger.send_file_attachment("U", p, "a.pdf")
            self.assertEqual(len(calls), 2)
            with mock.patch.object(messenger.requests, "post", side_effect=lambda url, **kw: FakeResp(200, json.dumps({"attachment_id": "A1"}))):
                messenger.send_file_attachment("U", p, "a.pdf")
        finally:
            os.remove(p)

    def test_dua_is_optional_not_forced(self):
        with mock.patch.dict(os.environ, {}), mock.patch.object(messenger, "DUA_CHANCE", 0.0):
            self.assertEqual(messenger.add_dua_footer("رد طويل بما يكفي لإضافة دعاء إليه لو سُمح بذلك"), "رد طويل بما يكفي لإضافة دعاء إليه لو سُمح بذلك")
        with mock.patch.object(messenger, "DUA_CHANCE", 1.0):
            out = messenger.add_dua_footer("رد طويل بما يكفي لإضافة دعاء إليه لو سُمح بذلك")
            self.assertTrue(any(d in out for d in messenger.DUAS))
            self.assertEqual(messenger.add_dua_footer("تم"), "تم")


class TestMisc(Base):
    def test_no_secrets_in_repo_files(self):
        root = Path(__file__).resolve().parent.parent
        for f in list(root.glob("*.py")) + list(root.glob("*.yaml")) + list(root.glob("*.example")) + list(root.glob("static/*.js")):
            text = f.read_text(encoding="utf-8")
            for bad in ("EAA", "gsk_", "sk-or-", "nvapi-"):
                self.assertNotIn(bad, text, f"{f.name} looks like it contains a key ({bad})")

    def test_forbidden_phrases_absent_from_persona(self):
        import llm
        # the prompt may mention the ban, but the bot must not be instructed to use the phrases
        for f in (Path(llm.__file__), Path(messenger.__file__)):
            text = f.read_text(encoding="utf-8")
            self.assertNotIn("بإذن الله\"", text)
        self.assertTrue(all("إن شاء الله" not in d and "بإذن الله" not in d for d in messenger.DUAS))


if __name__ == "__main__":
    unittest.main()
