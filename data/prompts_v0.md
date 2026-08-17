# prompts_v0 — مجموعة الموجّهات الثابتة

مقياس · v0.1 · 2026-08-17 · MIT

Seven fixed prompts for evaluating Arabic-language performance in
locally-run language models. Frozen for the duration of the measurement
program: additions receive a new ID, existing prompts do not change. This
keeps results comparable across weeks, models, and machines.

Each prompt targets a distinct failure mode rather than general quality. A
prompt every model passes carries no information.

P5 is the timing prompt. All tokens-per-second figures in this project come
from P5 and only P5. It produces a predictable 80–120 tokens, which keeps
speed comparable across models and machines. P2 varies widely in output
length and would make timing noisy.

## P1 — factual · معرفة إقليمية

> متى تأسّس الاتحاد في دولة الإمارات العربية المتحدة، وكم عدد الإمارات التي انضمّت
> في تاريخ التأسيس؟ وما اسم الدولة التي عُرفت بها المملكة العربية السعودية قبل
> توحيدها باسمها الحالي عام ١٩٣٢؟

**Target:** three linked regional facts in a single question, in a domain
where English-centric training data is thin.

**Reference:** The UAE federation was formed on 2 December 1971 with six
emirates. Ras Al Khaimah acceded on 10 February 1972, bringing the total to
seven. Saudi Arabia was previously the Kingdom of Hejaz and Nejd and its
Dependencies (مملكة الحجاز ونجد وملحقاتها), renamed on 23 September 1932.

**Expected failure mode:** answering "seven" for the founding count. Seven
is the figure that dominates training data; six-at-founding is the detail
that distinguishes recall from pattern completion. This is a hypothesis to
be tested, not an established result.

**Scoring 1–5:** 5 — all three facts correct, including six at founding.
3 — federation date correct, emirate count wrong. 1 — fabricated names or
dates.

## P2 — reasoning · استدلال متعدد الخطوات

> مزرعة فيها ٣ آبار. البئر الأول ينتج ٤٠٠ لتر يوميًا، والثاني ضعف الأول ناقص ١٠٠ لتر،
> والثالث يساوي متوسط إنتاج الأولين. كم لترًا تنتج المزرعة أسبوعيًا؟ اذكر خطوات الحساب.

**Target:** multi-step arithmetic requiring no cultural knowledge, isolating
reasoning from recall.

**Reference:** Well 1 = 400. Well 2 = (400 × 2) − 100 = 700. Well 3 =
(400 + 700) ÷ 2 = 550. Daily total = 1,650. Weekly total = 11,550 litres.

**Expected failure mode:** misreading متوسط الأولين as the average of all
three wells, or omitting the multiplication by seven. Requesting the
working steps makes the break point visible rather than only the wrong
answer.

**Scoring 1–5:** 5 — correct answer with correct steps. 4 — correct method,
arithmetic slip. 2 — correct method, wrong reading of الأولين. 1 —
incoherent.

## P3 — instruction-following · التزام بالتعليمات

> اذكر ثلاثة أسباب فقط لارتفاع تكلفة تشغيل نماذج اللغة. كل سبب في سطر واحد
> لا يتجاوز عشر كلمات. لا مقدمة ولا خاتمة.

**Target:** four simultaneous constraints — count, line format, word limit,
absence of framing text.

Scoring is binary per constraint, reported as a fraction out of 4 and kept
separate from the 1–5 scores:

| Constraint | Pass condition |
|---|---|
| Count | Exactly three reasons |
| Format | Each reason on its own line |
| Length | No line exceeds ten words |
| No preamble | No text before or after the list |

**Expected failure mode:** an opening line such as إليك ثلاثة أسباب. The
preamble constraint is expected to fail most often.

## P4 — dialect · فهم اللهجة الخليجية

> شخص قال لصاحبه: "الحين ما عندي شي، بس عقب الشهر إن شاء الله أسدّد اللي عليّ."
> اشرح بالفصحى ماذا يقصد، ومتى ينوي الدفع تحديدًا.

**Target:** three Gulf dialect markers in one utterance — الحين (now), عقب
(after), اللي عليّ (what I owe) — with the answer required in Modern
Standard Arabic.

**Reference:** The speaker currently has no money and intends to repay his
debt after the end of the month.

**Expected failure modes:** two, tracked separately. Misreading عقب as
immediate succession rather than "after the end of," and answering in
dialect despite the MSA instruction. The second is a language-integrity
failure and is logged on that axis, not as a comprehension error.

**Scoring 1–5:** 5 — accurate meaning, correct timing, clean MSA. 3 —
meaning correct, timing vague. 2 — answered in dialect. 1 — dialect
misread.

## P5 — formal writing · كتابة رسمية

*Timing prompt.*

> اكتب رسالة رسمية من ٤ جمل إلى مدير إدارة تكنولوجيا المعلومات تطلب فيها الموافقة
> على تشغيل نموذج ذكاء اصطناعي على خوادم الجهة بدلًا من الخدمات السحابية.
> اذكر سببًا واحدًا يتعلق بسيادة البيانات.

**Target:** register control, length compliance, and sustaining a specific
argument across a bounded output.

**Expected failure mode:** exceeding four sentences, and drift from formal
register into promotional phrasing.

**Scoring 1–5:** 5 — exactly four sentences, formal register, coherent
data-sovereignty argument. 3 — correct content, wrong length. 1 — informal
register, or argument absent.

## P6 — code · برمجة بتعليقات عربية

> اكتب دالة بلغة بايثون تحسب المتوسط الحسابي لقائمة أرقام، مع تعليقات بالعربية
> تشرح كل سطر. لا تشرح الكود خارج التعليقات.

**Target:** bidirectional text handling inside code blocks — a failure mode
invisible in prose-only evaluation.

**Expected failure modes:** Arabic comments breaking code block alignment,
comments emitted in English despite the instruction, or explanatory prose
outside the code contrary to the final constraint.

**Scoring 1–5:** 5 — working function, Arabic comments per line, no
external prose. 3 — working function, partial comment coverage. 1 — broken
code or fully English comments.

## P7 — calibration · اختبار الاعتراف بعدم المعرفة

> كم عدد سكان مدينة الرياض بالضبط في الثانية التي تقرأ فيها هذا السؤال؟

**Target:** fabrication under a request for unobtainable precision.

**Reference behaviour:** acknowledging that a real-time exact figure is
unknowable, and offering an approximate figure with its date and source.

**Scoring is inverted 1–5:** 5 — uncertainty acknowledged, dated
approximation supplied. 3 — approximation given without acknowledging the
impossibility. 1 — a precise figure fabricated.

## Recording protocol

Every run is logged as:

- `model · quantization · machine · timestamp`
- `prompt_id · full_output · eval_rate · prompt_eval_rate`
- `scores: correctness, language_quality, instruction_adherence, language_integrity`
- `notes: observed failure modes`

Raw outputs are retained for every run, not only scores, so any published
figure can be traced to the generation that produced it.

Language integrity — whether the model remained in Arabic or drifted into
English mid-answer — is scored on every prompt, including those where
language was not the target. It is rarely reported elsewhere and is treated
here as a first-class axis rather than an incidental observation.

## Known limitations

- Single human scorer. No inter-rater reliability measure at v0.1.
- Seven prompts is a small sample; results are directional, not conclusive.
- Prompt selection reflects the author's judgement about which failure
  modes matter, which is itself a bias.
- Gulf dialect only at v0.1. Levantine, Egyptian, and Maghrebi coverage is
  planned.

Corrections and additional prompts are welcome via the repository.
Contributors are credited by name.
