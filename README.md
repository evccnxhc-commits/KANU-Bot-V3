# KANU Bot V3 — v3.7.0

مشروع مستقل (لا علاقة له بمشروع KANU/MangaDar القديم). تطبيق Flask: واجهة محادثة عربية RTL، مكتبتا المانهوا والروايات، وتكامل Meta Messenger.

- التدقيق وسبب أخطاء 500: `AUDIT.md`
- النشر خطوة بخطوة (Android + GitHub + Render): `GUIDE-AR.md`

## المسارات
| المسار | الوظيفة |
|---|---|
| `/` | المحادثات (قائمة جانبية، سجل، حفظ لكل مستخدم) |
| `/manga` ، `/manga/<slug>` | مكتبة المانهوا وصفحة العمل |
| `/novels` ، `/novels/<slug>` | مكتبة الروايات وصفحة العمل |
| `/health` | حالة الخدمة (قاعدة البيانات والقوالب؛ بلا أسرار) |
| `/webhook` | Meta Messenger (GET تحقق، POST أحداث موقّعة) |
| `/api/*` | واجهات JSON (جلسة، حساب، محادثات، فحص مصدر) |

## البنية
```
app.py llm.py manga.py books.py messenger.py db.py sources.py catalog.py
data/manga.json data/novels.json      ← الكتالوج (أنت تديره)
templates/  static/  tests/
requirements.txt Procfile render.yaml .env.example
```

## تشغيل محلي واختبار
```
pip install -r requirements.txt
COOKIE_SECURE=false SECRET_KEY=dev python app.py
python -m unittest discover -s tests -v
```

## إضافة عمل إلى المكتبة
عدّل `data/manga.json` أو `data/novels.json` (حقول: `slug` بحروف إنجليزية صغيرة وأرقام وشرطات، `title`، `title_ar` اختياري، `categories`، `source_url`، `source_name`، `cover` اختياري برابط صورة تملك حق استخدامها). لا يعرض KANU إلا ما أضفته. `featured: true` يُظهر العمل في «مقترحة»، و`added: "2026-10-20"` في «أُضيفت حديثًا». أضف سلسلة للطلب عبر Messenger في `MANGA_SERIES_JSON`.

## حدود مهمة
- SQLite على Render المجاني مؤقتة (قد تضيع الحسابات/المحادثات عند إعادة التشغيل).
- لا تحقق بريد ولا استعادة كلمة مرور. لا تدقيق أمني متخصص.
- المصادر الخارجية: يحترم KANU ملف robots.txt ولا يتجاوز حماية أي موقع (403 يُعرض كما هو).
- تنزيل الفصول عبر الويب غير مفعّل؛ الإرسال عبر Messenger فقط، ولا يُعلن النجاح قبل تأكيد Meta.
- كل الاختبارات المرفقة محلية بلا شبكة؛ لا تثبت عمل Render أو Meta أو المصادر الحية.
