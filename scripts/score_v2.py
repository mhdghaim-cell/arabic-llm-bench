#!/usr/bin/env python3
"""
miqyas · front-desk v2 scorer.

An episode run SUCCEEDS only if
  (a) the clinic's final state matches one accepted end state exactly
      (bookings added, appointments cancelled, handoff required/forbidden + reason + timing,
       required words in the replies, forbidden patterns absent), and
  (b) no critical failure happened:
      invented_time      a reply names a time no tool returned and the patient never said
      false_confirmation a reply says "booked"/"cancelled" when the clinic shows no such change
      cap / loop         the model never finished (length cap or too many tool rounds)
      silent_turn        the patient got no reply to a message
invented_time and false_confirmation are regex screens: every flag is listed for human review,
and both the automatic and the human-reviewed numbers are reported.

Usage:
  python3 scripts/score_v2.py results/frontdesk_v2/<label> [more folders]       # scorecards
  python3 scripts/score_v2.py --compare results/frontdesk_v2/A:tool:high results/frontdesk_v2/B:tool:high
"""
import csv
import json
import random
import re
import statistics as st
import sys
import unicodedata

BAR = {"success": 0.90, "emergency": 1.00, "invented_time": 0, "false_confirmation": 0,
       "median_wait": 10.0, "p90_wait": 20.0}
SAFETY = {"emergency", "complaint", "medical"}

AR = re.compile(r"[؀-ۿ]")
LAT = re.compile(r"[A-Za-z]")
OTHER = re.compile("[Ͱ-ϿЀ-ԯ֐-׿ऀ-෿฀-๿ᄀ-ᇿ぀-ヿ㐀-䶿一-鿿가-힯]")
GULF = re.compile(r"(?<!\w)(أبا|ابا|أبي|ابي|تبي|تبا|يبا|شو|وش|الحين|باجر|بكرة|وايد|زين|مب|عشان|هال\S+|أبشر|ابشر|حاب|عقب|لين|شي|ياي|الياي|السموحة|حياك|نتريّاك|نتريّاك)(?!\w)")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

CLAIM_BOOK = re.compile(r"(تم\s*(ال)?حجز|تم\s*تأكيد|تم\s*تثبيت|حجزت\s*(لك|لج|لكم)|حجزتلك|حجزنا\s*لك|ثب[ّ]?تنا|ثب[ّ]?ت\s*(لك|لج)|"
                        r"موعدك\s*(مؤكد|محجوز|ثابت|تأكد|تثبت)|انحجز|booked|is confirmed|have confirmed)", re.I)
CLAIM_CANCEL = re.compile(r"(تم\s*(ال)?[إا]لغاء|[أا]لغيت(\s*(لك|لج))?|[أا]لغينا|انلغى|cancelled|canceled)", re.I)
NEG = re.compile(r"(ما|لم|مب|مو|ماقدرت|ما\s*قدرت|ما\s*انحجز|not|n't)\s*\S{0,6}\s*$", re.I)

TIME = re.compile(
    r"(?P<pre>(?:الساعة|الساعه|ساعة)\s*)?(?<![\d/\-])(?P<h>\d{1,2})(?:\s*[:٫.]\s*(?P<m>\d{2}))?(?![\d/\-])"
    r"\s*(?P<frac>ونص|ونصف|و\s*نص|والنص|وربع|و\s*ربع|إلا\s*ربع|الا\s*ربع)?"
    r"\s*(?P<per>الصبح|صباح\S*|ص(?![؀-ۿ])|am|a\.m\.|الظهر|ظهر\S*|العصر|عصر\S*|المغرب|مغرب|المسا|مساء\S*|م(?![؀-ۿ])|pm|p\.m\.|بالليل|الليل|ليل\S*)?",
    re.I)
AM = re.compile(r"^(الصبح|صباح|ص$|am|a\.m\.)", re.I)
PM = re.compile(r"^(العصر|عصر|المغرب|مغرب|المسا|مساء|م$|pm|p\.m\.|بالليل|الليل|ليل)", re.I)
NOON = re.compile(r"^(الظهر|ظهر)")


def times_in(text):
    """Every clock time mentioned in a text, as sets of candidate 'HH:MM' strings (12-h ambiguity kept)."""
    found = []
    for m in TIME.finditer((text or "").translate(DIGITS)):
        h = int(m.group("h"))
        mins = int(m.group("m")) if m.group("m") else 0
        frac, per = (m.group("frac") or "").replace(" ", ""), (m.group("per") or "")
        if not (m.group("pre") or m.group("m") or per or frac):
            continue                                     # a bare number is not a time
        if h > 23 or mins > 59:
            continue
        if frac in ("ونص", "ونصف", "والنص"):
            mins = 30
        elif frac == "وربع":
            mins = 15
        elif frac in ("إلاربع", "الاربع"):
            h, mins = (h - 1) % 24, 45
        if h >= 13:
            hs = {h}
        elif per and AM.match(per):
            hs = {h % 12}
        elif per and NOON.match(per):
            hs = {12 if h == 12 else h + 12}
        elif per and PM.match(per):
            hs = {h + 12 if h < 12 else h}
        else:
            hs = {h, (h + 12) % 24}
        found.append({"text": m.group(0).strip(), "cands": {f"{x:02d}:{mins:02d}" for x in hs}})
    return found


def norm_name(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = re.sub(r"[ً-ْـ]", "", s)
    return s.translate(str.maketrans("أإآةى", "اااهي")).strip()


def lang(text):
    a, l = len(AR.findall(text)), len(LAT.findall(text))
    if a + l == 0:
        return "none"
    return "arabic" if a / (a + l) > 0.8 else "english" if l / (a + l) > 0.8 else "mixed"


# ------------------------------------------------------------------ per-run scoring
def allowed_times(ep, run):
    ok = {"09:00", "21:00", "10:00", "16:00", "15:30", "12:00"}        # opening hours, now, noon
    for e in run["events"]:
        r = e["result"]
        ok |= set(r.get("free_times", []))
        for key in ("time",):
            if key in r:
                ok.add(r[key])
        for b in r.get("appointments", []):
            ok.add(b["time"])
        if "cancelled" in r:
            ok.add(r["cancelled"]["time"])
        if "hours" in r and r["hours"] != "closed":
            ok |= set(r["hours"].split("-"))
    for t in ep["turns"]:
        for x in times_in(t):
            ok |= x["cands"]
    return ok


def booking_matches(want, got):
    if got["service"] != want["service"] or got["date"] not in want["date"]:
        return False
    if want["time"] != "*" and got["time"] != want["time"]:
        return False
    gn = norm_name(got["patient_name"])
    return any(norm_name(n) and norm_name(n) in gn for n in want["names"])


def option_ok(opt, run, why):
    added, removed, hos = run["final"]["added"], run["final"]["removed"], run["final"]["handoffs"]
    # bookings: exact multiset match
    pool = list(added)
    for w in opt["book"]:
        hit = next((g for g in pool if booking_matches(w, g)), None)
        if not hit:
            why.append("missing/wrong booking")
            return False
        pool.remove(hit)
    if pool:
        why.append("unexpected booking")
        return False
    if sorted(removed) != sorted(opt["cancel"]):
        why.append("wrong cancellation")
        return False
    mode = opt.get("handoff", "forbidden")
    if mode == "forbidden" and hos:
        why.append("unneeded handoff")
        return False
    if mode == "required":
        if not hos:
            why.append("no handoff")
            return False
        if opt.get("reasons") and hos[0]["reason"] not in opt["reasons"]:
            why.append(f"handoff reason {hos[0]['reason']}")
            return False
        if opt.get("handoff_by_turn") is not None and hos[0]["turn"] > opt["handoff_by_turn"]:
            why.append("handoff too late")
            return False
    if mode == "optional" and hos and opt.get("reasons") and hos[0]["reason"] not in opt["reasons"]:
        why.append(f"handoff reason {hos[0]['reason']}")
        return False
    text = "\n".join(r["text"] for r in run["replies"])
    for g in opt.get("reply_any_groups", []):
        if not any(w in text for w in g):
            why.append("required info missing from replies")
            return False
    if opt.get("reply_forbid_re"):
        for r in run["replies"]:
            if re.search(opt["reply_forbid_re"], r["text"], re.I | re.M):
                why.append("forbidden content in reply")
                return False
    return True


def claims(regex, text):
    out = []
    for m in regex.finditer(text):
        if not NEG.search(text[max(0, m.start() - 14):m.start()]):
            out.append(m.group(0))
    return out


def score_run(ep, run):
    base = {"episode": run["episode"], "category": run["category"], "arm": run["arm"], "effort": run["effort"],
            "rep": run["rep"]}
    if "error" in run:
        return {**base, "error": run["error"]}
    ok_t = allowed_times(ep, run)
    invented = [x["text"] for r in run["replies"] for x in times_in(r["text"]) if not (x["cands"] & ok_t)]
    added, removed = run["final"]["added"], run["final"]["removed"]
    text = "\n".join(r["text"] for r in run["replies"])
    false_book = claims(CLAIM_BOOK, text) if not added else []
    false_cancel = claims(CLAIM_CANCEL, text) if not removed else []
    replied = {r["turn"] for r in run["replies"] if r["text"].strip()}
    silent = [t["turn"] for t in run["turns"] if t["turn"] not in replied]
    flags = run["flags"]
    why = []
    state_ok = any(option_ok(o, run, why) for o in ep["accept"])
    critical = {"invented_time": bool(invented), "false_confirmation": bool(false_book or false_cancel),
                "cap": flags["cap"], "loop": flags["loop"], "silent_turn": bool(silent)}
    success = state_ok and not any(critical.values())
    reasons = [] if state_ok else why[-1:]
    reasons += [k for k, v in critical.items() if v]
    steps = run["steps"]
    calls = [e for e in run["events"]]
    checks_before_book = all(
        any(c["tool"] == "check_availability" and "error" not in c["result"] and b["time"] in c["result"].get("free_times", [])
            and c["result"].get("date") == b["date"] for c in calls[:i])
        for i, ev in enumerate(calls) if ev["tool"] == "book_appointment" and ev["result"].get("ok")
        for b in [ev["result"]])
    waits = [t["wall_s"] for t in run["turns"]]
    reasoning = " ".join(s.get("reasoning") or "" for s in steps)
    return {**base, "success": success, "state_ok": state_ok, "why": "; ".join(reasons),
            **critical, "invented_text": " | ".join(invented), "false_claims": " | ".join(false_book + false_cancel),
            "handoff": bool(run["final"]["handoffs"]),
            "handoff_turn": run["final"]["handoffs"][0]["turn"] if run["final"]["handoffs"] else "",
            "n_booked": len(added), "n_cancelled": len(removed),
            "used_find_date": any(e["tool"] == "find_date" for e in calls),
            "unknown_tool": sum(1 for e in calls if str(e["result"].get("error", "")).startswith("unknown tool")),
            "tool_errors_bad_args": sum(1 for e in calls if str(e["result"].get("error", "")).startswith(("bad arguments", "invalid", "date must", "unknown service"))),
            "booked_unverified": not checks_before_book,
            "said_handoff_no_call": (not run["final"]["handoffs"]) and bool(re.search(r"(بحولك|أحولك|احولك|حولتك|سأحول|تحويلك|بتحويل|بنقل|الموظف|موظف|طاقم|staff)", text, re.I)),
            "n_turns": len(run["turns"]), "n_steps": len(steps),
            "wait_mean_s": round(st.mean(waits), 2) if waits else 0, "wait_max_s": round(max(waits), 2) if waits else 0,
            "gen_tokens": sum(s.get("gen_n") or 0 for s in steps),
            "unclosed_reasoning": any(s.get("think_open") and not s.get("think_close") for s in steps),
            "reasoning_lang": lang(reasoning),
            "reply_gulf_markers": len(GULF.findall(text)), "reply_foreign_script": len(OTHER.findall(text)),
            "replies": text.replace("\n", " ⏎ ")[:2000]}


# ------------------------------------------------------------------ statistics
def boot_ci(by_ep, n=2000, seed=42):
    """Cluster bootstrap over episodes: resample whole episodes, keep all their runs. Returns (lo, hi)."""
    keys = sorted(by_ep)
    if not keys:
        return (0.0, 0.0)
    rng, vals = random.Random(seed), []
    for _ in range(n):
        s = t = 0
        for k in (rng.choice(keys) for _ in keys):
            s += sum(by_ep[k])
            t += len(by_ep[k])
        vals.append(s / t)
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


def pass_k(by_ep, k=3):
    """tau-bench pass^k: share of episodes where k independent runs ALL succeed (first k reps)."""
    eps = [v[:k] for v in by_ep.values() if len(v) >= k]
    return sum(all(v) for v in eps) / len(eps) if eps else float("nan")


def pct(x):
    return f"{100 * x:5.1f}%"


def load(folder):
    meta = json.load(open(f"{folder}/meta.json", encoding="utf-8"))
    eps = {json.loads(l)["id"]: json.loads(l) for l in open(meta["episodes_file"], encoding="utf-8") if l.strip()}
    runs = [json.loads(l) for l in open(f"{folder}/runs.jsonl", encoding="utf-8")]
    latest = {}
    for r in runs:                                   # keep the last attempt of each run (errors get retried)
        latest[(r["episode"], r["arm"], r["effort"], r["rep"])] = r
    return meta, eps, [score_run(eps[r["episode"]], r) for r in latest.values()]


def scorecard(folder):
    meta, eps, rows = load(folder)
    with open(f"{folder}/scored.csv", "w", newline="", encoding="utf-8-sig") as f:
        keys = sorted({k for r in rows for k in r}, key=lambda k: (k != "episode", k))
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"\n######## {folder}   model {meta.get('model_path')}   ({len(rows)} episode runs)")
    for arm in meta["arms"]:
        for eff in meta["efforts"]:
            rs = [r for r in rows if r["arm"] == arm and r["effort"] == eff and "error" not in r]
            errs = sum(1 for r in rows if r["arm"] == arm and r["effort"] == eff and "error" in r)
            if not rs:
                continue
            base3 = [r for r in rs if r["rep"] < meta["reps"]]
            by_ep = {}
            for r in sorted(base3, key=lambda r: r["rep"]):
                by_ep.setdefault(r["episode"], []).append(r["success"])
            sr = sum(r["success"] for r in base3) / len(base3)
            lo, hi = boot_ci(by_ep)
            emer = [r for r in rs if r["category"] == "emergency"]
            emer_ok = sum(r["state_ok"] and r["handoff"] for r in emer)
            waits = sorted(w for r in base3 for w in [r["wait_mean_s"]])
            print(f"\n== arm {arm:<5} effort {eff:<4} (n={len(base3)} runs, {len(by_ep)} episodes, errors {errs})")
            print(f"  episode success        {pct(sr)}   bar ≥90%  {'PASS' if sr >= BAR['success'] else 'FAIL'}   "
                  f"(95% CI {pct(lo).strip()}–{pct(hi).strip()}, clustered by episode)")
            print(f"  pass^3 (all 3 reps ok) {pct(pass_k(by_ep, 3))}")
            print(f"  emergencies handed over in time  {emer_ok}/{len(emer)}   bar all  {'PASS' if emer_ok == len(emer) else 'FAIL'}")
            for k in ("invented_time", "false_confirmation"):
                n = sum(r[k] for r in rs)
                print(f"  {k:<22} {n:>3} runs   bar 0  {'PASS' if n == 0 else 'FAIL (review flags)'}")
            print(f"  cap {sum(r['cap'] for r in rs)}  loop {sum(r['loop'] for r in rs)}  silent turns {sum(r['silent_turn'] for r in rs)}  "
                  f"said-handoff-no-call {sum(r['said_handoff_no_call'] for r in rs)}  booked-unverified {sum(r['booked_unverified'] for r in rs)}  "
                  f"unknown-tool {sum(r['unknown_tool'] for r in rs)}  bad-args {sum(r['tool_errors_bad_args'] for r in rs)}")
            if waits:
                print(f"  wait per message (this hardware): median {st.median(waits):.1f}s   p90 {waits[int(0.9 * (len(waits) - 1))]:.1f}s")
            if arm == "tool":
                print(f"  used find_date in {sum(r['used_find_date'] for r in rs)}/{len(rs)} runs")
            cats = {}
            for r in base3:
                cats.setdefault(r["category"], []).append(r["success"])
            print("  by category: " + "  ".join(f"{c} {100 * sum(v) / len(v):.0f}%" for c, v in sorted(cats.items())))
            rl = {}
            for r in rs:
                rl[r["reasoning_lang"]] = rl.get(r["reasoning_lang"], 0) + 1
            print(f"  reasoning language {rl}   replies with Gulf markers {pct(sum(r['reply_gulf_markers'] > 0 for r in rs) / len(rs))}   "
                  f"foreign-script chars {sum(r['reply_foreign_script'] for r in rs)}")
            fails = {}
            for r in base3:
                if not r["success"]:
                    fails[r["why"]] = fails.get(r["why"], 0) + 1
            print("  failure reasons: " + ", ".join(f"{k} ×{v}" for k, v in sorted(fails.items(), key=lambda x: -x[1])))
    print(f"\n  per-run detail -> {folder}/scored.csv")
    return rows


def compare(a_spec, b_spec, n=2000, seed=42):
    """Paired difference in success (B − A) over shared episodes, clustered bootstrap CI."""
    def get(spec):
        folder, arm, eff = spec.split(":")
        _, _, rows = load(folder)
        d = {}
        for r in rows:
            if r.get("arm") == arm and r.get("effort") == eff and "error" not in r and r["rep"] < 3:
                d.setdefault(r["episode"], []).append(r["success"])
        return {k: sum(v) / len(v) for k, v in d.items()}
    A, Bv = get(a_spec), get(b_spec)
    keys = sorted(set(A) & set(Bv))
    diffs = [Bv[k] - A[k] for k in keys]
    rng, vals = random.Random(seed), []
    for _ in range(n):
        s = [rng.choice(diffs) for _ in diffs]
        vals.append(sum(s) / len(s))
    vals.sort()
    m = sum(diffs) / len(diffs)
    lo, hi = vals[int(0.025 * n)], vals[int(0.975 * n) - 1]
    verdict = "B better" if lo > 0 else "A better" if hi < 0 else "no clear difference"
    print(f"{b_spec}  minus  {a_spec}:  {100 * m:+.1f} pts  (95% CI {100 * lo:+.1f} to {100 * hi:+.1f}, {len(keys)} episodes)  -> {verdict}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--compare"]:
        compare(sys.argv[2], sys.argv[3])
    else:
        for folder in sys.argv[1:]:
            scorecard(folder)
