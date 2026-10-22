# qt-01 · ALLaM 7B · X thread (Miqyas account) — DRAFT for Mahmoud's review

Every number from results.json. Quick Trial: numbers only, no verdict. Image on tweet 1: scorecard_x.png.

---
1/7
تجربة سريعة · استكشافية

اختبرنا ALLaM 7B على استقبال عيادة أسنان عبر واتساب: نفس الحالات الـ42 من تجربة العمل #1، ثلاث محاولات لكل حالة، على جهاز واحد بلا إنترنت.

محادثات صحيحة كاملة: 9%

أرقام فقط، بلا حكم.

---
2/7
الأرقام:
محادثات صحيحة كاملة: 9% (11 من 126، والنطاق المرجّح 3% إلى 17%)
صحيحة في المحاولات الثلاث: 5%
طوارئ وصلت لموظف: 1 من 25
شكاوى وأسئلة طبية وصلت لموظف: 0 من 20
زمن الرد على RTX 4090: نحو 0.6 ثانية

---
3/7
أبرز ما رأيناه: ALLaM يتعرّف على الطوارئ ويقول إنها تحتاج تدخلًا فوريًا، لكنه لا يحوّل المحادثة لموظف.

في 12 من 25 حالة طوارئ أعطى المريض رقم هاتف ليتصل عليه، وتعليمات العيادة لا تحتوي أي رقم.

---
4/7
هذه ملاحظة لم نسجّلها قبل التشغيل، فنعرضها ملاحظةً لا مقياسًا.

حذفنا الأرقام من النصوص المنشورة لأنها قد تعود لأشخاص حقيقيين، وتأكدنا أن النتائج لم تتغير بعد الحذف.

---
5/7
لماذا "تجربة سريعة" وليس حكمًا:
إعداد واحد، ومجموعة الاختبار العامة فقط.
ALLaM لا يملك صيغة خاصة لاستدعاء الأدوات، فشغّلناه عبر محوّل JSON كتبناه وسجّلناه قبل تشغيل الاختبار، بينما استخدم Jais 3 وQwen3 صيغهما الخاصة. قد يفسّر هذا جزءًا من الفارق.

---
6/7
للمقارنة على الإعداد نفسه (أداة التاريخ، بلا تفكير قبل الرد): Qwen3 4B وصل إلى 28%، وحوّل 20 من 25 حالة طوارئ.

ALLaM لا يملك وضع تفكير. النماذج التي تفكّر قبل الرد وصلت إلى 92% على الحالات نفسها.

---
7/7
المحادثات الـ144 كاملة، والمحوّل، وملف التسجيل المسبق مع تعديلاته، كلها منشورة:
https://github.com/mhdghaim-cell/arabic-llm-bench/tree/main/findings/qt01-allam-7b

إذا كان لدى فريق ALLaM إعداد أفضل لاستدعاء الأدوات، نعيد التجربة به وننشر النتيجة.

---
## Hugging Face comment (ALLaM-AI/ALLaM-7B-Instruct-preview, Community tab) — English

Quick Trial (exploratory, numbers only): ALLaM-7B-Instruct-preview (Q4_K_M, llama.cpp) as a WhatsApp front desk for a dental clinic, 42 public test scenarios × 3 runs, offline.
Fully correct conversations: 8.7% (95% CI 3.2–16.7%). Emergencies handed to staff: 1/25. Complaints and medical questions handed over: 0/20.
The model has no tool-call syntax, so it ran through a prompted-JSON adapter we pre-registered; models in our earlier trial used their native syntax. In 12/25 emergencies the model gave the patient a phone number that is not in the clinic's instructions (post-hoc observation; numbers redacted in the published transcripts).
All transcripts, the adapter and the pre-registration: https://github.com/mhdghaim-cell/arabic-llm-bench/tree/main/findings/qt01-allam-7b
If there is a recommended tool-calling setup for this model, we will rerun with it and publish the result.
