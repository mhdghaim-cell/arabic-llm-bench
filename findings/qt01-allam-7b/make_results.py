"""Build results.json for qt-01 from the scored runs (every published number comes from here)."""
import csv, json, re, collections, subprocess
D = "results/qt01/allam-7b-q4-qt01"
rows = list(csv.DictReader(open(f"{D}/scored.csv", encoding="utf-8-sig")))
runs = [json.loads(l) for l in open(f"{D}/runs.jsonl", encoding="utf-8")]
sc = open(f"{D}/scorecard.txt", encoding="utf-8").read()
T = lambda r, k: r[k] == "True"
main = [r for r in rows if int(r["rep"]) < 3]                     # 42 episodes x 3 reps
ci = re.search(r"episode success\s+([\d.]+)%.*?95% CI ([\d.]+)%–([\d.]+)%", sc)
p3 = re.search(r"pass\^3 \(all 3 reps ok\)\s+([\d.]+)%", sc)
wait = re.search(r"median ([\d.]+)s\s+p90 ([\d.]+)s", sc)
def handed(cat):
    rr = [r for r in runs if r["category"] == cat]
    return [sum(any(c["name"] == "handoff_to_human" for s in r["steps"] for c in s["calls"]) for r in rr), len(rr)]
def phone(cat=None):
    rr = [r for r in runs if cat is None or r["category"] == cat]
    return [sum(any("[رقم محذوف]" in x["text"] for x in r["replies"]) for r in rr), len(rr)]
bycat = collections.defaultdict(lambda: [0, 0])
for r in main:
    bycat[r["category"]][0] += T(r, "success"); bycat[r["category"]][1] += 1
res = {
  "trial": "qt-01-allam-7b-clinic", "type": "quick-trial (numbers only, no verdict)",
  "model": "ALLaM-AI/ALLaM-7B-Instruct-preview", "quant": "Q4_K_M (llama.cpp, converted by Miqyas)",
  "model_sha256": open("results/qt01/model_provenance.txt").read().split()[3],
  "job": "clinic-frontdesk", "test_set": "public test set only (private held-out set not yet written)",
  "setup": "tool arm (date tool), prompted-JSON adapter (no native tool syntax), ALLaM model-card sampling, 4,096-token window",
  "scenarios": 42, "reps": 3, "runs_total": len(runs), "runs_main": len(main),
  "episode_success_pct": float(ci.group(1)), "ci95_pct": [float(ci.group(2)), float(ci.group(3))],
  "successes_main": sum(T(r, "success") for r in main),
  "pass3_pct": float(p3.group(1)),
  "handed_over": {c: handed(c) for c in ("emergency", "complaint", "medical")},
  "flags_runs": {k: sum(T(r, k) for r in rows) for k in ("invented_time", "false_confirmation", "booked_unverified")},
  "by_category_main": {k: v for k, v in sorted(bycat.items())},
  "wait_per_message_rtx4090_s": {"median": float(wait.group(1)), "p90": float(wait.group(2))},
  "laptop_floor": "not measured in this Quick Trial",
  "post_hoc_invented_phone_runs": {"all": phone(), "emergency": phone("emergency"), "complaint": phone("complaint"), "medical": phone("medical")},
  "errors": sum("error" in r for r in runs), "context_overflows": sum(r["flags"].get("context", False) for r in runs),
  "run_commit": "6985322", "results_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
}
json.dump(res, open("findings/qt01-allam-7b/results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
