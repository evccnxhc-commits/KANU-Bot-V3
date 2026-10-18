"""Book intent detection and known Afedne book page routing."""
import re
import unicodedata
from llm import get_last_assistant_context, set_last_assistant_context

IKADOLI_URL = "https://bo.afedne.com/book/2235/%D8%A5%D9%8A%D9%83%D8%A7%D8%AF%D9%88%D9%84%D9%8A_-_%D9%85%D9%85%D9%84%D9%83%D8%A9_%D8%A7%D9%84%D8%A8%D9%84%D8%A7%D8%BA%D8%A9"
AFEDNE_HOME = "https://bo.afedne.com/"

def normalize(text):
    text = unicodedata.normalize("NFKC", text or "").lower()
    table = str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي"})
    text = text.translate(table)
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    return re.sub(r"\s+", " ", text).strip()

BOOK_INTENT = (
    "روايه", "رواية", "كتاب", "كتب", "pdf", "بي دي اف", "روايات",
    "جيب لي رواية", "هات رواية", "بدي رواية", "اريد رواية", "تقدر تجيب لي رواية",
    "تقدر تجيب رواية", "تحميل رواية", "ابغى رواية", "عايز رواية"
)

def _is_book_name(text):
    n = normalize(text)
    return any(word in n for word in ("ارسس", "اراسس", "ارسي", "ايكادولي", "مملكه البلاغه"))

def looks_like_book_followup(text, sender_id=None):
    if _is_book_name(text):
        return True
    context = normalize(get_last_assistant_context(sender_id) or "")
    n = normalize(text)
    return ("رواية" in context or "كتاب" in context) and len(n) < 100

def handle_book_request(text, sender_id=None):
    n = normalize(text)
    context = normalize(get_last_assistant_context(sender_id) or "")

    # Handle a follow-up like "رواية آرسس" after "تقدر تجيب لي رواية؟"
    book_name = None
    if "ايكادولي" in n or "مملكه البلاغه" in n:
        book_name = "ikadoli"
    elif "ارسس" in n or "اراسس" in n or "ارسي" in n:
        book_name = "arss"
    elif any(term in n for term in ("روايه", "كتاب", "pdf", "روايات")):
        # If this is only a general request, ask for a title once and store context.
        set_last_assistant_context(sender_id, "awaiting_book_title")
        return (
            "أكيد 📚 اكتب اسم الرواية اللي بدك إياها، وأنا أساعدك أبحث عنها. "
            "وإذا كتبت اسمها برسالتك التالية، سأكمل من دون ما أعيد نفس السؤال."
        )
    elif context == "awaiting_book_title" and n:
        # Any short next message can be the requested title.
        if len(n.split()) <= 8:
            book_name = "arss" if "ارسس" in n or "اراسس" in n else ("ikadoli" if "ايكادولي" in n else None)

    if book_name == "ikadoli":
        set_last_assistant_context(sender_id, "book:ikadoli")
        return (
            "لقيت لك صفحة إيكادولي – مملكة البلاغة 📚✨\n"
            f"{IKADOLI_URL}\n"
            "افتح الصفحة لتنزيل الكتاب. إرسال الملف مباشرة من البوت يحتاج استكمال ربط التنزيل وإرسال المرفقات."
        )
    if book_name == "arss":
        set_last_assistant_context(sender_id, "book:arss")
        return (
            "تمام، تقصد رواية آرسس 📚✨\n"
            "ما عندي رابط موثوق ومؤكد لها حاليًا، وما راح أخترع لك رابط. تقدر ترسل رابط صفحة الرواية على أفدني، "
            "وبعد ربط البحث بالموقع سأقدر أوجّه الطلب بشكل صحيح."
        )

    if any(term in n for term in ("روايه", "كتاب", "pdf", "روايات")):
        set_last_assistant_context(sender_id, "awaiting_book_title")
        return "أكيد 📚 اكتب اسم الرواية اللي بدك إياها، وسأتابع معك من رسالتك التالية."
    return None
