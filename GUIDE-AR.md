# دليل النشر — KANU Bot V3 v3.7.0 (Android + GitHub + Render)

> لا تنشر قبل مراجعتك. هذا الدليل يوصلك لنسخة جاهزة على فرع جانبي، ولا يغيّر الموقع الحي حتى تقرر أنت.

## 0) قبل البدء
- احتفظ بنسخة من ZIP القديم (v3.6) كنسخة احتياطية.
- لا ترسل أي مفتاح أو رمز لأي شخص، ولا تكتبه في ملفات المشروع.

## 1) الطريقة الموصى بها: Termux + git (تحفظ المجلدات كما هي)
1. حمّل `KANU-Bot-V3-v3.7.0.zip` إلى مجلد Downloads.
2. في Termux (مرة واحدة): `pkg install git unzip python -y` ثم `termux-setup-storage` ووافق على الإذن.
3. استنسخ المستودع وأنشئ فرعًا جانبيًا:
```
cd ~
git clone https://github.com/evccnxhc-commits/KANU-Bot-V3.git
cd KANU-Bot-V3
git checkout -b v3.7-redesign
```
4. احذف الملفات القديمة المكررة، ثم فك الحزمة فوقها (محتوياتها في الجذر مباشرة):
```
rm -f index.html app.js style.css UPLOAD-AR.md
unzip -o ~/storage/downloads/KANU-Bot-V3-v3.7.0.zip -d .
ls
```
   يجب أن ترى `app.py` و`templates` و`static` و`data` و`tests`.
5. (اختياري لكنه مفيد) اختبر محليًا:
```
pip install -r requirements.txt
python -m unittest discover -s tests
```
6. ارفع الفرع:
```
git add -A
git commit -m "KANU V3.7: fix library pages, chat redesign, messenger dedupe"
git push -u origin v3.7-redesign
```
   عند طلب كلمة المرور استخدم **Personal Access Token** من GitHub (Settings ← Developer settings ← Tokens) واكتبه في Termux فقط.

## 2) بديل بلا Termux: من متصفح GitHub
1. افتح المستودع ← زر الفرع ← اكتب `v3.7-redesign` ← Create branch.
2. لكل ملف: Add file ← Create new file، واكتب المسار كاملًا في خانة الاسم، مثل `templates/chat.html` (الشرطة المائلة تنشئ المجلد)، والصق المحتوى. كرّر لكل ملفات `templates/` و`static/` و`data/` و`tests/` والملفات الجذرية.
3. الصورة `static/team-sponsor.jpg`: Add file ← Upload files داخل مجلد static.
4. احذف من الفرع: `index.html` و`app.js` و`style.css` و`UPLOAD-AR.md` في الجذر.

## 3) متغيرات البيئة في Render (Environment) — الأسماء فقط
| الاسم | مطلوب؟ | الوظيفة |
|---|---|---|
| `SECRET_KEY` | نعم | مفتاح الجلسات (ولّده بـ `python -c "import secrets;print(secrets.token_hex(32))"`) |
| `COOKIE_SECURE` | نعم | `true` على Render |
| `GROQ_API_KEY` / `CEREBRAS_API_KEY` / `OPENROUTER_API_KEY` / `NVIDIA_API_KEY` | واحد على الأقل | مزوّدو الذكاء الاصطناعي بالترتيب |
| `VERIFY_TOKEN` | لـMessenger | رمز التحقق في إعداد webhook |
| `FACEBOOK_APP_SECRET` | لـMessenger | للتحقق من توقيع الأحداث (بدونه يُرفض الـwebhook) |
| `PAGE_ACCESS_TOKEN` | لـMessenger | الإرسال عبر الصفحة |
| `GRAPH_API_VERSION` | اختياري | افتراضي `v23.0` |
| `DATABASE_PATH` | اختياري | مسار SQLite (انظر قسم التخزين) |
| `KANU_SHOW_DEMO` | اختياري | `false` دائمًا في الإنتاج |
| `DUA_CHANCE` | اختياري | احتمال إضافة الدعاء (0 إلى 1، افتراضي 0.6) |
| `MANGA_SERIES_JSON` | اختياري | سلاسل إضافية: `{"الاسم":"رابط صفحة السلسلة"}` |

القيم الموجودة حاليًا في Render **لا تغيّرها**؛ التحديث لا يمسّها.

## 4) التخزين (مهم)
على الخطة المجانية، ملفات Render مؤقتة: قد تضيع الحسابات والمحادثات عند إعادة التشغيل أو النشر. لحفظ دائم تحتاج قرصًا دائمًا (مدفوعًا) تضبط `DATABASE_PATH` على مساره، مثل `/var/data/kanu.sqlite3`. إلى ذلك الحين اعتبر الحسابات والمحادثات **غير مضمونة البقاء**.

## 5) النشر بعد موافقتك
1. على GitHub: افتح Pull Request من `v3.7-redesign` إلى `main` وراجع الملفات.
2. عندما تقرر: ادمج الـPR. Render ينشر تلقائيًا إن كان Auto-Deploy مفعّلًا (وإلا Manual Deploy).
3. لتجربة قبل الدمج: غيّر Branch الخدمة في Render إلى `v3.7-redesign` ثم أعده إلى `main`. (هذا نشر فعلي؛ افعله عن قصد.)

## 6) فحص ما بعد النشر (افعله بنفسك)
1. `/health` يجب أن يُظهر `"status":"ok"` و`"templates":true` و`"database":true`. إن ظهر `templates:false` فمجلد `templates/` ناقص على GitHub.
2. افتح `/` و`/manga` و`/novels` وصفحة Nano Machine.
3. أنشئ حسابًا (كلمة مرور 10 أحرف مع حرف ورقم) وأرسل رسالة. إن لم تُضبط مفاتيح الذكاء الاصطناعي سترى رسالة خطأ واضحة.
4. في صفحة العمل اضغط «افحص التوفر الآن» و«تحميل قائمة الفصول»: ستعرف إن كان المصدر يرفض (403) أو يسمح.
5. Messenger: أرسل «نانو ميشل الفصل 3» من الصفحة. النجاح الحقيقي هو وصول ملف PDF إليك. الرسالة «تم إرسال…» لا تظهر إلا بعد تأكيد Meta. إن رفض المصدر الوصول ستصلك رسالة تشرح السبب.
6. أرسل رسالة مرتين متتاليتين للتأكد من عدم تكرار الرد.

## 7) صورة فريق TURBO DZ
الملف `static/team-sponsor.jpg` هو الموجود في الحزمة القديمة. للاستبدال بالأصلية: ارفع صورتك بالاسم نفسه داخل `static/`. تُعرض صغيرة بالأبيض والأسود في التذييل فقط، والملف الأصلي لا يُعدَّل.

## 8) أعطال شائعة
- 500 في `/manga`: مجلد `templates/` ناقص (انظر `/health`).
- الرسائل لا تصل من Messenger: تأكد من `FACEBOOK_APP_SECRET` و`PAGE_ACCESS_TOKEN` و`VERIFY_TOKEN` في Render، وراجع Logs.
- تسجيل خروج متكرر: `SECRET_KEY` غير مضبوط أو تغيّر.
