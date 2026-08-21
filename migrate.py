#!/usr/bin/env python3
"""
migrate.py — restructure arabic-llm-bench to a single-source-of-truth layout.

Run once from the repo root:   python3 migrate.py
Safe to re-run: it is idempotent and never deletes raw data.
"""
import json, os, re, shutil, sys, glob
from datetime import datetime, timezone

ROOT = os.getcwd()
def p(*a): return os.path.join(ROOT, *a)
def w(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(obj, (dict, list)):
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        else:
            f.write(obj)
    print("  wrote", os.path.relpath(path, ROOT))

if not os.path.exists(p("data")) or not os.path.exists(p("index.html")):
    sys.exit("Run this from the repo root (the folder containing index.html and data/).")

print("\n=== 1. Canonical rubric ===")

RUBRIC = {
  "version": "0.1",
  "updated": "2026-08-20",
  "note": "المرجع الوحيد لطريقة التقييم. أي جدول نتائج في الموقع يقرأ من هنا.",
  "scale": {"min": 1, "max": 5},
  "dimensions": [
    {"id": "correctness", "ar": "الصحة", "en": "Correctness",
     "desc_ar": "هل الإجابة صحيحة واقعيًا، بلا اختلاق؟",
     "desc_en": "Is the answer factually correct, with nothing fabricated?"},
    {"id": "language_quality", "ar": "جودة اللغة", "en": "Language quality",
     "desc_ar": "هل اللغة سليمة نحويًا وطبيعية، لا مترجمة حرفيًا أو مكسّرة؟",
     "desc_en": "Is the Arabic grammatical and natural rather than translated or broken?"},
    {"id": "instruction_adherence", "ar": "الالتزام بالتعليمات", "en": "Instruction adherence",
     "desc_ar": "هل نُفِّذ المطلوب بالصيغة والطول المحددين؟",
     "desc_en": "Was the instruction followed in the specified format and length?"},
    {"id": "language_integrity", "ar": "ثبات اللغة", "en": "Language integrity",
     "desc_ar": "هل بقي النموذج بالعربية أم انزلق إلى لغة أخرى؟ يُقاس على كل موجّه، لا على موجّهات اللغة وحدها.",
     "desc_en": "Did the model stay in Arabic or drift into another language? Scored on every prompt, not only language-focused ones."}
  ],
  "exceptions": [
    {"prompt_id": "P3",
     "rule_ar": "يُقيَّم P3 بشكل ثنائي على أربعة قيود (العدد، الصيغة، الطول، غياب المقدمة) ويُنشر ككسر من ٤، منفصلًا عن مقياس ١–٥.",
     "rule_en": "P3 is scored binary across four constraints (count, format, length, no preamble) and reported as a fraction out of 4, kept separate from the 1–5 scale."},
    {"prompt_id": "P7",
     "rule_ar": "مقياس P7 معكوس: ٥ تعني الاعتراف بعدم إمكانية المعرفة، و١ تعني اختلاق رقم دقيق.",
     "rule_en": "P7 is inverted: 5 means acknowledging the question is unanswerable, 1 means fabricating a precise figure."}
  ],
  "known_limitations": [
    {"ar": "مقيّم بشري واحد. لا يوجد قياس لثبات التقييم بين مقيّمين في النسخة ٠٫١.",
     "en": "Single human scorer. No inter-rater reliability measure at v0.1."},
    {"ar": "سبعة موجّهات عينة صغيرة؛ النتائج إرشادية لا قاطعة.",
     "en": "Seven prompts is a small sample; results are directional, not conclusive."},
    {"ar": "اختيار الموجّهات يعكس حكم المؤلف حول أنماط الفشل المهمة، وهذا تحيّز في ذاته.",
     "en": "Prompt selection reflects the author's judgement about which failure modes matter, which is itself a bias."},
    {"ar": "اللهجة الخليجية فقط في النسخة ٠٫١. الشامية والمصرية والمغاربية مخطط لها.",
     "en": "Gulf dialect only at v0.1. Levantine, Egyptian and Maghrebi coverage is planned."}
  ]
}
w(p("data", "rubric.json"), RUBRIC)

print("\n=== 2. Consolidate prompts into data/prompts.json ===")

res = json.load(open(p("data", "results.json"), encoding="utf-8"))
prompts = res.get("prompts", [])
if not prompts:
    sys.exit("No prompts found in data/results.json — aborting rather than guessing.")

# P4 must use Arabic quotation marks; straight quotes break JSON encoding in the runner.
fixed_p4 = 0
for pr in prompts:
    if pr["id"] == "P4" and '"' in pr["prompt"]:
        pr["prompt"] = re.sub(r'"([^"]*)"', r'«\1»', pr["prompt"])
        fixed_p4 += 1
    pr["timing_prompt"] = (pr["id"] == "P5")

PROMPTS = {
  "version": "0.1",
  "updated": "2026-08-20",
  "frozen": True,
  "note_ar": "مجموعة الموجّهات مجمّدة طوال البرنامج. الإضافات تأخذ معرّفًا جديدًا؛ الموجّهات القائمة لا تتغيّر.",
  "note_en": "Frozen for the duration of the program. Additions receive a new ID; existing prompts do not change.",
  "timing_prompt": "P5",
  "timing_note_en": "All tokens-per-second figures in this project come from P5 and only P5. It produces a predictable 80-120 tokens. P2 varies widely in output length and would make timing noisy.",
  "prompts": prompts
}
w(p("data", "prompts.json"), PROMPTS)
if fixed_p4:
    print("  fixed P4 straight quotes -> «»")

print("\n=== 3. Generate prompts/*.txt from the canonical source ===")
os.makedirs(p("prompts"), exist_ok=True)
for pr in prompts:
    w(p("prompts", pr["id"].lower() + ".txt"), pr["prompt"].strip() + "\n")
w(p("prompts", "README.md"),
  "# prompts/\n\n**Generated — do not edit by hand.**\n\n"
  "These files are written by `scripts/gen-prompts.mjs` from `data/prompts.json`,\n"
  "which is the single source of truth. Editing here will be overwritten.\n\n"
  "`p5.txt` is the timing prompt. Every tokens-per-second figure in this project comes from it.\n")

print("\n=== 4. Changelog ===")
CHANGELOG = {
  "version": "0.1",
  "updated": "2026-08-20",
  "note_ar": "كل تصحيح يُسجَّل هنا مع تاريخه وسببه. سجل الأخطاء المصحّحة جزء من المنهجية، لا ملحق بها.",
  "entries": [
    {
      "date": "2026-08-20",
      "type": "correction",
      "severity": "published",
      "title_ar": "تصحيح رقم ٢٩٪ المنشور حول أثر إغلاق التطبيقات",
      "title_en": "Correction to the published 29% figure on background applications",
      "published_claim": "إغلاق التطبيقات المفتوحة رفع السرعة ٢٩٪ (١٠٫٠٠ ← ١٢٫٨٧ رمز/ثانية)",
      "published_on": ["X", "LinkedIn"],
      "published_date": "2026-08-18",
      "corrected_claim": "إغلاق التطبيقات يوفّر ٥–٢٢٪ من الإنتاجية على جهاز بـ٨ غيغابايت، بحسب النموذج",
      "reasons": [
        "تعميم من نموذج واحد: llama3.2:3b أظهر أكبر أثر (+٢٢٪)، بينما qwen3:1.7b أظهر ربعه تقريبًا (+٥٪).",
        "تجاهل تباين الجلسات: نفس النموذج في نفس الحالة النظيفة قاس ١٢٫٨٧ في يوم و١٢٫١٨ في اليوم التالي — فارق ٥٪ من رتبة أصغر أثر مرصود."
      ],
      "caught_by": "mhdghaim-cell",
      "evidence": "results/w1_timing.md"
    },
    {
      "date": "2026-08-19",
      "type": "retraction",
      "severity": "pre-publication",
      "title_ar": "سحب قراءة «كلما كبر النموذج ساءت العربية» قبل النشر",
      "title_en": "Retracted the reading that larger models produce worse Arabic, before publication",
      "retracted_claim": "النماذج الأكبر تنتج عربية أسوأ",
      "reason": "الانعكاس الظاهري سببه ضريبة الاستدلال وهي تستهلك سقف الرموز الثابت. عند تعطيل الاستدلال، تفوّق qwen3:8b (٥/٥) بوضوح على qwen3:1.7b (٢/٥). الحجم يساعد؛ الإعداد الافتراضي يخفي ذلك.",
      "caught_by": "mhdghaim-cell",
      "evidence": "results/w1_timing.md"
    },
    {
      "date": "2026-08-20",
      "type": "methodology",
      "severity": "internal",
      "title_ar": "توحيد دليل التقييم",
      "title_en": "Unified the scoring rubric",
      "reason": "كان الموقع ينشر دليل تقييم من أربعة أبعاد على مقياس ٠–١٠ يتضمن بُعد «السلامة» غير المقاس، بينما تلتزم وثيقة المنهجية بأربعة أبعاد على مقياس ١–٥ تتضمن «ثبات اللغة». المرجع الآن ملف واحد: data/rubric.json.",
      "evidence": "data/rubric.json"
    },
    {
      "date": "2026-08-20",
      "type": "methodology",
      "severity": "internal",
      "title_ar": "تصحيح علامات الاقتباس في P4",
      "title_en": "Fixed quotation marks in P4",
      "reason": "استخدام علامات الاقتباس المستقيمة داخل الموجّه كسر ترميز JSON في السكربت. النسخة المعتمدة تستخدم «» — على أي شخص يعيد التجربة استخدام نسخة المستودع.",
      "evidence": "prompts/p4.txt"
    }
  ]
}
w(p("data", "changelog.json"), CHANGELOG)

print("\n=== 5. Machines registry ===")
MACHINES = {
  "version": "0.1",
  "updated": "2026-08-20",
  "machines": [
    {
      "id": "machine-a", "label_ar": "الجهاز أ", "label_en": "Machine A",
      "role": "baseline",
      "model": "MacBook Air (Retina, 13-inch, 2020)",
      "cpu": "1.2 GHz Quad-Core Intel Core i7 (Ice Lake, 4C/8T)",
      "gpu": "Intel Iris Plus 1536 MB — unused, CPU-only inference",
      "ram_gb": 8, "ram_spec": "LPDDR4X 3733 MHz",
      "os": "macOS Sequoia 15.7.7",
      "runtime": "ollama 0.32.11", "backend": "cpu",
      "owned": True, "cost_per_day_usd": 0,
      "notes_en": "Fanless chassis; sustained clocks thermally limited. Real model budget ~4-4.5 GB after OS overhead. Ceiling 3B-4B at Q4."
    },
    {
      "id": "machine-b", "label_ar": "الجهاز ب", "label_en": "Machine B",
      "role": "capability",
      "model": "Mac mini M4 (rented)",
      "cpu": "Apple M4",
      "gpu": "Apple M4 integrated — Metal backend",
      "ram_gb": 16, "ram_spec": "unified",
      "os": "macOS 26.6.1",
      "runtime": "ollama 0.32.14", "backend": "metal",
      "owned": False, "provider": "Macly", "cost_per_day_usd": 14.99,
      "notes_en": "Rented per day. OS and runtime differ from Machine A — disclosed as uncontrolled variables in cross-machine comparisons."
    }
  ]
}
w(p("data", "machines.json"), MACHINES)

print("\n=== 6. Models registry ===")
MODELS = {
  "version": "0.1",
  "updated": "2026-08-20",
  "note_en": "Digests verified identical across machines, so weights are the same; runtime and OS are not.",
  "models": [
    {"id": "llama3.2:1b", "family": "llama3.2", "params_b": 1, "quantization": "Q4_K_M",
     "digest": "baf6a787fdff", "size_gb": 1.3, "source": "ollama", "reasoning_mode": False},
    {"id": "qwen3:1.7b", "family": "qwen3", "params_b": 1.7, "quantization": "Q4_K_M",
     "digest": "8f68893c685c", "size_gb": 1.4, "source": "ollama", "reasoning_mode": True},
    {"id": "llama3.2:3b", "family": "llama3.2", "params_b": 3, "quantization": "Q4_K_M",
     "digest": "a80c4f17acd5", "size_gb": 2.0, "source": "ollama", "reasoning_mode": False},
    {"id": "qwen3:8b", "family": "qwen3", "params_b": 8, "quantization": "Q4_K_M",
     "digest": "500a1f067a9f", "size_gb": 5.2, "source": "ollama", "reasoning_mode": True,
     "fits_machine_a": False}
  ]
}
w(p("data", "models.json"), MODELS)

print("\n=== 7. Migrate raw logs to runs/ ===")

MACHINE_OF = lambda fn: "machine-b" if fn.startswith("m4_") else "machine-a"
migrated = skipped = 0
raw_dir = p("results", "raw")
if os.path.isdir(raw_dir):
    for src in sorted(glob.glob(os.path.join(raw_dir, "*.txt"))):
        fn = os.path.basename(src)
        if fn.startswith("w1_corruption") or fn == "w1_air_session.txt":
            continue
        txt = open(src, encoding="utf-8", errors="replace").read()
        m = re.search(r'\{.*\}\s*$', txt, re.S)
        api, parsed_text = None, False
        if m:
            try:
                api = json.loads(m.group())
            except Exception:
                api = None
        if api is None:
            # Machine A logs use a pretty-printed format, not raw JSON.
            g = lambda pat: (re.search(pat, txt).group(1) if re.search(pat, txt) else None)
            ec = g(r'eval count:\s*(\d+)')
            er = g(r'eval rate:\s*([\d.]+)')
            pr = g(r'prompt rate:\s*([\d.]+)')
            td = g(r'total:\s*([\d.]+)s')
            if not (ec and er):
                skipped += 1
                continue
            out = txt.split("--- full output ---", 1)
            api = {
                "eval_count": int(ec),
                "_eval_rate": float(er),
                "_prompt_rate": float(pr) if pr else None,
                "_total_s": float(td) if td else None,
                "prompt_eval_count": None,
                "response": out[1].strip() if len(out) > 1 else "",
                "done_reason": None,
            }
            parsed_text = True

        machine = MACHINE_OF(fn)
        base = fn[3:] if fn.startswith("m4_") else fn
        is_quality = base.startswith("q_")
        if is_quality:
            base = base[2:]
        pm = re.match(r'(p\d)_', base)
        prompt_id = pm.group(1).upper() if pm else "P5"
        if pm:
            base = base[len(pm.group(0)):]
        # bench_nothink.sh did not mark its output filenames; these timestamps are
        # known think:false runs. Corroborated by token count (1.7b: 286 vs 300,
        # 8b: 121 vs 300) and by identical output across sessions.
        NOTHINK_TIMESTAMPS = {
            "20260819_053955", "20260819_074015", "20260819_074027",   # qwen3:1.7b
            "20260819_061927", "20260819_073730", "20260819_073803",   # qwen3:8b
            "20260819_073817",
        }
        nothink = ("_nothink" in base) or any(t in fn for t in NOTHINK_TIMESTAMPS)
        base = base.replace("_nothink", "").replace("_earlier", "")
        ts = re.search(r'(\d{8})_(\d{6})', base)
        stamp = f"{ts.group(1)}T{ts.group(2)}" if ts else "unknown"
        model_slug = re.sub(r'_?\d{8}_\d{6}\.txt$', '', base).strip('_')
        model_id = model_slug.replace("_", ":", 1).replace("_", ".")

        if parsed_text:
            metrics = {
                "eval_count": api["eval_count"],
                "eval_rate": api["_eval_rate"],
                "prompt_eval_count": None,
                "prompt_eval_rate": api["_prompt_rate"],
                "total_duration_s": api["_total_s"],
                "done_reason": None,
            }
        ed = api.get("eval_duration") or 1
        pd_ = api.get("prompt_eval_duration") or 1
        rec = {
            "id": f"{machine[-1]}-w1-{stamp}-{model_slug}-{prompt_id.lower()}" + ("-nothink" if nothink else ""),
            "machine": machine,
            "week": 1,
            "timestamp": stamp,
            "run_type": "quality" if is_quality else "timing",
            "model": {"id": model_id, "quantization": "Q4_K_M"},
            "prompt": {"id": prompt_id, "version": "0.1"},
            "config": {
                "num_predict": 500 if is_quality else 300,
                "temperature": 0.7, "seed": 42,
                "think": False if nothink else None
            },
            "metrics": metrics if parsed_text else {
                "eval_count": api.get("eval_count"),
                "eval_rate": round(api.get("eval_count", 0) / ed * 1e9, 2),
                "prompt_eval_count": api.get("prompt_eval_count"),
                "prompt_eval_rate": round((api.get("prompt_eval_count") or 0) / pd_ * 1e9, 2),
                "total_duration_s": round((api.get("total_duration") or 0) / 1e9, 2),
                "done_reason": api.get("done_reason")
            },
            "output": api.get("response", ""),
            "thinking": api.get("thinking"),
            "source_file": f"results/raw/{fn}"
        }
        # Protocol is three *consecutive* runs, median reported. This run came from
        # a separate session, so it corroborates the median rather than entering it.
        if "20260819_061927" in fn:
            rec["protocol"] = "corroborating"
            rec["protocol_note_en"] = ("Separate session from the three-run block. Produced byte-identical "
                                       "output and a rate within 0.7% of the reported median, so it supports "
                                       "reproducibility across sessions without being pooled into it.")
        else:
            rec["protocol"] = "three-run-median"
        dest = p("runs", machine, "w1", f"{stamp}_{model_slug}_{prompt_id.lower()}{'_nothink' if nothink else ''}.json")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2); f.write("\n")
        migrated += 1
print(f"  migrated {migrated} runs, skipped {skipped} non-JSON files")
print("  results/raw/ left untouched as the immutable original record")

print("\n=== 8. Run index ===")
runs = []
for f in sorted(glob.glob(p("runs", "*", "*", "*.json"))):
    r = json.load(open(f, encoding="utf-8"))
    runs.append({k: r[k] for k in ("id","machine","week","timestamp","run_type","model","prompt","config","metrics")} | {"path": os.path.relpath(f, ROOT)})
w(p("data", "runs.json"), {"version":"0.1","updated":"2026-08-20","count":len(runs),"runs":runs})

print("\n=== 9. Clean results.json — it now references, not duplicates ===")
res_new = {
  "version": "0.1",
  "updated": "2026-08-20",
  "note_ar": "هذا الملف يشير إلى المصادر ولا يكرّرها.",
  "sources": {
    "rubric": "data/rubric.json",
    "prompts": "data/prompts.json",
    "machines": "data/machines.json",
    "models": "data/models.json",
    "runs": "data/runs.json",
    "scores": "data/scores.json",
    "changelog": "data/changelog.json"
  },
  "leaderboard": res.get("leaderboard", []),
  "contributors": res.get("contributors", [])
}
w(p("data", "results.json"), res_new)

print("\n=== 10. Scores — Week 1, Machine B ===")
SCORES = {
  "version": "0.1",
  "updated": "2026-08-20",
  "note_en": "Scores are stored separately from runs so a run can be rescored, and so multiple scorers can score the same run without touching the measurement.",
  "scores": [
    {"model": "qwen3:8b", "config": "think:false", "machine": "machine-b", "prompt": "P1",
     "scorer": "mhdghaim-cell", "value": 1, "max": 5,
     "notes_en": "Federation date 18 Dec (correct: 2 Dec). Listed Oman as an emirate. Invented الظفير. Omitted Dubai. Then contradicted itself with a second list. Said Saudi Arabia was previously الإمارة الحمراء — fabricated."},
    {"model": "qwen3:8b", "config": "think:false", "machine": "machine-b", "prompt": "P2",
     "scorer": "mhdghaim-cell", "value": 5, "max": 5,
     "notes_en": "11,550 litres, all steps correct, avoided the متوسط الأولين trap."},
    {"model": "qwen3:8b", "config": "think:false", "machine": "machine-b", "prompt": "P3",
     "scorer": "mhdghaim-cell", "value": 4, "max": 4,
     "notes_en": "All four constraints passed, including no preamble."},
    {"model": "qwen3:8b", "config": "think:false", "machine": "machine-b", "prompt": "P4",
     "scorer": "mhdghaim-cell", "value": 3, "max": 5,
     "notes_en": "All three dialect markers understood. Timing wrong — read عقب الشهر as one month from today rather than after the end of this month."},
    {"model": "qwen3:8b", "config": "think:false", "machine": "machine-b", "prompt": "P5",
     "scorer": "mhdghaim-cell", "value": 5, "max": 5,
     "notes_en": "Four sentences as instructed, correct formal register, سيادة البيانات spelled correctly, no contamination. Best Arabic output recorded in Week 1."},
    {"model": "qwen3:8b", "config": "think:false", "machine": "machine-b", "prompt": "P6",
     "scorer": "mhdghaim-cell", "value": 4, "max": 5,
     "notes_en": "Working function with Arabic identifiers (متوسط_حسابي, مجموع_العناصر) — valid Python 3. Lost a point for prose outside the code block, which the prompt forbade."},
    {"model": "qwen3:8b", "config": "think:false", "machine": "machine-b", "prompt": "P7",
     "scorer": "mhdghaim-cell", "value": 2, "max": 5,
     "notes_en": "Gave 4.5 million without acknowledging the question is unanswerable (2022 census ~7 million). Cited المركز الوطني للإحصاء والمسوحات, which does not exist."},

    {"model": "llama3.2:3b", "config": "default", "machine": "machine-b", "prompt": "P1",
     "scorer": "mhdghaim-cell", "value": 2, "max": 5,
     "notes_en": "Federation date correct (2 Dec 1971). Answered seven for the founding count — the expected failure. Circular non-answer on the Saudi question rather than a fabrication."},
    {"model": "llama3.2:3b", "config": "default", "machine": "machine-b", "prompt": "P2",
     "scorer": "mhdghaim-cell", "value": 5, "max": 5,
     "notes_en": "11,550 litres, all steps correct. Register slip: used اكتشف where نحسب would be natural."},
    {"model": "llama3.2:3b", "config": "default", "machine": "machine-b", "prompt": "P3",
     "scorer": "mhdghaim-cell", "value": 3, "max": 4,
     "notes_en": "Added numbering that was not requested; third item is a noun phrase rather than a reason."},
    {"model": "llama3.2:3b", "config": "default", "machine": "machine-b", "prompt": "P4",
     "scorer": "mhdghaim-cell", "value": 1, "max": 5,
     "notes_en": "Did not understand الحين, عقب or اللي عليّ. No mention of money or debt."},
    {"model": "llama3.2:3b", "config": "default", "machine": "machine-b", "prompt": "P5",
     "scorer": "mhdghaim-cell", "value": 4, "max": 5,
     "notes_en": "Coherent formal letter, sovereignty argument present. Unrequested preamble هذه رسالة رسمية:."},
    {"model": "llama3.2:3b", "config": "default", "machine": "machine-b", "prompt": "P6",
     "scorer": "mhdghaim-cell", "value": 1, "max": 5,
     "notes_en": "Produced a script rather than a function, ignoring the instruction. English identifiers. Contamination: функциة (Russian stem + Arabic ة) four times."},
    {"model": "llama3.2:3b", "config": "default", "machine": "machine-b", "prompt": "P7",
     "scorer": "mhdghaim-cell", "value": 4, "max": 5,
     "notes_en": "Explicitly stated it could not estimate the figure precisely — the correct behaviour."}
  ]
}
w(p("data", "scores.json"), SCORES)

print("\n=== 11. Findings ===")
FINDINGS = {
  "version": "0.1", "updated": "2026-08-20",
  "findings": [
    {"slug": "apple-silicon-speedup", "week": 1,
     "title_ar": "تسريع Apple Silicon: ٣٫٥–٣٫٧×", "title_en": "Apple Silicon speedup: 3.5-3.7x",
     "summary_ar": "التسريع في التوليد ثابت عند ٣٫٥–٣٫٧× عبر ثلاثة نماذج. تسريع معالجة الموجّه أكبر وأكثر تفاوتًا (٣٫٥–٩٫٦×) لأنه محكوم بالحوسبة لا بعرض النطاق."},
    {"slug": "reasoning-tax", "week": 1, "starred": True,
     "title_ar": "ضريبة الاستدلال على العربية", "title_en": "The reasoning tax on Arabic",
     "summary_ar": "نموذجا qwen3 أنفقا كامل سقف الرموز في الاستدلال بالإنجليزية حول كيفية كتابة رسالة عربية. تعطيل الاستدلال لم يغيّر السرعة إطلاقًا، لكنه غيّر مكان هبوط الرموز: من ١/٥ إلى ٥/٥."},
    {"slug": "regional-knowledge-gap", "week": 1, "starred": True,
     "title_ar": "الكفاءة اللغوية والمعرفة الإقليمية محوران منفصلان", "title_en": "Language capability and regional knowledge are separate axes",
     "summary_ar": "qwen3:8b سجّل ٥/٥ في الاستدلال و٤/٤ في الالتزام بالتعليمات و٥/٥ في الكتابة الرسمية — و١/٥ في المعرفة الإقليمية. أدرج عُمان إمارةً، واخترع إمارة اسمها الظفير، وأسقط دبي."},
    {"slug": "confident-fabrication", "week": 1,
     "title_ar": "النموذج الأصغر كان أكثر صدقًا", "title_en": "The smaller model was more honest",
     "summary_ar": "على الموجّهين اللذين يختبران الأمانة المعرفية، تفوّق llama3.2:3b على qwen3:8b. النموذج الأكبر يفشل بثقة أعلى، ويولّد أكاذيب مفصّلة ومقنعة حيث يعطي الأصغر إجابة رقيقة أو يعترف بالجهل."},
    {"slug": "script-contamination", "week": 1,
     "title_ar": "تلوّث الكتابة: ست لغات مصدر", "title_en": "Script contamination: six source languages",
     "summary_ar": "تايلاندية، سيريلية، فيتنامية، ألمانية، إنجليزية، روسية — على جهازين ونسختَي تشغيل ونظامَي تشغيل. نمطان متمايزان: سلاسل بلا معنى، وجذور كلمات أجنبية تحمل تصريفًا عربيًا."},
    {"slug": "background-apps", "week": 1,
     "title_ar": "التطبيقات المفتوحة تكلّف ٥–٢٢٪ من الإنتاجية", "title_en": "Background applications cost 5-22% of throughput",
     "summary_ar": "على جهاز بـ٨ غيغابايت. يتضمن هذا تصحيحًا لرقم ٢٩٪ المنشور سابقًا — انظر سجل التغييرات.",
     "has_correction": True},
    {"slug": "seed-insufficient", "week": 1,
     "title_ar": "البذرة الثابتة لا تضمن إعادة الإنتاج", "title_en": "A fixed seed does not guarantee reproducibility",
     "summary_ar": "حالة ذاكرة KV المؤقتة في Ollama تؤثر على التوليد بمعزل عن البذرة. رُصد على الجهازين."}
  ]
}
w(p("data", "findings.json"), FINDINGS)

print("\n=== 12. Standard files ===")

w(p(".gitignore"),
"node_modules/\n.DS_Store\n.venv/\n__pycache__/\n*.pyc\n.env\n.env.*\n/tmp/\n*.log\n.vscode/\n.idea/\n")

w(p("CITATION.cff"),
"""cff-version: 1.2.0
title: "مقياس (miqyas) — Arabic LLM Benchmark"
message: "If you use these measurements, please cite them."
type: dataset
authors:
  - alias: mhdghaim-cell
    website: "https://github.com/mhdghaim-cell"
repository-code: "https://github.com/mhdghaim-cell/arabic-llm-bench"
abstract: >-
  Open measurements of how locally-run language models handle Arabic:
  tokenizer efficiency, quantization effects, dialect comprehension,
  and regional knowledge. All raw outputs published.
keywords:
  - arabic
  - nlp
  - benchmark
  - local-inference
  - llm
license: MIT
version: "0.1"
date-released: "2026-08-20"
""")

w(p("CONTRIBUTING.md"),
"""# المساهمة · Contributing

شكرًا لاهتمامك. هذا المعيار مفتوح لأن معيارًا يضعه شخص واحد يعكس تحيّزات شخص واحد.

---

## ما نحتاجه أكثر

- **موجّهات باللهجات** — المغاربية والشامية والمصرية هي الأقل تمثيلًا حاليًا.
- **تشغيل النماذج على أجهزة أخرى** — أرقام مختلفة عن أرقامنا معلومة مفيدة، لا خطأ.
- **تصحيحات** — لغوية أو منهجية أو حسابية.

كل مساهم يُذكر بالاسم في المستودع، وفي كل نتيجة تُنشر باستخدام مساهمته.

---

## إضافة موجّه

الموجّهات تُخزّن في `data/prompts.json`. الملفات في `prompts/` مولّدة منه — لا تحرّرها مباشرة.

الموجّه الجيد يستهدف نمط فشل محدد. الموجّه الذي تنجح فيه كل النماذج لا يحمل معلومة.

```json
{
  "id": "P8",
  "category": "فئة",
  "category_en": "category",
  "prompt": "نص الموجّه",
  "target": "ما الذي يختبره تحديدًا",
  "reference": "الإجابة الصحيحة أو معايير الصحة",
  "expected_failure": "نمط الفشل المتوقع",
  "dialect": "gulf | levantine | egyptian | maghrebi | msa",
  "scoring": "شرح التقييم من ١ إلى ٥"
}
```

**لا تُعدّل الموجّهات القائمة.** المجموعة مجمّدة حتى تبقى النتائج قابلة للمقارنة عبر الأسابيع. الإضافات تأخذ معرّفًا جديدًا.

⚠️ استخدم علامات الاقتباس العربية «» داخل نص الموجّه. العلامات المستقيمة تكسر ترميز JSON في السكربت.

---

## إرسال نتيجة تشغيل

1. شغّل `scripts/run.sh` على جهازك.
2. أرفق ملف التشغيل الناتج من `runs/` كاملًا — لا الأرقام وحدها.
3. اذكر: الجهاز، نظام التشغيل، نسخة Ollama، ومعرّف النموذج (digest).

المخرجات الخام مطلوبة. أي رقم يُنشر يجب أن يكون قابلًا للتتبّع إلى التوليد الذي أنتجه.

---

## التقييم

دليل التقييم كاملًا في `data/rubric.json`. أربعة أبعاد على مقياس ١–٥، مع استثناءات موثّقة لـ P3 و P7.

إن اختلف تقييمك عن تقييمنا لنفس المخرج، هذا مفيد — التقييمات تُخزّن منفصلة عن التشغيلات في `data/scores.json` تحديدًا ليتمكن أكثر من شخص من تقييم نفس التوليد.

---

## Corrections

Found an error? Open an issue. Every correction is logged in `data/changelog.json`
with the date, the reason, and attribution to whoever caught it.

A visible history of being corrected is stronger evidence of honesty than any
claim of rigour.
""")

print("\n=== 13. Validation script ===")
w(p("scripts", "validate.mjs"),
"""#!/usr/bin/env node
// Validates the data spine. Run: node scripts/validate.mjs
import { readFileSync, existsSync } from 'fs';

let errors = 0, warnings = 0;
const fail = m => { console.error('  ERROR  ' + m); errors++; };
const warn = m => { console.warn('  WARN   ' + m); warnings++; };
const load = f => {
  if (!existsSync(f)) { fail(`missing file: ${f}`); return null; }
  try { return JSON.parse(readFileSync(f, 'utf8')); }
  catch (e) { fail(`invalid JSON in ${f}: ${e.message}`); return null; }
};

console.log('\\nValidating data spine...\\n');

const rubric   = load('data/rubric.json');
const prompts  = load('data/prompts.json');
const machines = load('data/machines.json');
const models   = load('data/models.json');
const runs     = load('data/runs.json');
const scores   = load('data/scores.json');
const findings = load('data/findings.json');
const tokenizers = load('data/tokenizers.json');

// referential integrity
const promptIds  = new Set((prompts?.prompts  ?? []).map(p => p.id));
const machineIds = new Set((machines?.machines ?? []).map(m => m.id));
const modelIds   = new Set((models?.models    ?? []).map(m => m.id));

for (const r of runs?.runs ?? []) {
  if (!machineIds.has(r.machine)) fail(`run ${r.id}: unknown machine "${r.machine}"`);
  if (!promptIds.has(r.prompt?.id)) fail(`run ${r.id}: unknown prompt "${r.prompt?.id}"`);
  if (!modelIds.has(r.model?.id)) warn(`run ${r.id}: model "${r.model?.id}" not in registry`);
  if (r.metrics?.eval_rate == null) fail(`run ${r.id}: missing eval_rate`);
}

for (const s of scores?.scores ?? []) {
  if (!promptIds.has(s.prompt)) fail(`score for ${s.model}/${s.prompt}: unknown prompt`);
  if (!machineIds.has(s.machine)) fail(`score for ${s.model}/${s.prompt}: unknown machine`);
  const max = s.max ?? rubric?.scale?.max;
  if (s.value > max) fail(`score for ${s.model}/${s.prompt}: ${s.value} exceeds max ${max}`);
}

// rule 5: never invent a number
const nulls = (tokenizers?.tokenizers ?? []).filter(t => t.ratio == null).length;
if (nulls) console.log(`  note   ${nulls} tokenizer ratios are null (unmeasured) — correct per Rule 5`);

// timing prompt discipline
const timing = (runs?.runs ?? []).filter(r => r.run_type === 'timing');
const badTiming = timing.filter(r => r.prompt?.id !== 'P5');
if (badTiming.length) fail(`${badTiming.length} timing runs do not use P5`);

console.log(`\\n${errors} errors, ${warnings} warnings\\n`);
process.exit(errors ? 1 : 0);
""")

print("\n=== 14. Prompt generator ===")
w(p("scripts", "gen-prompts.mjs"),
"""#!/usr/bin/env node
// Regenerates prompts/*.txt from data/prompts.json. Run: node scripts/gen-prompts.mjs
import { readFileSync, writeFileSync } from 'fs';
const d = JSON.parse(readFileSync('data/prompts.json', 'utf8'));
for (const p of d.prompts) {
  const f = `prompts/${p.id.toLowerCase()}.txt`;
  writeFileSync(f, p.prompt.trim() + '\\n', 'utf8');
  console.log('wrote', f);
}
""")

print("\n=== 15. Tag suggestion ===")
print("  git tag -a w1 -m 'Week 1 complete: two machines, 39 runs, nine findings'")

print("\nDone.\n")
print("Next:")
print("  node scripts/validate.mjs")
print("  git add -A && git commit -m 'Restructure: single source of truth for data spine'")
