"""Polite, typed access to external source sites.

KANU identifies itself honestly, honours robots.txt, and never tries to get around a
site's protection. A 401/403/429 response is reported as "blocked" and is not retried
with a different identity.
"""
import logging
import os
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

log = logging.getLogger(__name__)

USER_AGENT = os.getenv(
    "SOURCE_USER_AGENT",
    "KANU-Bot-V3/3.7 (+https://kanu-bot-v3.onrender.com/)",
)
TIMEOUT = (6, 20)
_ROBOTS_TTL = 3600
_robots_cache = {}  # host -> (fetched_at, RobotFileParser | None)


class SourceError(Exception):
    code = "error"
    message_ar = "تعذّر الوصول إلى المصدر."


class SourceBlocked(SourceError):
    code = "blocked"
    message_ar = "المصدر رفض الوصول الآلي (HTTP 403/401/429). لن يحاول KANU تجاوز حمايته."


class SourceDisallowed(SourceError):
    code = "robots"
    message_ar = "ملف robots.txt في المصدر لا يسمح بجلب هذه الصفحة آليًا."


class SourceNotFound(SourceError):
    code = "not_found"
    message_ar = "الصفحة غير موجودة في المصدر (404)."


class SourceUnreachable(SourceError):
    code = "unreachable"
    message_ar = "لم يستجب المصدر (انتهت المهلة أو تعذّر الاتصال)."


def _robots_for(url):
    parts = urlparse(url)
    host = f"{parts.scheme}://{parts.netloc}"
    cached = _robots_cache.get(host)
    if cached and time.time() - cached[0] < _ROBOTS_TTL:
        return cached[1]
    parser = None
    try:
        resp = requests.get(host + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        if resp.status_code == 200:
            parser = RobotFileParser()
            parser.parse(resp.text.splitlines())
        elif resp.status_code in (401, 403):
            # A site that forbids even robots.txt is telling us not to crawl it.
            parser = RobotFileParser()
            parser.parse(["User-agent: *", "Disallow: /"])
    except requests.RequestException:
        log.info("robots.txt unavailable for %s; continuing without it", host)
    _robots_cache[host] = (time.time(), parser)
    return parser


def robots_allows(url):
    parser = _robots_for(url)
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


def fetch(url, *, stream=False, referer=None):
    """GET `url` and return the response, or raise a typed SourceError."""
    if urlparse(url).scheme not in ("http", "https"):
        raise SourceError("Only http(s) sources are supported")
    if not robots_allows(url):
        raise SourceDisallowed(url)
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT, stream=stream)
    except requests.RequestException as exc:
        raise SourceUnreachable(str(exc)) from exc
    if resp.status_code in (401, 403, 429):
        raise SourceBlocked(f"HTTP {resp.status_code}")
    if resp.status_code == 404:
        raise SourceNotFound(url)
    try:
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise SourceUnreachable(str(exc)) from exc
    return resp


def check_source(url):
    """Live availability probe. Returns {state, message}; never raises."""
    try:
        fetch(url).close()
        return {"state": "ok", "message": "المصدر متاح للقراءة الآلية الآن. هذا لا يضمن توفر كل فصل أو ملف."}
    except SourceError as exc:
        return {"state": exc.code, "message": exc.message_ar}
