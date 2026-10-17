"""Manga request parser and source integration boundary."""
import re

CHAPTER_PATTERNS = (
    re.compile(r"^(?P<series>.+?)\s+(?:الفصل|شابتر|chapter|ch\.?|الفصل رقم)\s*(?P<chapter>\d+(?:\.\d+)?)\s*$", re.I),
    re.compile(r"^(?P<series>.+?)\s*#\s*(?P<chapter>\d+(?:\.\d+)?)\s*$", re.I),
)

def parse_chapter_request(text: str):
    for pattern in CHAPTER_PATTERNS:
        match = pattern.match(text.strip())
        if match:
            series = match.group("series").strip(" -:#")
            chapter = match.group("chapter")
            if series and len(series) <= 120:
                return {"series": series, "chapter": chapter}
    return None

def get_chapter_status(series: str, chapter: str) -> str:
    return (
        f"فهمت طلبك: {series} — الفصل {chapter} 📚\n"
        "خدمة جلب الفصول وتحويلها إلى PDF لم تُربط بمصدر بعد. "
        "هذه النسخة لا تدّعي أنها حمّلت الفصل. الخطوة التالية هي إضافة موصل "
        "لمصدر مسموح باستخدامه، ثم اختبار إرسال الملف عبر Messenger."
    )
