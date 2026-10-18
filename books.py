"""Book request handling. This module does not bypass source protections."""
import re
import unicodedata
from urllib.parse import quote

AFEDNE_BASE = "https://bo.afedne.com/"
IKADOLI_URL = "https://bo.afedne.com/book/2235/%D8%A5%D9%8A%D9%83%D8%A7%D8%AF%D9%88%D9%84%D9%8A_-_%D9%85%D9%85%D9%84%D9%83%D8%A9_%D8%A7%D9%84%D8%A8%D9%84%D8%A7%D8%BA%D8%A9"

BOOK_WORDS = ("رواية", "كتاب", "كتب", "pdf", "بي دي اف", "اقرأ", "اقرا", "تحميل رواية")

def _norm(value):
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return re.sub(r"\s+", " ", value).strip().lower()

def handle_book_request(text: str):
    normalized = _norm(text)
    if not any(word in normalized for word in BOOK_WORDS):
        return None
    if "ايكادولي" in normalized or "مملكة البلاغة" in normalized:
        return (
            "لقيت لك صفحة إيكادولي – مملكة البلاغة 📚✨\n"
            f"{IKADOLI_URL}\n"
            "تقدر تفتح الصفحة وتشوف خيارات الكتاب. إرسال ملف PDF مباشرة من البوت "
            "لم يُفعّل بعد؛ نحتاج إكمال موصل التنزيل المصرّح به واختبار إرسال المرفقات."
        )
    # Do not guess an undocumented search endpoint.
    return (
        "أكيد 📚 اكتب اسم الرواية، أو أرسل رابط صفحتها على أفدني، "
        "وسأساعدك في تجهيز ربطها. إرسال ملفات PDF مباشرة لم يُفعّل بعد."
    )
