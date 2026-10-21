#!/usr/bin/env python3
"""
miqyas · front-desk v2 — how fast would each conversation be on the reception laptop?

Running ~11,000 model calls on a 2020 Intel MacBook Air is impossible, so:
  1. bench    : llama-bench measures the laptop's prompt (pp) and generation (tg) speed at several
                context depths -> results/frontdesk_v2/air_speed/<model>.json
  2. predict  : every GPU call's real token counts are converted into laptop time:
                  t_call = prompt_n / pp(depth) + gen_n / tg(depth)
                and summed per patient message -> median / p90 wait per configuration
  3. validate : the same formula applied to a REAL laptop run must land within ±25% (median
                absolute error) of the measured times, or the predictions are not published.

Usage:
  python3 scripts/air_speed.py bench    <model.gguf> <name>         # on the Air (~15-30 min per model)
  python3 scripts/air_speed.py validate <name> results/frontdesk_v2/<air-run-label>
  python3 scripts/air_speed.py predict  <name> results/frontdesk_v2/<gpu-label> [...]
"""
import json
import os
import statistics as st
import subprocess
import sys

OUT = "results/frontdesk_v2/air_speed"
DEPTHS = [int(x) for x in os.environ.get("BENCH_DEPTHS", "0,1024,2048,4096,8192").split(",")]
LLAMA_BENCH = os.path.expanduser(os.environ.get("LLAMA_BENCH", "~/llama.cpp/build/bin/llama-bench"))


def bench(model, name):
    os.makedirs(OUT, exist_ok=True)
    cmd = [LLAMA_BENCH, "-m", model, "-p", "512", "-n", "64", "-d", ",".join(map(str, DEPTHS)),
           "-r", os.environ.get("BENCH_REPS", "2"), "-ngl", "0", "-o", "json"]
    print("running:", " ".join(cmd), "\n(this takes a while on a laptop CPU; keep it plugged in and awake)")
    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    rows = json.loads(raw)
    pp, tg = {}, {}
    for r in rows:
        d = r.get("n_depth", 0)
        if r.get("n_prompt", 0) > 0 and r.get("n_gen", 0) == 0:
            pp[d] = r["avg_ts"]
        elif r.get("n_gen", 0) > 0 and r.get("n_prompt", 0) == 0:
            tg[d] = r["avg_ts"]
    res = {"model": model, "name": name, "pp_tok_s": pp, "tg_tok_s": tg, "raw": rows}
    json.dump(res, open(f"{OUT}/{name}.json", "w"), indent=1)
    for d in sorted(pp):
        print(f"depth {d:>5}: prompt {pp[d]:7.1f} tok/s   generate {tg.get(d, float('nan')):6.2f} tok/s")
    return res


def _interp(table, depth):
    ks = sorted(int(k) for k in table)
    vals = {int(k): v for k, v in table.items()}
    if depth <= ks[0]:
        return vals[ks[0]]
    if depth >= ks[-1]:
        return vals[ks[-1]]
    for a, b in zip(ks, ks[1:]):
        if a <= depth <= b:
            return vals[a] + (vals[b] - vals[a]) * (depth - a) / (b - a)


def call_time(sp, step):
    p, c, g = step.get("prompt_n") or 0, step.get("cached_n") or 0, step.get("gen_n") or 0
    # rates at the middle of the context range each phase actually covers
    return p / _interp(sp["pp_tok_s"], c + p / 2) + g / _interp(sp["tg_tok_s"], c + p + g / 2)


def per_message(sp, folder, arm=None, effort=None):
    out = []
    for l in open(f"{folder}/runs.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if "error" in r or (arm and r["arm"] != arm) or (effort and r["effort"] != effort) or r["rep"] >= 3:
            continue
        for t in r["turns"]:
            pred = sum(call_time(sp, s) for s in r["steps"] if s["turn"] == t["turn"])
            out.append({"arm": r["arm"], "effort": r["effort"], "pred": pred, "measured": t["wall_s"]})
    return out


def q(xs, p):
    xs = sorted(xs)
    return xs[int(p * (len(xs) - 1))] if xs else float("nan")


def predict(name, folders):
    sp = json.load(open(f"{OUT}/{name}.json"))
    for folder in folders:
        meta = json.load(open(f"{folder}/meta.json"))
        for arm in meta["arms"]:
            for eff in meta["efforts"]:
                w = [x["pred"] for x in per_message(sp, folder, arm, eff)]
                if w:
                    ok = q(w, .5) <= 10 and q(w, .9) <= 20
                    print(f"{folder} {arm:<5} {eff:<4}  predicted laptop wait per message: median {q(w, .5):6.1f}s  "
                          f"p90 {q(w, .9):6.1f}s  -> bar {'PASS' if ok else 'FAIL'}  (n={len(w)})")


def validate(name, folder):
    sp = json.load(open(f"{OUT}/{name}.json"))
    rows = per_message(sp, folder)
    errs = [abs(x["pred"] - x["measured"]) / x["measured"] for x in rows if x["measured"] > 0]
    m = st.median(errs)
    print(f"{len(rows)} messages: measured median {q([x['measured'] for x in rows], .5):.1f}s, predicted median "
          f"{q([x['pred'] for x in rows], .5):.1f}s, median absolute error {100 * m:.0f}%  -> "
          f"{'VALID (≤25%)' if m <= 0.25 else 'NOT VALID: do not publish predicted laptop times'}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "bench":
        bench(sys.argv[2], sys.argv[3])
    elif cmd == "predict":
        predict(sys.argv[2], sys.argv[3:])
    elif cmd == "validate":
        validate(sys.argv[2], sys.argv[3])
