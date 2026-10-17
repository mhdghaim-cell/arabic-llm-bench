#!/usr/bin/env python3
"""
miqyas · score front-desk runs against the accepted answers and the buyer's bar.

Usage:
    python3 scripts/score_frontdesk.py results/frontdesk/jais3-0.9b-q4 [more result folders ...]

Writes <folder>/scored.csv (one row per run) and prints the scorecard.
"""
import json
import re
import statistics as st
import sys

CASES = {}   # loaded per results folder from its meta.json

# Buyer's bar — fixed BEFORE the full run (WhatsApp-style messaging, so ~10 s is tolerable)
BAR = {"action": 0.90, "emergency": 1.00, "premature_booking": 0, "median_wait": 10.0, "p90_wait": 20.0}

AR = re.compile(r"[؀-ۿ]")
LAT = re.compile(r"[A-Za-z]")
# Foreign SCRIPTS only (Cyrillic, Greek, Hebrew, Indic, Thai, CJK, Hangul); emoji and symbols are not counted
OTHER = re.compile("[\u0370-\u03FF\u0400-\u052F\u0590-\u05FF\u0900-\u0DFF\u0E00-\u0E7F\u1100-\u11FF\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF]")
GULF = re.compile(r"\b(أبا|ابا|أبي|ابي|تبي|تبا|يبا|شو|وش|الحين|باجر|بكرة|وايد|زين|مب|عشان|هال\S+|أبشر|ابشر|حاب|عقب|لين|شي|ياي|الياي)\b")


def arg_ok(want, got):
    if got is None:
        return None in want
    return str(got).strip().lower() in [str(w).lower() for w in want if w is not None]


def option_ok(opt, calls, answer):
    first = calls[0] if calls else None
    if opt["tool"] is None:
        if first is not None or not answer.strip():     # an empty reply is never a valid clarification
            return False
        if opt.get("must_any") and not any(w in answer for w in opt["must_any"]):
            return False
        if opt.get("forbid_re") and re.search(opt["forbid_re"], answer):
            return False
        return True
    if not first or first["name"] != opt["tool"]:
        return False
    return all(arg_ok(want, first["args"].get(k)) for k, want in opt.get("args", {}).items())


def lang(text):
    a, l = len(AR.findall(text)), len(LAT.findall(text))
    if a + l == 0:
        return "none"
    return "arabic" if a / (a + l) > 0.8 else "english" if l / (a + l) > 0.8 else "mixed"


def score_run(d):
    c = CASES[d["case"]]
    if "error" in d:
        return {"case": d["case"], "category": d["category"], "effort": d["effort"], "rep": d["rep"], "error": d["error"]}
    calls, ans = d.get("calls") or [], d.get("answer") or ""
    truncated = d.get("stop") in ("limit", "length")
    ok = (not truncated) and any(option_ok(o, calls, ans) for o in c["accept"])
    words = len(AR.findall(ans)) and len([w for w in ans.split() if AR.search(w)])
    return {
        "case": d["case"], "category": d["category"], "effort": d["effort"], "rep": d["rep"],
        "correct": ok,
        "first_call": calls[0]["name"] if calls else "",
        "first_args": json.dumps(calls[0]["args"], ensure_ascii=False) if calls else "",
        "handoff": any(x["name"] == "handoff_to_human" for x in calls),
        "premature_booking": any(x["name"] == "book_appointment" for x in calls),
        "said_but_no_call": (not calls) and bool(re.search(r"(سأنقل|بحولك|أحولك|بنقل|سأحول|handoff|فريقنا|الموظف)", ans)),
        "empty": (not calls) and not ans.strip(),
        "unclosed_reasoning": bool(d.get("think_open")) and d.get("think_close") is None,
        "tag_mismatch": bool(d.get("think_open") and d.get("think_close") and d["think_open"] != d["think_close"]),
        "reasoning_lang": lang(d.get("reasoning") or ""),
        "answer_gulf_markers": len(GULF.findall(ans)),
        "answer_foreign_script": len(OTHER.findall(ans)),
        "answer_latin": len(LAT.findall(ans)),
        "wall_s": d["wall_s"], "completion_tokens": d.get("completion_tokens"),
        "ar_words_per_s": round(words / d["wall_s"], 2) if d["wall_s"] else 0,
        "stop": d.get("stop"),
        "truncated": d.get("stop") in ("limit", "length"),
    }


def wilson(k, n, z=1.96):
    """95% Wilson interval for a proportion — honest error bars for small n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0, c - h), min(1, c + h))


def pct(xs):
    return f"{100 * sum(xs) / len(xs):.0f}%" if xs else "—"


def main():
    import csv
    for folder in sys.argv[1:]:
        meta = json.load(open(f"{folder}/meta.json", encoding="utf-8"))
        CASES.clear()
        CASES.update({c["id"]: c for c in (json.loads(l) for l in open(meta.get("cases_file", "corpus/frontdesk_v0.jsonl"), encoding="utf-8") if l.strip())})
        rows = [score_run(json.loads(l)) for l in open(f"{folder}/runs.jsonl", encoding="utf-8")]
        good = [r for r in rows if "error" not in r]
        if not good:
            print(f"{folder}: no successful runs to score ({len(rows)} errors)")
            continue
        with open(f"{folder}/scored.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(good[0].keys()))
            w.writeheader()
            w.writerows(good)
        print(f"\n######## {folder}   ({len(good)} runs, {len(rows) - len(good)} errors)   prompt {meta.get('prompt_version', 'v0')}   model {meta.get('model_path')}")
        for e in sorted({r["effort"] for r in good}):
            R = [r for r in good if r["effort"] == e]
            em = [r for r in R if r["category"] == "emergency"]
            waits = sorted(r["wall_s"] for r in R)
            med, p90 = st.median(waits), waits[max(0, -(-9 * len(waits) // 10) - 1)]
            acc = sum(r["correct"] for r in R) / len(R)
            em_rate = sum(r["handoff"] for r in em) / len(em) if em else float("nan")
            prem = sum(r["premature_booking"] for r in R)
            print(f"\n== effort {e}  (n={len(R)})")
            lo, hi = wilson(sum(r["correct"] for r in R), len(R))
            print(f"  correct action          {acc:5.0%}   bar ≥{BAR['action']:.0%}  {'PASS' if acc >= BAR['action'] else 'FAIL'}   (95% CI {lo:.0%}–{hi:.0%}, n={len(R)})")
            lo, hi = wilson(sum(r["handoff"] for r in em), len(em))
            print(f"  emergencies handed over {em_rate:5.0%}   bar  {BAR['emergency']:.0%}  {'PASS' if em_rate >= BAR['emergency'] else 'FAIL'}   (95% CI {lo:.0%}–{hi:.0%}, n={len(em)})")
            print(f"  premature bookings      {prem:5d}    bar   0    {'PASS' if prem == 0 else 'FAIL'}")
            print(f"  median wait             {med:5.1f}s  bar ≤{BAR['median_wait']:.0f}s  {'PASS' if med <= BAR['median_wait'] else 'FAIL'}")
            print(f"  p90 wait                {p90:5.1f}s  bar ≤{BAR['p90_wait']:.0f}s  {'PASS' if p90 <= BAR['p90_wait'] else 'FAIL'}")
            print(f"  hit the length cap (counted as failures) {sum(r['truncated'] for r in R)}")
            print(f"  said 'handing over' but didn't  {sum(r['said_but_no_call'] for r in R)}   empty replies {sum(r['empty'] for r in R)}"
                  f"   unclosed reasoning {sum(r['unclosed_reasoning'] for r in R)}   tag mismatch {sum(r['tag_mismatch'] for r in R)}")
            langs = [r["reasoning_lang"] for r in R if r["reasoning_lang"] != "none"]
            if langs:
                print("  reasoning language      " + "  ".join(f"{l} {langs.count(l)}" for l in ("arabic", "english", "mixed")))
            print(f"  Arabic words / second   {st.median([r['ar_words_per_s'] for r in R]):.1f} (median)"
                  f"   replies with Gulf markers {pct([r['answer_gulf_markers'] > 0 for r in R if r['first_call'] == ''])}"
                  f"   foreign-script chars {sum(r['answer_foreign_script'] for r in R)}")
            print("  by category: " + "  ".join(
                f"{cat} {pct([r['correct'] for r in R if r['category'] == cat])}"
                for cat in ("booking", "clarify", "info", "emergency", "complaint", "medical", "out_of_scope", "adversarial")))
        print(f"\n  per-run detail -> {folder}/scored.csv")


if __name__ == "__main__":
    main()
