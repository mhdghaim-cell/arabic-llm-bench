#!/usr/bin/env python3
"""
miqyas · blind audit — checks that the automatic scorer agrees with a human.

Step 1 (make the sheet):
    python3 scripts/audit_sample.py make results/frontdesk/<label> 30
  -> writes <label>/audit_sheet.csv : message, what the model did, an empty "human_ok" column.
     The scorer's verdict is NOT in the sheet, so you grade blind.

Step 2 (grade): open audit_sheet.csv in Numbers/Excel, put 1 (acceptable) or 0 (not) in human_ok.
     Judge as a clinic manager would: would you accept this reply/action from your receptionist?

Step 3 (compare):
    python3 scripts/audit_sample.py compare results/frontdesk/<label>
  -> agreement rate + every disagreement, so we can see whether the scorer is too strict or too lenient.
"""
import csv
import json
import random
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import score_frontdesk as S  # noqa: E402


def load(folder):
    meta = json.load(open(f"{folder}/meta.json", encoding="utf-8"))
    cases = {c["id"]: c for c in (json.loads(l) for l in open(meta["cases_file"], encoding="utf-8") if l.strip())}
    S.CASES.clear()
    S.CASES.update(cases)
    runs = [json.loads(l) for l in open(f"{folder}/runs.jsonl", encoding="utf-8")]
    return cases, [r for r in runs if "error" not in r]


def make(folder, n):
    cases, runs = load(folder)
    rnd = random.Random(7)
    # stratify: every category represented, then fill at random
    by_cat = {}
    for r in runs:
        by_cat.setdefault(r["category"], []).append(r)
    pick = [rnd.choice(v) for v in by_cat.values()]
    rest = [r for r in runs if r not in pick]
    pick += rnd.sample(rest, max(0, n - len(pick)))
    rnd.shuffle(pick)
    with open(f"{folder}/audit_sheet.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["key", "message", "tool_called", "tool_args", "reply_to_customer", "human_ok", "comment"])
        for r in pick:
            calls = r.get("calls") or []
            w.writerow([f"{r['case']}|{r['effort']}|{r['rep']}", cases[r["case"]]["message"],
                        calls[0]["name"] if calls else "", json.dumps(calls[0]["args"], ensure_ascii=False) if calls else "",
                        (r.get("answer") or "")[:600], "", ""])
    print(f"wrote {folder}/audit_sheet.csv with {len(pick)} runs — grade the human_ok column (1/0), then run 'compare'.")


def compare(folder):
    cases, runs = load(folder)
    idx = {f"{r['case']}|{r['effort']}|{r['rep']}": r for r in runs}
    rows = list(csv.DictReader(open(f"{folder}/audit_sheet.csv", encoding="utf-8-sig")))
    graded = [x for x in rows if x["human_ok"].strip() in ("0", "1")]
    agree, dis = 0, []
    for x in graded:
        auto = S.score_run(idx[x["key"]])["correct"]
        human = x["human_ok"].strip() == "1"
        if auto == human:
            agree += 1
        else:
            dis.append((x["key"], "scorer TOO STRICT" if human else "scorer TOO LENIENT", x["message"], x["tool_called"],
                        x["tool_args"], x["reply_to_customer"][:200], x["comment"]))
    print(f"graded {len(graded)}  agreement {agree}/{len(graded)} = {agree / max(1, len(graded)):.0%}")
    for d in dis:
        print("\n", " | ".join(d))


if __name__ == "__main__":
    {"make": lambda: make(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 30),
     "compare": lambda: compare(sys.argv[2])}[sys.argv[1]]()
