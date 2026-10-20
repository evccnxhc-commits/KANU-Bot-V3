# تعليمات رفع KANU Bot V3 v3.6 من Android

1. فك ضغط ملف ZIP.
2. ارفع محتويات الحزمة إلى جذر مستودع `KANU-Bot-V3`، وليس ملف ZIP نفسه.
3. استبدل `app.py`, `index.html`, `style.css`, `app.js`, `README.md`, و`UPLOAD-AR.md`.
4. أضف مجلد `templates` وفيه `manga.html` و`novels.html`، ومجلد `static` وفيه `team-sponsor.jpg`.
5. احتفظ بملفات `llm.py`, `manga.py`, `books.py`, `messenger.py`, `requirements.txt`, `render.yaml`, و`Procfile` ولا تستبدل أسرار Render أو ترفع `.env` الحقيقي.
6. بعد نجاح Render اختبر `/`, `/manga`, `/novels`, ثم `/health`.
7. بطاقات المكتبات اقتراحات أولية برسوم غلاف تجريبية وليست كتالوجًا حيًا. لا يعني ظهور العنوان أن كل فصل أو PDF متوفر.
8. اختبر Messenger بشكل منفصل؛ تحديث الواجهة لا يثبت أن إرسال الملفات يعمل.
