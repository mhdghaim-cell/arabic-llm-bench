#!/usr/bin/env python3
"""
miqyas · re-run only the runs whose text was damaged by the old per-token decoder,
and use them as a reproducibility check at the same time.

    python3 scripts/repair_rerun.py prepare results/frontdesk/<label>
        -> backs up runs.jsonl, removes damaged runs (text containing U+FFFD),
           saves the originals to repro_originals.jsonl, and reports how many.
    then re-run the SAME run_frontdesk.py command — it resumes and redoes only those runs
    (same seeds, fixed decoder).
    python3 scripts/repair_rerun.py compare results/frontdesk/<label>
        -> for every re-run: did the model make the same tool call with the same arguments,
           and stop the same way? Identical = the run is reproducible.
"""
import json
import shutil
import sys
import time


def key(d):
    return (d["case"], d["effort"], d["rep"])


def damaged(d):
    return any("�" in (d.get(f) or "") for f in ("raw", "answer", "reasoning"))


def prepare(folder):
    path = f"{folder}/runs.jsonl"
    runs = [json.loads(l) for l in open(path, encoding="utf-8")]
    bad = [d for d in runs if damaged(d)]
    keep = [d for d in runs if not damaged(d)]
    shutil.copy(path, f"{folder}/runs_backup_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
    with open(f"{folder}/repro_originals.jsonl", "w", encoding="utf-8") as f:
        for d in bad:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with open(path, "w", encoding="utf-8") as f:
        for d in keep:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    by = {}
    for d in bad:
        by[d["effort"]] = by.get(d["effort"], 0) + 1
    print(f"{len(runs)} runs, {len(bad)} with damaged text ({by}); removed them for re-running.")
    print("Backup saved. Now re-run the same run_frontdesk.py command (it will redo only these).")


def compare(folder):
    orig = {key(d): d for d in (json.loads(l) for l in open(f"{folder}/repro_originals.jsonl", encoding="utf-8"))}
    new = {key(d): d for d in (json.loads(l) for l in open(f"{folder}/runs.jsonl", encoding="utf-8")) if key(d) in orig}
    same = 0
    for k, o in orig.items():
        n = new.get(k)
        if n is None:
            print("not re-run yet:", k)
            continue
        a = (json.dumps(o.get("calls"), sort_keys=True, ensure_ascii=False), o.get("stop"), o.get("completion_tokens"))
        b = (json.dumps(n.get("calls"), sort_keys=True, ensure_ascii=False), n.get("stop"), n.get("completion_tokens"))
        if a == b:
            same += 1
        else:
            print("DIFFERENT:", k, "\n  before:", a, "\n  after: ", b)
    print(f"reproducibility: {same}/{len(orig)} identical (same tool call, arguments, stop reason and token count)")
    left = sum("�" in (d.get("answer") or "") for d in new.values())
    print(f"damaged text remaining after re-run: {left}")


if __name__ == "__main__":
    {"prepare": prepare, "compare": compare}[sys.argv[1]](sys.argv[2])
