"""Arabic/English chapter request parser; source downloader is a separate integration."""
import re
import unicodedata

def normalize(text):
    text = unicodedata.normalize("NFKC", text or "")
    table = str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي"})
    text = text.translate(table)
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    return re.sub(r"\s+", " ", text).strip()

CHAPTER_PATTERNS = (
    re.compile(r"^(?P<series>.+?)\s+(?:الفصل(?:\s+رقم)?|فصل|شابتر|شابت(?:ر)?|chapter|ch\.?)\s*(?P<chapter>\d+(?:\.\d+)?)\s*$", re.I),
    re.compile(r"^(?P<series>.+?)\s*#\s*(?P<chapter>\d+(?:\.\d+)?)\s*$", re.I),
    re.compile(r"^(?:تقدر تجيب لي|تقدر تجيب|جيب لي|هات لي|اعطني|اريد|بدي|ابغى|عايز|هات|جيب)\s+(?P<series>.+?)\s+(?:الفصل|فصل|شابتر|chapter|ch\.?)\s*(?P<chapter>\d+(?:\.\d+)?)\s*$", re.I),
)

def parse_chapter_request(text):
    cleaned = normalize(text)
    for pattern in CHAPTER_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            series = match.group("series").strip(" -:#")
            chapter = match.group("chapter")
            series = re.sub(r"^(?:تقدر تجيب لي|تقدر تجيب|جيب لي|هات لي|اعطني|اريد|بدي|ابغى|عايز|هات|جيب)\s+", "", series, flags=re.I)
            series = re.sub(r"^مانهوا\s+", "", series, flags=re.I)
            if series and len(series) <= 120:
                return {"series": series, "chapter": chapter}
    # Also recognize imperative phrasing with series aliases/typos.
    match = re.match(r"^(?:هات|جيب لي|جيب|اعطني|اريد|بدي|تقدر تجيب لي)\s+مانهوا\s+(.+?)\s+(?:الفصل|فصل|شابتر)\s*(\d+(?:\.\d+)?)$", cleaned, re.I)
    if match:
        return {"series": match.group(1).strip(), "chapter": match.group(2)}
    return None

def get_chapter_status(series, chapter):
    # Honest fallback until the authorized source downloader and file delivery are implemented.
    return (
        f"تمام، فهمت طلبك: {series} الفصل {chapter} 📚\n"
        "ميزة جلب الفصل وإرساله كملف لم تكتمل بعد. ما راح أقول لك إني حمّلته قبل ما يصير الإرسال فعليًا."
    )
