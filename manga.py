"""Authorized manga source adapter for chapter discovery and PDF assembly.

The adapter starts from a known series page, discovers chapter URLs from its HTML,
extracts likely chapter-page images, and assembles a PDF. Site HTML may change;
verify against the source's allowed access/reuse terms before production use.
"""
import io
import json
import logging
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

log = logging.getLogger(__name__)
TIMEOUT = (8, 25)
MAX_IMAGES = int(os.getenv("MANGA_MAX_IMAGES", "100"))
MAX_DOWNLOAD_BYTES = int(os.getenv("MANGA_MAX_DOWNLOAD_BYTES", str(24 * 1024 * 1024)))
USER_AGENT = os.getenv("MANGA_USER_AGENT", "KANU-Bot-V3/1.0 (authorized chapter retrieval)")

# Add other series pages here or configure MANGA_SERIES_JSON in Render.
DEFAULT_SERIES = {
    "nano machine": "https://mangawy.org/series/nm-lkim9hef",
    "nano-machine": "https://mangawy.org/series/nm-lkim9hef",
    "نانو ميشل": "https://mangawy.org/series/nm-lkim9hef",
    "نانو ماشين": "https://mangawy.org/series/nm-lkim9hef",
    "نانو ماشين": "https://mangawy.org/series/nm-lkim9hef",
    "nano machine manhwa": "https://mangawy.org/series/nm-lkim9hef",
}
KNOWN_CHAPTER_URL = "https://mangawy.org/series/nm-lkim9hef/chapter/323-r7te8j8g"

def _normalize(value):
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = value.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي"}))
    value = re.sub(r"[ًٌٍَُِّْـ]", "", value)
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

def parse_chapter_request(text: str):
    value = _normalize(text)
    patterns = (
        r"^(?:(?:هل\s+)?(?:تقدر|ممكن|ممكنك)\s+)?(?:ترسل|تجيب|تجلب|جيب|هات|اعطني|أعطني|ارسل|أرسل|اريد|أريد|بدي|ابغى|عايز)\s+(?:لي\s+)?(?:فصول?\s+)?(?:مانهوا\s+|مانجا\s+|المانهوا\s+|المانجا\s+)?(?P<series>.+?)\s+(?:الفصل(?:\s+رقم)?|فصل|شابتر|chapter|ch\.?)\s*(?P<chapter>\d+(?:\.\d+)?)$",
        r"^(?P<series>.+?)\s+(?:الفصل(?:\s+رقم)?|فصل|شابتر|شابت(?:ر)?|chapter|ch\.?)\s*(?P<chapter>\d+(?:\.\d+)?)$",
        r"^(?P<series>.+?)\s*#\s*(?P<chapter>\d+(?:\.\d+)?)$",
    )
    for pattern in patterns:
        match = re.match(pattern, value, re.I)
        if match:
            series = match.group("series").strip()
            for _ in range(2):
                series = re.sub(r"^(?:(?:هل\s+)?(?:تقدر|ممكن|ممكنك)\s+)?(?:ترسل|تجيب|تجلب|جيب|هات|اعطني|أعطني|ارسل|أرسل|اريد|أريد|بدي|ابغى|عايز)(?:\s+لي)?\s+", "", series, flags=re.I)
                series = re.sub(r"^(?:فصول?\s+)?(?:مانهوا|مانجا|المانهوا|المانجا)\s+", "", series, flags=re.I)
            if series and len(series) <= 120:
                return {"series": series.strip(), "chapter": match.group("chapter")}
    return None

def _resolve_series_url(series):
    n = _normalize(series)
    mapping = _series_map()
    if n in mapping:
        return mapping[n]
    for alias, url in mapping.items():
        if alias in n or n in alias:
            return url
    # Do not guess a URL for an unknown series.
    return None

def _get(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    response.raise_for_status()
    return response

def _chapter_number(url, anchor_text=""):
    path = urlparse(url).path
    candidates = [anchor_text, path]
    for candidate in candidates:
        # Common slug forms: chapter/323-slug, chapter-323, الفصل-323
        m = re.search(r"(?:chapter|chap|الفصل|فصل)[-/\s]*(\d+(?:\.\d+)?)", candidate, re.I)
        if m:
            return m.group(1)
    m = re.search(r"/chapter/(\d+)(?:-|/|$)", path, re.I)
    return m.group(1) if m else None

def _find_chapter_url(series_url, chapter):
    # The supplied known chapter is a safe fallback only for chapter 323.
    series_response = _get(series_url)
    soup = BeautifulSoup(series_response.text, "html.parser")
    links = {}
    for anchor in soup.find_all("a", href=True):
        href = urljoin(series_response.url, anchor["href"])
        if "/chapter/" not in urlparse(href).path:
            continue
        num = _chapter_number(href, anchor.get_text(" ", strip=True))
        if num and num not in links:
            links[num] = href
    target = str(chapter).rstrip("0").rstrip(".") if "." in str(chapter) else str(chapter)
    if target in links:
        return links[target]
    if target == "323" and "323" not in links:
        return KNOWN_CHAPTER_URL
    raise LookupError(f"Chapter {chapter} was not found in the series chapter list")

def _image_candidates(chapter_url, html):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for img in soup.find_all("img"):
        src = (img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
               or img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        absolute = urljoin(chapter_url, src)
        alt = (img.get("alt") or "").lower()
        cls = " ".join(img.get("class", [])).lower()
        # Filter obvious UI images; retain reader/page/chapter image candidates.
        if any(x in (alt + " " + cls + " " + absolute.lower())
               for x in ("avatar", "logo", "icon", "banner", "cover", "social")):
            continue
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        if absolute not in candidates:
            candidates.append(absolute)
    # Some readers store image URLs in data attributes rather than img src.
    for node in soup.find_all(attrs={"data-src": True}):
        src = (node.get("data-src") or "").strip()
        if re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", src, re.I):
            absolute = urljoin(chapter_url, src)
            if absolute not in candidates:
                candidates.append(absolute)
    return candidates[:MAX_IMAGES]

def _download_images(urls):
    images = []
    total = 0
    for url in urls:
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT, "Referer": "https://mangawy.org/"},
                                    timeout=TIMEOUT, stream=True)
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Chapter images exceed configured size limit")
                content.extend(chunk)
            image = Image.open(io.BytesIO(content))
            image.load()
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            elif image.mode == "L":
                image = image.convert("RGB")
            images.append(image)
        except Exception:
            log.warning("Could not retrieve a candidate chapter image: %s", url, exc_info=True)
    return images

def download_chapter_pdf(series, chapter):
    """Return a temporary PDF path for a chapter, or raise an actionable exception."""
    series_url = _resolve_series_url(series)
    if not series_url:
        raise LookupError("I do not have a configured source page for this series yet")
    chapter_url = _find_chapter_url(series_url, chapter)
    chapter_response = _get(chapter_url)
    image_urls = _image_candidates(chapter_url, chapter_response.text)
    if not image_urls:
        raise RuntimeError("No chapter images were found; the reader may load images dynamically")
    images = _download_images(image_urls)
    if not images:
        raise RuntimeError("Chapter images could not be downloaded")
    fd, pdf_path = tempfile.mkstemp(prefix="kanu_chapter_", suffix=".pdf")
    os.close(fd)
    try:
        first, *rest = images
        first.save(pdf_path, "PDF", save_all=True, append_images=rest, resolution=100.0)
    except Exception:
        try:
            os.unlink(pdf_path)
        except OSError:
            pass
        raise
    finally:
        for image in images:
            try:
                image.close()
            except Exception:
                pass
    return pdf_path

def get_chapter_status(series: str, chapter: str) -> str:
    # Kept for compatibility with callers; app.py should call download_chapter_pdf
    # for actual delivery and only send a success message after upload succeeds.
    return (
        f"تمام، فهمت طلبك: {series} الفصل {chapter} 📚\n"
        "سأحاول جلب الفصل وإرساله الآن."
    )
