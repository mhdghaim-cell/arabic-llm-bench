#!/usr/bin/env python3
"""
miqyas · front-desk test runner.

Sends every case in corpus/frontdesk_v0.jsonl to a running llama-server and logs
what the model did. Resumable: re-running skips anything already logged.

Usage (from ~/miqyas, llama-server on :8080):
    python3 scripts/run_frontdesk.py --label jais3-0.9b-q4 --efforts low high --reps 3
    python3 scripts/run_frontdesk.py --label qwen3-4b-q4 --mode chat --efforts off on --reps 3

Modes
  jais : builds the prompt with /apply-template, generates with /completion, and parses
         Jais 3's own control tokens itself — so llama.cpp's tool-call parser cannot
         lose a call. Efforts: low | medium | high.
  chat : standard /v1/chat/completions with server-side parsing (for other models).
         Efforts: off | on  (thinking disabled / enabled).

Output: results/frontdesk/<label>/runs.jsonl  (one line per case x effort x rep)
"""
import argparse
import json
import os
import platform
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from try_tools import PROMPTS, TOOLS  # noqa: E402

BASE = "http://localhost:8080"
SAMPLING = {"temperature": 0.7, "top_p": 0.95, "top_k": 20}   # model card, Arabic
_piece_cache = {}


def post(path, body, timeout=900):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def _piece(i):
    if i not in _piece_cache:
        _piece_cache[i] = post("/detokenize", {"tokens": [i]}).get("content", "")
    return _piece_cache[i]


_SPECIAL = re.compile(r"^<\|?/?ifm\|[a-z_]+\|?>$")


def detok(ids):
    """Token ids -> text, keeping Jais 3's control tokens.

    Ordinary tokens are decoded together in runs: decoding them one at a time splits
    multi-byte UTF-8 characters (Arabic-Indic digits, emoji) into broken "\ufffd" pieces.
    Control tokens are decoded one by one so they survive as text.
    """
    out, run = [], []
    for i in ids:
        p = _piece(i)
        if _SPECIAL.match(p):
            if run:
                out.append(post("/detokenize", {"tokens": run}).get("content", ""))
                run = []
            out.append(p)
        else:
            run.append(i)
    if run:
        out.append(post("/detokenize", {"tokens": run}).get("content", ""))
    return "".join(out)


THINK_CLOSE = re.compile(r"</ifm\|(think[a-z_]*)>")
CALL = re.compile(r"<ifm\|tool_call>(.*?)(?:</ifm\|tool_call>|$)", re.S)
ARG = re.compile(r"<ifm\|arg_key>(.*?)</ifm\|arg_key>\s*<ifm\|arg_value>(.*?)(?:</ifm\|arg_value>|$)", re.S)
CTRL = re.compile(r"<\|?/?ifm\|[a-z_]+\|?>")


def parse_jais(prompt_tail, text):
    """Split raw Jais 3 output into reasoning / tool calls / answer."""
    opened = (re.findall(r"<ifm\|(think[a-z_]*)>\s*$", prompt_tail) or [None])[0]
    m = THINK_CLOSE.search(text)
    if opened and m:
        reasoning, rest, closed = text[:m.start()], text[m.end():], m.group(1)
    elif opened:
        reasoning, rest, closed = text, "", None          # never closed its reasoning
    else:
        reasoning, rest, closed = "", text, None
    calls = []
    for body in CALL.findall(rest):
        name = re.split(r"<ifm\|arg_key>", body)[0].strip()
        args = {}
        for k, v in ARG.findall(body):
            v = v.strip()
            try:
                v = json.loads(v)
            except Exception:
                v = v.strip('"')
            args[k.strip()] = v
        calls.append({"name": name, "args": args})
    answer = CTRL.sub("", re.sub(r"<ifm\|tool_calls>.*?(</ifm\|tool_calls>|$)", "", rest, flags=re.S)).strip()
    return {"reasoning": CTRL.sub("", reasoning).strip(), "calls": calls, "answer": answer,
            "think_open": opened, "think_close": closed}


def run_jais(msg, effort, seed, n_predict, system):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": msg}]
    prompt = post("/apply-template", {"messages": messages, "tools": TOOLS,
                                      "chat_template_kwargs": {"reasoning_effort": effort}})["prompt"]
    t0 = time.time()
    r = post("/completion", {"prompt": prompt, "n_predict": n_predict, "seed": seed, "return_tokens": True,
                             "cache_prompt": True, **SAMPLING})
    wall = time.time() - t0
    text = detok(r.get("tokens", []))
    p = parse_jais(prompt[-60:], text)
    return {**p, "raw": text, "wall_s": round(wall, 2), "stop": r.get("stop_type"),
            "prompt_tokens": r.get("tokens_evaluated"), "completion_tokens": len(r.get("tokens", [])),
            "timings": r.get("timings", {})}


def run_chat(msg, effort, seed, n_predict, system):
    body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": msg}],
            "tools": TOOLS, "max_tokens": n_predict, "seed": seed, **SAMPLING,
            "chat_template_kwargs": {"enable_thinking": effort == "on"}}
    t0 = time.time()
    r = post("/v1/chat/completions", body)
    wall = time.time() - t0
    ch = r["choices"][0]
    m = ch["message"]
    calls = []
    for c in m.get("tool_calls") or []:
        try:
            args = json.loads(c["function"]["arguments"])
        except Exception:
            args = {"_unparsed": c["function"]["arguments"]}
        calls.append({"name": c["function"]["name"], "args": args})
    return {"reasoning": m.get("reasoning_content") or "", "calls": calls, "answer": m.get("content") or "",
            "think_open": None, "think_close": None, "raw": None, "wall_s": round(wall, 2),
            "stop": ch.get("finish_reason"), "prompt_tokens": r["usage"]["prompt_tokens"],
            "completion_tokens": r["usage"]["completion_tokens"], "timings": r.get("timings", {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="e.g. jais3-0.9b-q4 (folder name for results)")
    ap.add_argument("--mode", choices=["jais", "chat"], default="jais")
    ap.add_argument("--efforts", nargs="+", default=["low", "high"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--cases", default="corpus/frontdesk_v1.jsonl")
    ap.add_argument("--prompt", choices=sorted(PROMPTS), default="v1")
    ap.add_argument("--safety-reps", type=int, default=2,
                    help="extra reps for emergency/complaint/medical cases (the headline safety numbers)")
    ap.add_argument("--show", action="store_true", help="print each raw output (for the smoke test)")
    ap.add_argument("--only", nargs="*", help="run only these case ids")
    ap.add_argument("--n-predict", type=int, default=4096)
    a = ap.parse_args()

    cases = [json.loads(l) for l in open(a.cases, encoding="utf-8") if l.strip()]
    if a.only:
        cases = [c for c in cases if c["id"] in a.only]
    out_dir = f"results/frontdesk/{a.label}"
    os.makedirs(out_dir, exist_ok=True)
    out = f"{out_dir}/runs.jsonl"
    done = set()
    if os.path.exists(out):
        for l in open(out, encoding="utf-8"):
            d = json.loads(l)
            if "error" not in d:                      # failed runs get retried
                done.add((d["case"], d["effort"], d["rep"]))

    try:
        props = json.load(urllib.request.urlopen(BASE + "/props", timeout=5))
    except Exception:
        props = {}
    meta = {"label": a.label, "mode": a.mode, "machine": platform.platform(), "sampling": SAMPLING,
            "n_predict": a.n_predict, "cases_file": a.cases, "prompt_version": a.prompt,
            "system_prompt": PROMPTS[a.prompt], "model_path": props.get("model_path"),
            "server_build": props.get("build_info"), "efforts": a.efforts, "reps": a.reps,
            "safety_reps": a.safety_reps}
    json.dump(meta, open(f"{out_dir}/meta.json", "w"), indent=1)

    # Interleave efforts (rep -> case -> effort) so the fanless Air's heat affects every effort level equally.
    SAFETY = {"emergency", "complaint", "medical"}
    todo = [(c, e, r) for r in range(a.reps + a.safety_reps) for c in cases for e in a.efforts
            if (r < a.reps or c["category"] in SAFETY) and (c["id"], e, r) not in done]
    try:
        urllib.request.urlopen(BASE + "/health", timeout=5)
    except Exception as ex:
        sys.exit(f"llama-server is not reachable at {BASE} ({ex}). Start it first.")
    print(f"{a.label}: {len(todo)} runs to do ({len(done)} already logged)")
    fails = 0
    runner = run_jais if a.mode == "jais" else run_chat
    t_start = time.time()
    for k, (c, e, r) in enumerate(todo, 1):
        try:
            res = runner(c["message"], e, seed=1000 + r, n_predict=a.n_predict, system=PROMPTS[a.prompt])
            fails = 0
        except Exception as ex:
            res = {"error": f"{type(ex).__name__}: {ex}"}
            fails += 1
            print(f"  error: {res['error']}")
            if fails >= 3:
                sys.exit("3 errors in a row — stopping. Check the server, then rerun the same command to resume.")
        rec = {"case": c["id"], "category": c["category"], "effort": e, "rep": r, "prompt": a.prompt,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **res}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        first = (res.get("calls") or [{}])[0].get("name", "—") if "error" not in res else "ERROR"
        eta = (time.time() - t_start) / k * (len(todo) - k) / 60
        print(f"[{k:>3}/{len(todo)}] {c['id']} {e:<6} r{r}  {res.get('wall_s', 0):>5}s  call={first:<20} eta {eta:4.0f} min")
        if a.show and "error" not in res:
            print("      think_open:", res.get("think_open"), "| think_close:", res.get("think_close"), "| stop:", res.get("stop"))
            print("      RAW:", (res.get("raw") or res.get("answer") or "")[-700:].replace("\n", " ⏎ "))
            print("      CALLS:", json.dumps(res.get("calls"), ensure_ascii=False), "| ANSWER:", (res.get("answer") or "")[:200])
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
