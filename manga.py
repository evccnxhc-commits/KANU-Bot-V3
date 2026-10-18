"""Manga request parsing and authorized-source integration boundary."""
import re
import unicodedata

def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = re.sub(r"\s+", " ", text).strip()
    return text

CHAPTER_PATTERNS = (
    re.compile(r"^(?P<series>.+?)\s+(?:الفصل(?:\s+رقم)?|فصل|شابتر|شابت(?:ر)?|chapter|ch\.?)\s*(?P<chapter>\d+(?:\.\d+)?)\s*$", re.I),
    re.compile(r"^(?P<series>.+?)\s*#\s*(?P<chapter>\d+(?:\.\d+)?)\s*$", re.I),
    re.compile(r"^(?:هات|جيب|اعطني|أعطني|اريد|أريد|بدي|ابغى|عايز)\s+(?P<series>.+?)\s+(?:الفصل|فصل|شابتر|chapter|ch\.?)\s*(?P<chapter>\d+(?:\.\d+)?)\s*$", re.I),
)

def parse_chapter_request(text: str):
    cleaned = _normalize(text)
    for pattern in CHAPTER_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            series = match.group("series").strip(" -:#")
            chapter = match.group("chapter")
            # Avoid treating generic imperative prefixes as part of the series name.
            series = re.sub(r"^(?:هات|جيب|اعطني|اريد|بدي|ابغى|عايز)\s+", "", series, flags=re.I)
            if series and len(series) <= 120:
                return {"series": series, "chapter": chapter}
    return None

def get_chapter_status(series: str, chapter: str) -> str:
    # Honest status until a source adapter and authorized file delivery are configured.
    return (
        f"تمام، {series} الفصل {chapter} 📚 فهمت طلبك!\n"
        "مصدر جلب الفصول وتحويلها إلى PDF لم يُربط بعد في هذه النسخة، "
        "لذلك لم أحمّل الفصل فعليًا. نكمل ربط مصدر مانجاوي المصرّح به واختبار الإرسال."
    )
