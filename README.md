# مقياس (miqyas)

مرجع عربي مفتوح لتشغيل نماذج الذكاء الاصطناعي محليًا: مسرد مصطلحات، أداة لقياس
الرموز في النصوص العربية، نتائج قياسات على أجهزة حقيقية، وحاسبة تكلفة. كل رقم في
الموقع مصدره ملف بيانات يمكن لأي أحد فحصه أو إعادة استخدامه.

- **مجاني ومفتوح** — بلا تسجيل، بلا إعلانات، بلا تتبّع.
- **لا نخترع القياسات** — أي قيمة لم تُقَس بعد تظهر كـ«لم يُقَس بعد»، لا رقم افتراضي.
- **يعمل بلا اتصال** بعد التحميل الأول، ويعمل مباشرة من `file://` أيضًا.

موقع ثابت (static site): HTML/CSS/JS خالص بلا إطار عمل وبلا خطوة بناء إلزامية،
جاهز للنشر على GitHub Pages.

## البنية

```
index.html                الصفحة الرئيسية
المسرد/index.html          مسرد المصطلحات
الأداة/index.html          أداة تقسيم الرموز (tokenizer playground)
المعيار/index.html         نتائج القياسات ولوحة الصدارة
الحاسبة/index.html         حاسبة تكلفة التشغيل المحلي
findings/<slug>/index.html صفحة دائمة لكل نتيجة منشورة
المنهجية/index.html         المنهجية وطريقة الاستشهاد
data/*.json                مصدر كل رقم يظهر في الموقع
assets/base.css            نظام التصميم المشترك
assets/card.js             مولّد بطاقات المشاركة المشترك
scripts/inline.mjs         يزامن نسخ البيانات المضمّنة مع data/*.json
```

## التشغيل محليًا

لا حاجة لأي أدوات — افتح `index.html` مباشرة في المتصفح، أو شغّل خادمًا بسيطًا:

```
python3 -m http.server 8000
```

بعد تعديل أي ملف في `data/`، شغّل هذا الأمر ليعيد مزامنة النسخ المضمّنة في
صفحات HTML (الاحتياط الذي يعمل حين يفشل `fetch` على `file://`):

```
npm run build
```

## البيانات

كل رقم في الموقع يُقرأ من `/data/*.json` وقت التشغيل. لا رقم مكتوب يدويًا في
صفحة HTML يوجد أيضًا في ملف بيانات — إن أردت تصحيح رقم، صحّحه في `data/` فقط.

## الترخيص

MIT. استخدم البيانات والكود كما تشاء.

للاستشهاد بالمشروع، انظر صفحة [المنهجية](./المنهجية/).

---

## miqyas (English)

An open Arabic reference for running AI models locally: a glossary, a
tokenizer playground for Arabic text, benchmark results on real hardware, and
a TCO calculator. Every number on the site is sourced from a JSON data file
anyone can inspect or reuse.

- **Free and open** — no signup, no ads, no tracking.
- **No invented measurements** — anything not yet measured shows as
  "لم يُقَس بعد" (not measured yet), never a placeholder number.
- **Works offline** after first load, and directly from `file://`.

A static site: plain HTML/CSS/JS, no framework, no required build step,
deployable to GitHub Pages as-is.

### Running locally

No tooling required — open `index.html` directly, or serve it:

```
python3 -m http.server 8000
```

After editing anything in `data/`, resync the inlined `file://` fallback
copies embedded in each HTML page:

```
npm run build
```

### License

MIT. Use the data and code freely.
