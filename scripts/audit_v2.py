#!/usr/bin/env python3
"""
miqyas · front-desk v2 — human checks on the automatic scorer.

  make    <sheet.csv> <folder> [folder ...]   30 test conversations, stratified across models x arms,
                                              shown WITHOUT model name, arm or scorer verdict (key saved apart)
  compare <sheet.csv>                         agreement between the human grades and the scorer (bar ≥ 90%)
  flags   <sheet.csv> <folder> [folder ...]   every invented-time / false-confirmation flag, for human review
  flagsum <sheet.csv>                         confirmed vs cleared flags per configuration
  repro   <folderA> <folderB>                 same seeds, same outcome? (reproducibility check)
"""
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_v2 import load  # noqa: E402

N_AUDIT, SEED = 30, 7


def transcript(run):
    lines, k = [], -1
    ev = iter(run["events"])
    for m in run["messages"][1:]:
        if m["role"] == "user":
            k += 1
            lines.append(f"[{k + 1}] PATIENT: {m['content']}")
        elif m["role"] == "assistant":
            for c in m.get("tool_calls") or []:
                e = next(ev, None)
                res = json.dumps(e["result"], ensure_ascii=False)[:220] if e else ""
                lines.append(f"      tool: {c['function']['name']}({c['function']['arguments']}) -> {res}")
            if m.get("content"):
                lines.append(f"    RECEPTIONIST: {m['content']}")
    return "\n".join(lines)


def goal(ep):
    parts = []
    for o in ep["accept"]:
        p = []
        for b in o["book"]:
            p.append(f"book {b['service']} {'/'.join(b['date'])} {b['time']} ({'/'.join(b['names'])})")
        if o["cancel"]:
            p.append("cancel " + ",".join(o["cancel"]))
        p.append({"required": "MUST hand over", "optional": "hand-over optional", "forbidden": "no hand-over"}[o["handoff"]]
                 + (f" ({'/'.join(o.get('reasons', []))})" if o.get("reasons") else "")
                 + (f" by message {o['handoff_by_turn'] + 1}" if o.get("handoff_by_turn") is not None else ""))
        if not o["book"] and not o["cancel"]:
            p.append("no booking / no cancellation")
        if o.get("reply_any_groups"):
            p.append("must mention: " + " AND ".join("/".join(g[:3]) for g in o["reply_any_groups"]))
        parts.append("; ".join(p))
    return " OR ".join(parts) + (f"   [{ep['note']}]" if ep.get("note") else "")


def runs_of(folders):
    out = []
    for f in folders:
        meta, eps, rows = load(f)
        raw = {}
        for l in open(f"{f}/runs.jsonl", encoding="utf-8"):
            r = json.loads(l)
            raw[(r["episode"], r["arm"], r["effort"], r["rep"])] = r
        for s in rows:
            if "error" in s or s["rep"] >= 3:
                continue
            out.append((meta["label"], eps[s["episode"]], raw[(s["episode"], s["arm"], s["effort"], s["rep"])], s))
    return out


def make(sheet, folders):
    pool = runs_of(folders)
    rng = random.Random(SEED)
    strata = {}
    for x in pool:
        strata.setdefault((x[0], x[2]["arm"], x[2]["effort"]), []).append(x)
    for v in strata.values():
        rng.shuffle(v)
    keys, picked = sorted(strata), []
    while len(picked) < N_AUDIT and any(strata.values()):
        for k in keys:
            if strata[k] and len(picked) < N_AUDIT:
                picked.append(strata[k].pop())
    rng.shuffle(picked)
    key = {}
    with open(sheet, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["item", "what_correct_looks_like", "conversation", "success_1_or_0", "invented_time_1_or_0",
                    "false_confirmation_1_or_0", "notes"])
        for i, (label, ep, run, s) in enumerate(picked, 1):
            w.writerow([i, goal(ep), transcript(run), "", "", "", ""])
            key[i] = {"label": label, "episode": ep["id"], "arm": run["arm"], "effort": run["effort"], "rep": run["rep"],
                      "success": s["success"], "invented_time": s["invented_time"], "false_confirmation": s["false_confirmation"],
                      "why": s["why"]}
    json.dump(key, open(sheet.replace(".csv", "_key.json"), "w"), indent=1)
    print(f"{len(picked)} conversations -> {sheet}  (key kept apart in {sheet.replace('.csv', '_key.json')})")


def compare(sheet):
    key = json.load(open(sheet.replace(".csv", "_key.json")))
    rows = list(csv.DictReader(open(sheet, encoding="utf-8-sig")))
    agree, dis = 0, []
    for r in rows:
        k = key[str(r["item"])]
        h = r["success_1_or_0"].strip() == "1"
        if h == k["success"]:
            agree += 1
        else:
            dis.append((r["item"], k, h, r["notes"]))
    n = len(rows)
    print(f"agreement {agree}/{n} = {100 * agree / n:.0f}%   bar ≥90%  {'PASS' if agree / n >= 0.9 else 'FAIL'}")
    for item, k, h, notes in dis:
        print(f"  item {item}: {k['label']} {k['episode']} {k['arm']}  scorer={'ok' if k['success'] else 'fail'} ({k['why']})  "
              f"human={'ok' if h else 'fail'}  notes: {notes}")


def flags(sheet, folders):
    n = 0
    with open(sheet, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["label", "episode", "arm", "effort", "rep", "flag", "flagged_text", "conversation", "confirmed_1_or_0"])
        for label, ep, run, s in runs_of(folders):
            for flag, txt in (("invented_time", s["invented_text"]), ("false_confirmation", s["false_claims"])):
                if s[flag]:
                    w.writerow([label, ep["id"], run["arm"], run["effort"], run["rep"], flag, txt, transcript(run), ""])
                    n += 1
    print(f"{n} flags -> {sheet}")


def flagsum(sheet):
    agg = {}
    for r in csv.DictReader(open(sheet, encoding="utf-8-sig")):
        k = (r["label"], r["arm"], r["effort"], r["flag"])
        a = agg.setdefault(k, [0, 0])
        a[0 if r["confirmed_1_or_0"].strip() == "1" else 1] += 1
    for k, (c, x) in sorted(agg.items()):
        print(f"{' '.join(k):<60} confirmed {c:>3}   cleared {x:>3}")


def repro(a, b):
    def outcomes(folder):
        _, _, rows = load(folder)
        return {(r["episode"], r["arm"], r["effort"], r["rep"]): r for r in rows if "error" not in r}
    A, B = outcomes(a), outcomes(b)
    shared = sorted(set(A) & set(B))
    same = sum(A[k]["success"] == B[k]["success"] and A[k]["why"] == B[k]["why"] for k in shared)
    ident = sum(A[k]["replies"] == B[k]["replies"] for k in shared)
    print(f"{len(shared)} conversations re-run: same outcome {same}/{len(shared)}, word-for-word identical {ident}/{len(shared)}")
    for k in shared:
        if A[k]["success"] != B[k]["success"]:
            print("  differs:", k, A[k]["why"], "->", B[k]["why"])


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "make":
        make(sys.argv[2], sys.argv[3:])
    elif c == "compare":
        compare(sys.argv[2])
    elif c == "flags":
        flags(sys.argv[2], sys.argv[3:])
    elif c == "flagsum":
        flagsum(sys.argv[2])
    elif c == "repro":
        repro(sys.argv[2], sys.argv[3])
