"""Book (novel) intent detection and routing to known source pages.

KANU does not invent links and does not send book files. It only points to pages the
project owner has configured.
"""
import re
import unicodedata

from llm import get_last_assistant_context, set_last_assistant_context

IKADOLI_URL = "https://bo.afedne.com/book/2235/%D8%A5%D9%8A%D9%83%D8%A7%D8%AF%D9%88%D9%84%D9%8A_-_%D9%85%D9%85%D9%84%D9%83%D8%A9_%D8%A7%D9%84%D8%A8%D9%84%D8%A7%D8%BA%D8%A9"
AFEDNE_HOME = "https://bo.afedne.com/"

_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
BOOK_WORDS = {"روايه", "روايات", "كتاب", "كتب", "pdf", "novel", "novels", "book", "books"}
REQUEST_WORDS = {"جيب", "جيبلي", "هات", "هاتلي", "بدي", "اريد", "ابغى", "ابي", "عايز", "عاوز", "نبغي", "تقدر", "ممكن", "حمل", "تحميل",
                 "نزل", "ارسل", "ارسلي", "ترسل", "اعطني", "ابحث", "دور", "ادور", "find", "send", "give", "get", "download"}


def normalize(text):
    text = unicodedata.normalize("NFKC", text or "").lower().translate(_LETTERS)
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(n):
    return set(re.findall(r"[\w]+", n))


def _book_name(n):
    if "ايكادولي" in n or "مملكه البلاغه" in n:
        return "ikadoli"
    if re.search(r"(?:^|\s)(?:ارسس|اراسس|ارسي)(?:\s|$)", n):
        return "arss"
    return None


def _is_general_book_request(n):
    t = _tokens(n)
    return bool(t & BOOK_WORDS) and bool(t & REQUEST_WORDS) and len(t) <= 12


def looks_like_book_followup(text, sender_id=None):
    n = normalize(text)
    return bool(_book_name(n)) or (get_last_assistant_context(sender_id) == "awaiting_book_title" and len(n.split()) <= 8)


def handle_book_request(text, sender_id=None):
    """Return a reply string if the message is a book request, else None."""
    n = normalize(text)
    context = get_last_assistant_context(sender_id)
    name = _book_name(n)
    awaiting = context == "awaiting_book_title"

    if not name and not _is_general_book_request(n) and not (awaiting and len(n.split()) <= 8):
        if awaiting:
            set_last_assistant_context(sender_id, None)
        return None

    if name == "ikadoli":
        set_last_assistant_context(sender_id, "book:ikadoli")
        return ("هذه صفحة «إيكادولي – مملكة البلاغة» في المصدر:\n"
                f"{IKADOLI_URL}\n"
                "افتح الصفحة للقراءة أو التنزيل. KANU لا يرسل ملف الكتاب بنفسه حاليًا.")
    if name == "arss":
        set_last_assistant_context(sender_id, "book:arss")
        return ("تقصد رواية آرسس؟ ما عندي رابط موثوق ومؤكد لها، وما راح أخترع لك رابطًا. "
                "أرسل لي رابط صفحتها في المصدر وأوجّهك منه.")
    if awaiting:
        set_last_assistant_context(sender_id, None)
        return ("ما عندي هذا العنوان ضمن المصادر المُعدّة حاليًا، وما راح أخترع رابطًا. "
                f"تقدر تتصفح المصدر بنفسك: {AFEDNE_HOME}")
    set_last_assistant_context(sender_id, "awaiting_book_title")
    return "اكتب اسم الرواية اللي تبحث عنها، وأتحقق إن كانت ضمن المصادر المُعدّة."
