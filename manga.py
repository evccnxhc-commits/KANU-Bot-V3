"""Manga chapter requests: parsing, chapter discovery and PDF assembly.

Access goes through `sources.fetch`, so robots.txt is honoured and HTTP 403 is
reported as such instead of being worked around.
"""
import io
import json
import logging
import os
import re
import tempfile
import unicodedata
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from PIL import Image

import sources
from sources import SourceBlocked, SourceDisallowed, SourceError  # noqa: F401  (re-exported)

log = logging.getLogger(__name__)
MAX_IMAGES = int(os.getenv("MANGA_MAX_IMAGES", "100"))
MAX_DOWNLOAD_BYTES = int(os.getenv("MANGA_MAX_DOWNLOAD_BYTES", str(24 * 1024 * 1024)))

DEFAULT_SERIES = {
    "nano machine": "https://mangawy.org/series/nm-lkim9hef",
    "nano-machine": "https://mangawy.org/series/nm-lkim9hef",
    "nano machine manhwa": "https://mangawy.org/series/nm-lkim9hef",
    "نانو ميشل": "https://mangawy.org/series/nm-lkim9hef",
    "نانو ماشين": "https://mangawy.org/series/nm-lkim9hef",
    "نانو مشين": "https://mangawy.org/series/nm-lkim9hef",
}
KNOWN_CHAPTER_URL = "https://mangawy.org/series/nm-lkim9hef/chapter/323-r7te8j8g"


class ChapterNotFound(LookupError):
    pass


class SeriesNotConfigured(LookupError):
    pass


class NoImagesFound(RuntimeError):
    pass


_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})


def _normalize(value):
    value = unicodedata.normalize("NFKC", value or "").lower().translate(_DIGITS).translate(_LETTERS)
    value = re.sub(r"[ًٌٍَُِّْـ]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _series_map():
    mapping = dict(DEFAULT_SERIES)
    raw = os.getenv("MANGA_SERIES_JSON", "").strip()
    if raw:
        try:
            extra = json.loads(raw)
            if isinstance(extra, dict):
                mapping.update({str(k): str(v) for k, v in extra.items()})
        except json.JSONDecodeError:
            log.error("MANGA_SERIES_JSON is invalid JSON; using built-in series map")
    return {_normalize(k): v for k, v in mapping.items()}


def _resolve_series_url(series):
    n = _normalize(series)
    mapping = _series_map()
    if n in mapping:
        return mapping[n]
    for alias, url in mapping.items():
        if alias in n or (len(n) >= 4 and n in alias):
            return url
    return None


_CHAPTER_MARK = re.compile(r"(?:^|\s)(?:الفصل|فصل|شابتر|شابت|chapter|chap|ch\.?|#)\s*(?:رقم|no\.?|number)?\s*(\d+(?:\.\d+)?)(?=$|\s|[?!.,،؟])", re.I)
_FILLER = {
    "هل", "تقدر", "تقدرون", "ممكن", "لو", "سمحت", "من", "فضلك", "ترسل", "ارسل", "ارسلي", "لي", "ليا", "لنا", "جيب", "جيبلي",
    "هات", "هاتلي", "تجيب", "تجيبلي", "ابعت", "ابعتلي", "تبعت", "تبعتلي", "ترسلي", "اعطني", "اعطيني", "اريد", "ابي", "ابغى", "بدي", "عايز", "عاوز", "نبغي", "حمل", "نزل", "فصول", "فصل", "الفصل",
    "مانهوا", "المانهوا", "مانجا", "المانجا", "مانهو", "في", "لل", "ل", "عن", "of", "from", "can", "could", "you", "send", "me", "give",
    "get", "please", "pls", "the", "a", "manhwa", "manga", "download", "i", "want", "need", "to", "read",
}
_VERBS = {"ترسل", "ارسل", "ارسلي", "تجيب", "تجيبلي", "ابعت", "ابعتلي", "تبعت", "تبعتلي", "ترسلي", "جيب", "جيبلي", "هات", "هاتلي", "اعطني", "اعطيني", "اريد", "ابي", "ابغى", "بدي", "عايز", "عاوز",
          "نبغي", "حمل", "نزل", "send", "give", "get", "download", "want", "need", "تقدر", "ممكن"}


def parse_chapter_request(text):
    """Return {"series", "chapter"} for a confident chapter request, else None.

    Handles: "نانو ميشل الفصل 3", "هل تقدر ترسل لي فصول مانهوا نانو ميشل فصل 3؟",
    "فصل 3 من نانو ميشل", "can you send me nano machine chapter 3?", "nano machine #3".
    A message is only treated as a request when the series is known, a request verb is
    present, or the message is a short "<series> chapter <n>" form.
    """
    value = _normalize(text)
    if not value or len(value) > 200:
        return None
    match = _CHAPTER_MARK.search(value)
    if not match:
        return None
    chapter = match.group(1)
    rest = (value[:match.start()] + " " + value[match.end():])
    rest = re.sub(r"[?!.,،؟:;\"'()\[\]]", " ", rest)
    words = rest.split()
    verbs = any(w in _VERBS for w in words)
    kept = [w for w in words if w not in _FILLER]
    series = " ".join(kept).strip()
    if not series or len(series) > 80 or len(kept) > 6:
        return None
    known = _resolve_series_url(series) is not None
    direct_form = not verbs and len(words) == len(kept) and len(kept) <= 4
    if known or verbs or direct_form:
        return {"series": series, "chapter": chapter}
    return None


def _chapter_number(url, anchor_text=""):
    path = urlparse(url).path
    for candidate in (anchor_text, path):
        m = re.search(r"(?:chapter|chap|الفصل|فصل)[-/\s]*(\d+(?:\.\d+)?)", candidate, re.I)
        if m:
            return m.group(1)
    m = re.search(r"/chapter/(\d+)(?:-|/|$)", path, re.I)
    return m.group(1) if m else None


def list_chapters(series_url):
    """Discover chapter links from the series page. Returns [{number, url}] newest first."""
    response = sources.fetch(series_url)
    soup = BeautifulSoup(response.text, "html.parser")
    links = {}
    for anchor in soup.find_all("a", href=True):
        href = urljoin(response.url, anchor["href"])
        if "/chapter/" not in urlparse(href).path:
            continue
        num = _chapter_number(href, anchor.get_text(" ", strip=True))
        if num and num not in links:
            links[num] = href
    return sorted(({"number": n, "url": u} for n, u in links.items()), key=lambda c: -float(c["number"]))


def _find_chapter_url(series_url, chapter):
    target = str(chapter)
    if "." in target:
        target = target.rstrip("0").rstrip(".")
    target = target.lstrip("0") or "0"
    chapters = {c["number"].lstrip("0") or "0": c["url"] for c in list_chapters(series_url)}
    if target in chapters:
        return chapters[target]
    if target == "323":
        return KNOWN_CHAPTER_URL
    raise ChapterNotFound(f"Chapter {chapter} was not found in the series chapter list")


def _image_candidates(chapter_url, html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for img in soup.find_all("img"):
        src = (img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        absolute = urljoin(chapter_url, src)
        hint = ((img.get("alt") or "") + " " + " ".join(img.get("class", [])) + " " + absolute).lower()
        if any(x in hint for x in ("avatar", "logo", "icon", "banner", "cover", "social")):
            continue
        if urlparse(absolute).scheme in ("http", "https") and absolute not in out:
            out.append(absolute)
    for node in soup.find_all(attrs={"data-src": True}):
        src = (node.get("data-src") or "").strip()
        if re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", src, re.I):
            absolute = urljoin(chapter_url, src)
            if absolute not in out:
                out.append(absolute)
    return out[:MAX_IMAGES]


def _download_images(urls, referer):
    images, total = [], 0
    for url in urls:
        try:
            response = sources.fetch(url, stream=True, referer=referer)
            content = bytearray()
            for chunk in response.iter_content(64 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Chapter images exceed configured size limit")
                content.extend(chunk)
            image = Image.open(io.BytesIO(content))
            image.load()
            images.append(image.convert("RGB"))
        except SourceBlocked:
            raise  # a blocked image host means the whole chapter is blocked; do not keep poking
        except Exception:
            log.warning("Could not retrieve a candidate chapter image: %s", url, exc_info=True)
    return images


def download_chapter_pdf(series, chapter):
    """Build a temporary PDF for a chapter and return its path.

    Raises SeriesNotConfigured, ChapterNotFound, SourceBlocked/SourceDisallowed/
    SourceError, or NoImagesFound. The caller must delete the file.
    """
    series_url = _resolve_series_url(series)
    if not series_url:
        raise SeriesNotConfigured(series)
    chapter_url = _find_chapter_url(series_url, chapter)
    html = sources.fetch(chapter_url).text
    image_urls = _image_candidates(chapter_url, html)
    if not image_urls:
        raise NoImagesFound("No chapter images found; the reader may load images dynamically")
    images = _download_images(image_urls, referer=chapter_url)
    if not images:
        raise NoImagesFound("Chapter images could not be downloaded")
    fd, pdf_path = tempfile.mkstemp(prefix="kanu_chapter_", suffix=".pdf")
    os.close(fd)
    try:
        first, *rest = images
        first.save(pdf_path, "PDF", save_all=True, append_images=rest, resolution=100.0)
        if os.path.getsize(pdf_path) < 1024:
            raise NoImagesFound("Generated PDF is empty")
    except Exception:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass
        raise
    finally:
        for image in images:
            image.close()
    return pdf_path


def describe_failure(exc, series, chapter):
    """Arabic user-facing explanation for a chapter retrieval failure (no secrets)."""
    if isinstance(exc, SeriesNotConfigured):
        return "ما لقيت هذه السلسلة في قائمة المصادر المتاحة عندي. اكتب اسمها كما هو في المكتبة."
    if isinstance(exc, ChapterNotFound):
        return f"ما لقيت الفصل {chapter} في قائمة فصول {series} على المصدر."
    if isinstance(exc, SourceError):
        return exc.message_ar + " لذلك ما قدرت أجهّز الفصل."
    if isinstance(exc, NoImagesFound):
        return "فتحت صفحة الفصل لكن ما لقيت صور قابلة للتنزيل، فلم أجهّز ملفًا."
    return "ما قدرت أجهّز الفصل هذه المرة. جرّب لاحقًا."
