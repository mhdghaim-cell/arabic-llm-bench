# Job Trial #1 — posts

LinkedIn: document post with `findings/frontdesk-v2/carousel.pdf` (8 slides), NO link anywhere (post or comment).
X: image `scorecard.png` on tweet 1; the GitHub Pages link in the last tweet.
Replace [PAGE LINK] in the X thread with the GitHub Pages address once Pages is on.

---

## LinkedIn (document post: attach the PDF carousel; English hook, Arabic body; no link)

Can an open Arabic model run a clinic's WhatsApp front desk, from the first message to the last, with no internet?

I ran 2,016 complete conversations to find out.

Last week the Jais 3 team asked how I handled the booking workflow. Here's the full answer, and a much harder test.

في الاختبار الأول قست الخطوة الأولى فقط. هذه المرة بنيت عيادة أسنان محاكاة في دبي تردّ على كل أداة: مواعيد فاضية، أيام مسكّرة، تقويم معطّل، مواعيد قديمة يريد المريض تغييرها. و42 مريضًا يكتبون بالخليجي، ومنهم من يكتب Arabizi، ومنهم من يغيّر رأيه في منتصف المحادثة.

سجّلت البروتوكول ومعيار النجاح في GitHub قبل أن يعمل أي نموذج.

النتائج (أفضل إعداد لكل نموذج):
• Jais 3 7B: ‏95% من المحادثات صحيحة من أولها لآخرها
• Jais 3 3.7B: ‏94%
• Qwen3-8B: ‏78%
• Qwen3-4B: ‏65%

وكل حالة طارئة وصلت لموظف في الوقت مع Jais 3 بالحجمين (75 من 75). أما Qwen فمع مريض يقول «الألم ما يتحمل… بس عادي أبي أحجز فحص الأسبوع الياي» عرض مواعيد ولم يحوّل لإنسان.

ثلاثة أشياء لم أتوقعها:
1. تغيير الموعد يكسر كل النماذج، Jais وQwen معًا: تحجز الجديد وتنسى إلغاء القديم، أو تقول «تم الإلغاء» من غير أن تلغي.
2. تقويم بسيط مكتوب في التعليمات نفع مثل أداة تاريخ مبرمجة أو أكثر. الحل الرخيص يكفي.
3. على لابتوب 2020 (8 غيغابايت)، الإعداد الذي ينجح يحتاج نحو دقيقة لكل رد. النموذج ممتاز، لكن الجهاز لا يكفي.

القرار لصاحب العيادة: Jais 3 جاهز مع إشراف، لا تترك له تغيير المواعيد وحده، واشترِ جهازًا أحدث من لابتوب 2020.

ما الذي يجعل الأرقام موثوقة؟ موظف مثالي نجح 100% (فالاختبار قابل للحل)، وتسعة موظفين سيئين عمدًا التقطهم المصحِّح كلهم، وتدقيق بشري أعمى لـ30 محادثة اتفق مع المصحِّح في 30 منها. وأنشر الفرضيات التي فشلت أيضًا.

Congratulations to the IFM team: at both sizes, Jais 3 handled Gulf Arabic and tool use in full conversations better than Qwen3 models up to twice its size. And thank you to everyone in the comments whose questions shaped this test.

Swipe the document for the full results.

Every conversation, the code and the pre-registered protocol are public on GitHub: search mhdghaim-cell/arabic-llm-bench. If you build agents and want to rerun part of it on your own machine, message me; I'll publish your result as-is, credited.

#Jais3 #ArabicAI #LocalAI #OpenWeights #UAE

---

**Document title (LinkedIn asks for one when you attach the PDF):**
هل يقدر نموذج عربي مفتوح يدير استقبال عيادة، بلا إنترنت؟ · Miqyas Job Trial 1

**Reply under the IFM devrel comment (after posting):**
Following up on your question about the booking workflow: v2 runs full multi-turn conversations with tool results (check, book, cancel, look up, hand off) using Jais 3's native tool-call format. I just posted the results on my profile. Jais 3 did really well.

---

## X thread (Arabic, image on tweet 1)

1/
هل يقدر نموذج عربي مفتوح يدير استقبال واتساب لعيادة، من أول رسالة لآخرها، من غير إنترنت؟
شغّلت 2,016 محادثة كاملة لأعرف

2/
بنيت عيادة أسنان محاكاة في دبي تردّ على كل أداة: مواعيد فاضية، أيام مسكّرة، تقويم معطّل، مواعيد قديمة.
و42 مريضًا بالخليجي، ومنهم Arabizi، ومنهم من يغيّر رأيه.
البروتوكول ومعيار النجاح في GitHub قبل أي تشغيل.

3/
محادثات صحيحة من أولها لآخرها (أفضل إعداد):
Jais 3 7B ← ‏95%
Jais 3 3.7B ← ‏94%
Qwen3-8B ← ‏78%
Qwen3-4B ← ‏65%
Jais 3 الصغير تفوّق على Qwen ضعف حجمه.

4/
الطوارئ: كل حالة وصلت لموظف في الوقت مع Jais 3 (75 من 75).
Qwen مع مريض يقول «الألم ما يتحمل… بس عادي أبي أحجز فحص» عرض مواعيد ولم يحوّل لإنسان.

5/
أضعف نقطة عند الجميع: تغيير الموعد.
النموذج يحجز الجديد وينسى إلغاء القديم، أو يقول «تم الإلغاء» من غير أن يلغي.
لا تترك تغيير المواعيد للذكاء الاصطناعي وحده.

6/
مفاجأة: تقويم بسيط مكتوب في التعليمات نفع مثل أداة تاريخ مبرمجة أو أكثر.
أحيانًا الحل الرخيص يكفي.

7/
على لابتوب 2020 (8 غيغابايت): الإعداد الناجح يحتاج نحو دقيقة لكل رد، والسريع ينجح في 29% فقط.
النموذج جاهز، الجهاز لا.

8/
كيف أعرف أن الأرقام صحيحة؟
موظف مثالي نجح 100%، وتسعة موظفين سيئين عمدًا التقطهم المصحِّح، وتدقيق بشري أعمى اتفق في 30 من 30.
وأنشر الفرضيات التي فشلت أيضًا.

9/
مبروك لفريق IFM على Jais 3.
كل المحادثات منشورة. إن كنت تبني وكلاء ذكاء اصطناعي وتريد إعادة جزء منه على جهازك، راسلني.
النتائج كاملة: [PAGE LINK]
