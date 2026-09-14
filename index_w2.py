#!/usr/bin/env python3
"""
index_w2.py — fold Week 2 into the data spine.

Run once from the repo root:  python3 index_w2.py
Idempotent: re-running replaces Week 2 entries rather than duplicating them.

Reads:
  results/w2/*_isolated.md    speed benchmarks (llama-bench)
  results/raw/w2_*.json       quality runs (ollama API)
Writes:
  runs/machine-a/w2/*.json    self-describing run records
  data/runs.json              index (week 1 preserved, week 2 added)
  data/scores.json            week 2 quality scores appended
  data/models.json            four quantization levels registered
  data/benchmarks.json        speed measurements, new file
"""
import json, os, re, glob, sys

ROOT = os.getcwd()
def p(*a): return os.path.join(ROOT, *a)
def w(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write("\n")
    print("  wrote", os.path.relpath(path, ROOT))

if not os.path.exists(p("data", "runs.json")):
    sys.exit("Run from the repo root (needs data/runs.json).")

LEVELS = {
    "l1b-q4":  {"quant": "Q4_K_M",  "size_mib": 763,  "file": "Llama-3.2-1B-Instruct-Q4_K_M.gguf"},
    "l1b-q5":  {"quant": "Q5_K_M",  "size_mib": 862,  "file": "Llama-3.2-1B-Instruct-Q5_K_M.gguf"},
    "l1b-q8":  {"quant": "Q8_0",    "size_mib": 1249, "file": "Llama-3.2-1B-Instruct-Q8_0.gguf"},
    "l1b-f16": {"quant": "F16",     "size_mib": 2355, "file": "Llama-3.2-1B-Instruct-f16.gguf"},
}

print("\n=== 1. Register the four quantization levels ===")
models = json.load(open(p("data", "models.json"), encoding="utf-8"))
existing = {m["id"] for m in models["models"]}
for tag, meta in LEVELS.items():
    if tag in existing: continue
    models["models"].append({
        "id": tag,
        "family": "llama3.2",
        "params_b": 1,
        "quantization": meta["quant"],
        "size_gb": round(meta["size_mib"] / 1024, 2),
        "source": "bartowski/Llama-3.2-1B-Instruct-GGUF",
        "gguf_file": meta["file"],
        "reasoning_mode": False,
        "note_en": "Registered locally via Modelfile for the Week 2 quantization ladder. Weights not committed."
    })
models["updated"] = "2026-09-01"
w(p("data", "models.json"), models)

print("\n=== 2. Speed benchmarks -> data/benchmarks.json ===")
bench = []
for f in sorted(glob.glob(p("results", "w2", "*_isolated.md"))):
    tag_key = os.path.basename(f).split("_")[0]          # q4 / q5 / q8 / f16
    tag = "l1b-" + tag_key
    txt = open(f, encoding="utf-8").read()
    rows = {}
    for m in re.finditer(r'\|\s*([\d.]+)\s*±\s*([\d.]+)\s*\|', txt):
        pass
    for line in txt.splitlines():
        mt = re.search(r'\|\s*(pp512|tg128)\s*\|\s*([\d.]+)\s*±\s*([\d.]+)\s*\|', line)
        if mt:
            rows[mt.group(1)] = {"mean": float(mt.group(2)), "stdev": float(mt.group(3))}
    if not rows: continue
    bench.append({
        "id": f"a-w2-{tag_key}-isolated",
        "machine": "machine-a",
        "week": 2,
        "model": {"id": tag, "quantization": LEVELS[tag]["quant"], "size_mib": LEVELS[tag]["size_mib"]},
        "tool": "llama-bench",
        "build": "c1d0e7a00 (10621)",
        "config": {"backend": "BLAS", "threads": 4, "n_prompt": 512, "n_gen": 128, "repetitions": 5},
        "protocol": "isolated-session",
        "protocol_note_en": ("Measured alone on a cool machine with at least 15 minutes idle before the run "
                             "and a discarded warmup pass. Sequential measurement on this chassis is invalid "
                             "— see the thermal finding."),
        "metrics": {"pp512_tok_s": rows.get("pp512"), "tg128_tok_s": rows.get("tg128")},
        "source_file": os.path.relpath(f, ROOT)
    })

# the invalidated sequential runs, kept as evidence
thermal = {
    "id": "a-w2-thermal-confound",
    "machine": "machine-a",
    "week": 2,
    "model": {"id": "l1b-q4", "quantization": "Q4_K_M"},
    "finding": "thermal-confound",
    "note_en": ("The same file measured five times under different thermal and cache conditions. "
                "Spread of 2.2x from thermal state alone, comparable in magnitude to the quantization "
                "effect being measured."),
    "measurements": [
        {"condition_en": "isolated, cool machine", "condition_ar": "معزولًا على جهاز بارد",
         "tg128": 36.36, "stdev": 1.67, "valid": True},
        {"condition_en": "first in sequence, after warmup", "condition_ar": "أولًا في التسلسل بعد الإحماء",
         "tg128": 30.84, "stdev": 0.74, "valid": False},
        {"condition_en": "second session, warm file cache", "condition_ar": "جلسة ثانية، ذاكرة ملفات دافئة",
         "tg128": 27.53, "stdev": 2.06, "valid": False},
        {"condition_en": "first run of session, cold cache", "condition_ar": "أول تشغيل، ذاكرة باردة",
         "tg128": 18.33, "stdev": 2.66, "valid": False},
        {"condition_en": "fourth in sequence, hot chassis", "condition_ar": "رابعًا في التسلسل، جهاز ساخن",
         "tg128": 16.43, "stdev": 12.32, "valid": False}
    ],
    "discarded": [
        {"measurement": "Q8_0 pp512 sequential", "value": 28.34, "stdev": 32.72,
         "reason_en": "Standard deviation exceeds the mean. Measurement invalid."}
    ],
    "evidence_files": ["results/w2/ladder.md", "results/w2/ladder_reversed.md"]
}
w(p("data", "benchmarks.json"),
  {"version": "0.1", "updated": "2026-09-01", "count": len(bench),
   "note_en": "Speed benchmarks. Quality runs live in data/runs.json; these are llama-bench throughput measurements.",
   "benchmarks": bench, "findings": [thermal]})

print("\n=== 3. Quality runs -> runs/machine-a/w2/ ===")
migrated = 0
for src in sorted(glob.glob(p("results", "raw", "w2_*.json"))):
    fn = os.path.basename(src)
    m = re.match(r'w2_(p\d)_(l1b-\w+)_(\d{8})_(\d{6})\.json', fn)
    if not m:
        print("  skip (unparsed name):", fn); continue
    prompt_id, tag, d, t = m.group(1).upper(), m.group(2), m.group(3), m.group(4)
    try:
        api = json.load(open(src, encoding="utf-8"))
    except Exception as e:
        print("  skip (bad json):", fn, e); continue

    ed = api.get("eval_duration") or 1
    pd_ = api.get("prompt_eval_duration") or 1
    rec = {
        "id": f"a-w2-{d}T{t}-{tag}-{prompt_id.lower()}",
        "machine": "machine-a",
        "week": 2,
        "timestamp": f"{d}T{t}",
        "run_type": "quality",
        "model": {"id": tag, "quantization": LEVELS.get(tag, {}).get("quant")},
        "prompt": {"id": prompt_id, "version": "0.1"},
        "config": {"num_predict": 500, "temperature": 0.7, "seed": 42, "think": None},
        "environment": {"os": "macOS Sequoia 15.7.7", "runtime": "ollama 0.32.11", "backend": "cpu"},
        "protocol": "isolated-session",
        "metrics": {
            "eval_count": api.get("eval_count"),
            "eval_rate": round((api.get("eval_count") or 0) / ed * 1e9, 2),
            "prompt_eval_count": api.get("prompt_eval_count"),
            "prompt_eval_rate": round((api.get("prompt_eval_count") or 0) / pd_ * 1e9, 2),
            "total_duration_s": round((api.get("total_duration") or 0) / 1e9, 2),
            "done_reason": api.get("done_reason")
        },
        "output": api.get("response", ""),
        "thinking": api.get("thinking"),
        "source_file": os.path.relpath(src, ROOT)
    }
    w(p("runs", "machine-a", "w2", f"{d}T{t}_{tag}_{prompt_id.lower()}.json"), rec)
    migrated += 1
print(f"  {migrated} quality runs written")

print("\n=== 4. Rebuild data/runs.json ===")
runs = []
for f in sorted(glob.glob(p("runs", "*", "*", "*.json"))):
    r = json.load(open(f, encoding="utf-8"))
    keep = {k: r[k] for k in ("id","machine","week","timestamp","run_type","model","prompt","config","metrics") if k in r}
    keep["path"] = os.path.relpath(f, ROOT)
    if "protocol" in r: keep["protocol"] = r["protocol"]
    runs.append(keep)
by_week = {}
for r in runs: by_week[r["week"]] = by_week.get(r["week"], 0) + 1
w(p("data", "runs.json"),
  {"version": "0.2", "updated": "2026-09-01", "count": len(runs),
   "by_week": by_week, "runs": runs})

print("\n=== 5. Week 2 scores ===")
scores = json.load(open(p("data", "scores.json"), encoding="utf-8"))
scores["scores"] = [s for s in scores["scores"] if s.get("week") != 2]

W2 = [
 ("l1b-q4","P1",1,5,"Fabricated throughout: 16 November 1971, a regional conference in دبئ, five states, then invented Gamal Abdel Nasser declaring UAE independence from Egypt. Contamination: التأسيسของ (Thai)."),
 ("l1b-q4","P2",1,5,"Read 'double the first minus 100' as 400/2=200. Said well 3 equals well 1. Answered 600; correct is 11,550. Contamination: للคำputation, nghĩa x2."),
 ("l1b-q4","P3",3,4,"Three reasons, own lines, no preamble. Lines exceed ten words."),
 ("l1b-q4","P4",1,5,"Incoherent. Read الشهر as January-to-December. Invented الم ukif. Contamination: sẽ, الميلadera."),
 ("l1b-q4","P5",1,5,"Seven paragraphs against a four-sentence instruction. Repetitive, argument muddled. Contamination: ประสิทธิภาพ x2 (Thai, full word for efficiency)."),

 ("l1b-q5","P1",1,5,"Said 1972. Invented four near-identical 'reasons'. Answered the Saudi question with سيف الله is a king in Saudi Arabia, repeated three times. Contamination: في Arabia."),
 ("l1b-q5","P2",1,5,"Read 'double minus 100' as just 'minus 100'. Answered 8,400; correct is 11,550. Switched to English mid-answer. Contamination: maintenant (French)."),
 ("l1b-q5","P3",4,4,"All four constraints passed. The cleanest instruction-following result of the week."),
 ("l1b-q5","P4",1,5,"Incoherent. Contamination: يسد्द — Devanagari द (U+0926) substituted for Arabic د."),
 ("l1b-q5","P5",2,5,"Letter-shaped with a header, but opens with أوبرا and refers to الصحة البيولوجية للذكاء الاصطناعي. Contamination: raison (French)."),

 ("l1b-q8","P1",2,5,"Answered SIX emirates at founding — the discriminator P1 was built around, and one qwen3:8b failed on Machine B. Year wrong (1961), Saudi answer circular. Clean format, 78 tokens, stopped naturally."),
 ("l1b-q8","P2",1,5,"Worst arithmetic of the four. Invented 4,000/3 and a '10% less' constraint absent from the prompt. Answered 40,118. Switched entirely to English."),
 ("l1b-q8","P3",3,4,"Three lines, no preamble. البرامج الستار is meaningless and repeats."),
 ("l1b-q8","P4",1,5,"Invented a religious framing (الصحابي) not present in the prompt. Contamination: 句话 (Chinese)."),
 ("l1b-q8","P5",2,5,"Reads as a report that approval was granted rather than a request for it. Task misread, but clean Arabic and no contamination."),

 ("l1b-f16","P1",1,5,"Listed Kuwait, Bahrain, Qatar, Saudi Arabia and Oman as UAE emirates. Item 5 is a nested list inside the list. Sentence cut off mid-quotation. Contamination: 2 tháng (Vietnamese)."),
 ("l1b-f16","P2",1,5,"Invented 4,000 litres. 'double 1,000 = 1,000'. Answered 7,000. Contamination: المترipple."),
 ("l1b-f16","P3",1,4,"Produced one reason out of three, with a preamble. Worse than every quantized level."),
 ("l1b-f16","P4",1,5,"Incoherent. Contamination: gì (Vietnamese) fused into Arabic."),
 ("l1b-f16","P5",1,5,"Most contaminated output of the week: ประสิทธิภาพ x3, ประสิทธividad (Thai + Spanish), việc, tôi (Vietnamese)."),
]
for tag, pid, val, mx, note in W2:
    scores["scores"].append({
        "model": tag, "config": "default", "machine": "machine-a", "week": 2,
        "prompt": pid, "scorer": "mhdghaim-cell", "scored_at": "2026-09-01",
        "value": val, "max": mx, "notes_en": note
    })
scores["updated"] = "2026-09-01"
scores["version"] = "0.2"
w(p("data", "scores.json"), scores)

print("\n=== 6. Week 2 findings ===")
fnd = json.load(open(p("data", "findings.json"), encoding="utf-8"))
fnd["findings"] = [f for f in fnd["findings"] if f.get("week") != 2]
fnd["findings"] += [
 {"slug": "thermal-confound", "week": 2, "starred": True,
  "title_ar": "الحرارة تفسد القياس على الأجهزة بلا مروحة",
  "title_en": "Thermal state invalidates benchmarks on fanless hardware",
  "summary_ar": "نفس الملف، نفس الأمر، فرق ٢٫٢× بين قياس معزول على جهاز بارد وقياس رابع في تسلسل. الخطأ الحراري من رتبة أثر التكميم نفسه."},
 {"slug": "quantization-ladder", "week": 2,
  "title_ar": "سلّم التكميم: Q4 هاوية لا درجة",
  "title_en": "The quantization ladder: Q4 is a cliff, not a step",
  "summary_ar": "التكميم يضاعف السرعة فورًا (٢٫٢× على الأقل). Q5 وQ8 متطابقان عمليًا رغم فارق الحجم ٤٠٪. Q4 أسرع بـ٥٨٪ من كليهما."},
 {"slug": "quantization-arabic-inconclusive", "week": 2,
  "title_ar": "هل يضرّ التكميم العربية؟ لم أستطع القياس",
  "title_en": "Does quantization damage Arabic? Not measurable at 1B",
  "summary_ar": "خمسة موجّهات على أربعة مستويات: النتائج ٥ إلى ٩ من ٢٤. الكل فشل، وF16 غير المكمّم كان الأسوأ. الفشل فشل سعة لا فشل ضغط. يُعاد الاختبار في الأسبوع الثامن.",
  "result_type": "inconclusive"}
]
fnd["updated"] = "2026-09-01"
w(p("data", "findings.json"), fnd)

print("\nDone.\n")
print("Next:")
print("  node scripts/validate.mjs")
print("  git add -A && git commit -m 'Index Week 2 into the data spine' && git push")
