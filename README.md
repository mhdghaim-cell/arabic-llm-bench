# مقياس (miqyas)

**اختبار مستقل للنماذج مفتوحة الأوزان بالعربية.** لوحة الصدارة تقول لك كم سجّل
النموذج؛ مقياس يقول لك ماذا يحدث عندما تستخدمه: كلفة الرموز، اللهجات، استدعاء
الأدوات في مهام حقيقية، والسرعة على أجهزة يملكها الناس فعلًا. البروتوكولات تُسجَّل
في git قبل التشغيل، والمخرجات الخام تُنشر كاملة.

المؤسّس: **محمود دغيم** (Mahmoud Deghaim). سياسة [الاستقلالية والتمويل](docs/independence.md).

## النتائج المنشورة

| | التاريخ | الصفحة | البيانات |
|---|---|---|---|
| **ضريبة الرموز** — ٢٬٠٠٩ جملة، ١١ مقسّمًا، ٧ لهجات، مع فترات ثقة | 2026-10-17 | [findings/token-tax](findings/token-tax/) | [results/w4](results/w4/) |
| **موظف الاستقبال v1** — الإجراء الأول على ٤٠ رسالة خليجية (استكشافي) | 2026-10-19 | [docs/frontdesk_protocol_v1.md](docs/frontdesk_protocol_v1.md) | [results/frontdesk](results/frontdesk/) |
| **هل يقدر يشتغل؟ #1: موظف الاستقبال v2** — ٢٬٠١٦ محادثة كاملة مع عيادة محاكاة، ٤ نماذج (مسجَّل مسبقًا) | 2026-10-25 | [findings/frontdesk-v2](findings/frontdesk-v2/) | [results/frontdesk_v2](results/frontdesk_v2/) |

الموقع يضم أيضًا مسرد مصطلحات، وأداة لقياس الرموز في النصوص العربية، وحاسبة تكلفة.

- **مجاني ومفتوح** — بلا تسجيل، بلا إعلانات، بلا تتبّع.
- **لا نخترع القياسات** — أي قيمة لم تُقَس بعد تظهر كـ«لم يُقَس بعد»، لا رقم افتراضي.



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

**Independent testing of open-weight AI for Arabic.** A leaderboard tells you
how a model scored; Miqyas tells you what happens when you try to use it:
tokenizer cost, dialect handling, tool use in real workflows, and speed on
hardware people actually own. Protocols are committed to git before any run;
raw outputs are published in full.

Founder: **Mahmoud Deghaim**. [Independence and funding policy](docs/independence.md).

### Published findings

| | Date | Page | Data |
|---|---|---|---|
| **Arabic token tax** — 2,009 parallel sentences, 11 tokenizers, 7 varieties, bootstrap CIs | 2026-10-17 | [findings/token-tax](findings/token-tax/) | [results/w4](results/w4/) |
| **Front desk v1** — first-action routing on 40 Gulf WhatsApp messages (exploratory) | 2026-10-19 | [protocol v1](docs/frontdesk_protocol_v1.md) | [results/frontdesk](results/frontdesk/) |
| **Can it do the job? #1: front desk v2** — 2,016 full conversations against a simulated clinic, 4 models (pre-registered) | 2026-10-25 | [findings/frontdesk-v2](findings/frontdesk-v2/) | [results/frontdesk_v2](results/frontdesk_v2/) |

The site also has a glossary, a tokenizer playground for Arabic text, and a
TCO calculator. Every number on the site is sourced from a JSON data file
anyone can inspect or reuse.

- **Free and open** — no signup, no ads, no tracking.
- **No invented measurements** — anything not yet measured shows as
  "لم يُقَس بعد" (not measured yet), never a placeholder number.
- **Works offline** after first load, and directly from `file://`.



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
