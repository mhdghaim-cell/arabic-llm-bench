#!/usr/bin/env python3
"""
miqyas · front-desk v2 runner — whole conversations with a scripted patient and a live clinic.

For every episode: the patient sends turn 1; the model may call tools (the clinic answers
from clinic.py) as many times as it needs, then replies; the patient sends the next scripted
turn; and so on. A handoff to a human ends the episode after the model's reply.

Usage (llama-server on :8080, from the repo root):
  python3 scripts/run_v2.py --label jais3-3.7b-q4 --mode jais --arms base table tool --efforts high
  python3 scripts/run_v2.py --label qwen3-4b-q4  --mode chat --arms base table tool --efforts on
  python3 scripts/run_v2.py --label oracle --mode oracle --arms base table tool    # harness self-test, no server

Output: results/frontdesk_v2/<label>/runs.jsonl  (one line per episode x arm x effort x rep), resumable.
"""
import argparse
import json
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clinic import Clinic, system_prompt, tools_for  # noqa: E402

BASE = "http://localhost:8080"
MAX_STEPS = 8            # tool rounds allowed before the model must answer the patient
SAFETY = {"emergency", "complaint", "medical"}

# Each vendor's own recommended sampling (model cards). Jais 3: Arabic thinking settings.
SAMPLING = {
    "jais": {"temperature": 0.7, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 0.0, "repeat_penalty": 1.0},
    "qwen-think": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "repeat_penalty": 1.0},
    "qwen-nothink": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "repeat_penalty": 1.0},
    # ALLaM-7B-Instruct-preview model card (example generation settings), added for qt-01
    "allam": {"temperature": 0.6, "top_p": 0.95, "top_k": 50, "min_p": 0.0, "presence_penalty": 0.0, "repeat_penalty": 1.0},
    # Falcon-H1 (TII README: temperature 0.1; other samplers neutral), added for qt-02
    "falcon-h1": {"temperature": 0.1, "top_p": 1.0, "top_k": 0, "min_p": 0.0, "presence_penalty": 0.0, "repeat_penalty": 1.0},
}
SAMPLING_OVERRIDE = None   # set by --sampling; None keeps the original Job Trial #1 behaviour


# ------------------------------------------------------------------ llama-server helpers
def post(path, body, timeout=1800):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


_piece_cache = {}
_SPECIAL = re.compile(r"^<\|?/?ifm\|[a-z_]+\|?>$")


def _piece(i):
    if i not in _piece_cache:
        _piece_cache[i] = post("/detokenize", {"tokens": [i]}).get("content", "")
    return _piece_cache[i]


def detok(ids):
    """Ordinary tokens decoded together (keeps multi-byte UTF-8 intact); control tokens one by one."""
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
    opened = (re.findall(r"<ifm\|(think[a-z_]*)>\s*$", prompt_tail) or [None])[0]
    m = THINK_CLOSE.search(text)
    if opened and m:
        reasoning, rest, closed = text[:m.start()], text[m.end():], m.group(1)
    elif opened:
        reasoning, rest, closed = text, "", None
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


# ------------------------------------------------------------------ policies
class JaisPolicy:
    """Jais 3 via its own chat template + raw completion; we parse its control tokens ourselves."""

    def __init__(self, effort, n_predict):
        self.effort, self.n_predict = effort, n_predict

    def step(self, messages, tools, seed, ctx):
        prompt = post("/apply-template", {"messages": messages, "tools": tools,
                                          "chat_template_kwargs": {"reasoning_effort": self.effort}})["prompt"]
        t0 = time.time()
        r = post("/completion", {"prompt": prompt, "n_predict": self.n_predict, "seed": seed, "return_tokens": True,
                                 "cache_prompt": True, **SAMPLING["jais"]})
        wall = time.time() - t0
        text = detok(r.get("tokens", []))
        p = parse_jais(prompt[-60:], text)
        tm = r.get("timings", {})
        return {**p, "raw": text, "wall_s": round(wall, 3), "stop": r.get("stop_type"),
                "prompt_n": tm.get("prompt_n"), "cached_n": tm.get("cache_n", r.get("tokens_cached")),
                "gen_n": len(r.get("tokens", [])), "timings": tm}


class ChatPolicy:
    """Any other model via /v1/chat/completions (llama.cpp parses its tool calls). effort: on | off."""

    def __init__(self, effort, n_predict):
        self.effort, self.n_predict = effort, n_predict
        self.sampling = SAMPLING[SAMPLING_OVERRIDE] if SAMPLING_OVERRIDE else SAMPLING["qwen-think" if effort == "on" else "qwen-nothink"]

    def step(self, messages, tools, seed, ctx):
        body = {"messages": messages, "tools": tools, "max_tokens": self.n_predict, "seed": seed, **self.sampling,
                "chat_template_kwargs": {"enable_thinking": self.effort == "on"}}
        t0 = time.time()
        try:
            r = post("/v1/chat/completions", body)
        except urllib.error.HTTPError as ex:
            msg = ex.read().decode("utf-8", "ignore")
            if "context" in msg.lower():   # conversation no longer fits the model's window: a failure, not a crash
                out = _fake()
                out.update(stop="context", wall_s=round(time.time() - t0, 3), raw=msg[:300])
                return out
            raise
        wall = time.time() - t0
        ch = r["choices"][0]
        m = ch["message"]
        calls = []
        for c in m.get("tool_calls") or []:
            try:
                args = json.loads(c["function"]["arguments"])
            except Exception:
                args = {"_unparsed": c["function"]["arguments"]}
            calls.append({"name": c["function"]["name"], "args": args, "id": c.get("id")})
        tm = r.get("timings", {})
        return {"reasoning": m.get("reasoning_content") or "", "calls": calls, "answer": (m.get("content") or "").strip(),
                "think_open": None, "think_close": None, "raw": None, "wall_s": round(wall, 3),
                "stop": "limit" if ch.get("finish_reason") == "length" else ch.get("finish_reason"),
                "prompt_n": tm.get("prompt_n"), "cached_n": tm.get("cache_n"),
                "gen_n": r["usage"]["completion_tokens"], "timings": tm}


# Prompted-JSON adapter (qt-01, amendment 2): for models whose chat template has no tool syntax (ALLaM).
# The tools and a two-form JSON reply format go in the system prompt; the reply is constrained to that JSON
# (llama.cpp json_schema grammar, tool arguments checked against each tool's own schema, the same way llama.cpp
# constrains native tool calls); tool results return as a user message. Roles always alternate.
PROMPTED_PROTOCOL = """

## Tools
You can use these tools:
{tools}

Every message you write must be exactly one JSON object, in one of two forms:
1. To use tools: {{"tool_calls": [{{"name": "<tool name>", "arguments": {{...}}}}]}}
2. To write to the patient: {{"response": "<your message to the patient>"}}
Tool results come back to you in a message that starts with "TOOL RESULTS:". After reading them, use more tools or write to the patient."""


def prompted_schema(tools):
    items = [{"type": "object", "properties": {"name": {"const": t["function"]["name"]},
                                               "arguments": t["function"]["parameters"]},
              "required": ["name", "arguments"], "additionalProperties": False} for t in tools]
    return {"anyOf": [
        {"type": "object", "properties": {"tool_calls": {"type": "array", "items": {"anyOf": items}, "minItems": 1, "maxItems": 4}},
         "required": ["tool_calls"], "additionalProperties": False},
        {"type": "object", "properties": {"response": {"type": "string"}},
         "required": ["response"], "additionalProperties": False}]}


def prompted_messages(messages, tools):
    spec = json.dumps([{"name": t["function"]["name"], "description": t["function"]["description"],
                        "parameters": t["function"]["parameters"]} for t in tools], ensure_ascii=False, indent=1)
    names, out = {}, []
    for m in messages:
        if m["role"] == "system":
            role, content = "system", m["content"] + PROMPTED_PROTOCOL.format(tools=spec)
        elif m["role"] == "user":
            role, content = "user", m["content"]
        elif m["role"] == "assistant":
            role = "assistant"
            if m.get("tool_calls"):
                tc = []
                for c in m["tool_calls"]:
                    names[c["id"]] = c["function"]["name"]
                    try:
                        args = json.loads(c["function"]["arguments"])
                    except Exception:
                        args = {}
                    tc.append({"name": c["function"]["name"], "arguments": args})
                content = json.dumps({"tool_calls": tc}, ensure_ascii=False)
            else:
                content = json.dumps({"response": m.get("content") or ""}, ensure_ascii=False)
        elif m["role"] == "tool":
            role = "user"
            content = "TOOL RESULTS:\n" + json.dumps({"name": names.get(m["tool_call_id"], "?"),
                                                       "result": json.loads(m["content"])}, ensure_ascii=False)
        else:
            continue
        if out and out[-1]["role"] == role and role != "system":     # keep user/assistant strictly alternating
            out[-1]["content"] += "\n" + content
        else:
            out.append({"role": role, "content": content})
    return out


def parse_prompted(text):
    try:
        o = json.loads(text)
    except Exception:
        return [], text.strip(), False
    if isinstance(o, dict) and isinstance(o.get("tool_calls"), list):
        return [{"name": c.get("name"), "args": c.get("arguments") if isinstance(c.get("arguments"), dict) else {}}
                for c in o["tool_calls"] if isinstance(c, dict)], "", True
    if isinstance(o, dict) and "response" in o:
        return [], str(o["response"]).strip(), True
    return [], text.strip(), False


class PromptedPolicy(ChatPolicy):
    """Chat model without a tool syntax: tools described in the prompt, JSON reply constrained by grammar."""

    def step(self, messages, tools, seed, ctx):
        body = {"messages": prompted_messages(messages, tools), "max_tokens": self.n_predict, "seed": seed, **self.sampling,
                "chat_template_kwargs": {"enable_thinking": self.effort == "on"},   # ignored by templates without a thinking switch (ALLaM)
                "response_format": {"type": "json_schema", "json_schema": {"name": "turn", "schema": prompted_schema(tools)}}}
        t0 = time.time()
        try:
            r = post("/v1/chat/completions", body)
        except urllib.error.HTTPError as ex:
            msg = ex.read().decode("utf-8", "ignore")
            if "context" in msg.lower():
                out = _fake()
                out.update(stop="context", wall_s=round(time.time() - t0, 3), raw=msg[:300])
                return out
            raise
        wall = time.time() - t0
        ch = r["choices"][0]
        text = ch["message"].get("content") or ""
        calls, answer, ok = parse_prompted(text)
        tm = r.get("timings", {})
        return {"reasoning": "", "calls": calls, "answer": answer, "think_open": None, "think_close": None,
                "raw": text, "parsed": ok, "wall_s": round(wall, 3),
                "stop": "limit" if ch.get("finish_reason") == "length" else ch.get("finish_reason"),
                "prompt_n": tm.get("prompt_n"), "cached_n": tm.get("cache_n"),
                "gen_n": r["usage"]["completion_tokens"], "timings": tm}


class OraclePolicy:
    """Replays an episode's oracle (what a correct receptionist does). Used to validate harness + scorer."""

    def __init__(self, episode, arm):
        self.ep, self.arm = episode, arm

    def step(self, messages, tools, seed, ctx):
        k, s = ctx["turn"], ctx["step_in_turn"]
        spec = self.ep["oracle"][k] if k < len(self.ep["oracle"]) else {"calls": [], "reply": "تمام."}
        calls = [{"name": n, "args": a} for n, a in spec["calls"] if self.arm == "tool" or n != "find_date"]
        if s == 0 and calls:
            return _fake(calls=calls)
        reply = spec["reply"] or auto_reply(ctx["turn_events"])
        return _fake(answer=reply)


def _fake(calls=(), answer="", reasoning=""):
    return {"reasoning": reasoning, "calls": list(calls), "answer": answer, "think_open": None, "think_close": None,
            "raw": None, "wall_s": 0.0, "stop": "eos", "prompt_n": 0, "cached_n": 0, "gen_n": 0, "timings": {}}


def auto_reply(events):
    """The oracle's reply, written from the last meaningful tool result of the turn."""
    for e in reversed(events):
        r, t = e["result"], e["tool"]
        if t == "book_appointment" and r.get("ok"):
            return f"تم الحجز ✅ {r['date']} الساعة {r['time']}، باسم {r['patient_name']}."
        if t == "cancel_appointment" and r.get("ok"):
            return "تم إلغاء الموعد."
        if t == "check_availability" and "error" not in r:
            if not r.get("open"):
                return "العيادة مسكرة ذاك اليوم. تبي أشوف لك يوم ثاني؟"
            if not r["free_times"]:
                return "السموحة، ما في أوقات فاضية ذاك اليوم. تبي أشوف لك يوم ثاني؟"
            return "الأوقات الفاضية: " + "، ".join(r["free_times"]) + ". أي وقت يناسبك؟ وشو الاسم الكريم؟"
    return "تمام."


# ------------------------------------------------------------------ one episode
def run_episode(ep, arm, policy, rep):
    clinic = Clinic(ep, arm=arm)
    tools = tools_for(arm)
    messages = [{"role": "system", "content": system_prompt(arm)}]
    steps, replies, turns_log = [], [], []
    flags = {"cap": False, "loop": False}
    n_call = 0
    g = 0                                            # global step counter (seeds)
    for k, utext in enumerate(ep["turns"]):
        messages.append({"role": "user", "content": utext})
        turn_events, turn_wall, s = [], 0.0, 0
        while True:
            if s >= MAX_STEPS:
                flags["loop"] = True
                break
            out = policy.step(messages, tools, seed=1000 + 100 * rep + g,
                              ctx={"turn": k, "step_in_turn": s, "turn_events": turn_events})
            g += 1
            turn_wall += out["wall_s"]
            steps.append({"turn": k, "step": s, **{x: out.get(x) for x in
                          ("wall_s", "stop", "prompt_n", "cached_n", "gen_n", "think_open", "think_close", "reasoning", "raw", "parsed")},
                          "calls": out["calls"], "answer": out["answer"]})
            if out.get("stop") in ("limit", "length", "context"):
                flags["cap"] = True
                if out.get("stop") == "context":
                    flags["context"] = True
                break
            amsg = {"role": "assistant", "content": out["answer"]}
            if out["calls"]:
                tcs = []
                for c in out["calls"]:
                    n_call += 1
                    cid = c.get("id") or f"call_{n_call}"
                    c["id"] = cid
                    tcs.append({"id": cid, "type": "function",
                                "function": {"name": c["name"], "arguments": json.dumps(c["args"], ensure_ascii=False)}})
                amsg["tool_calls"] = tcs
            messages.append(amsg)
            if out["answer"]:
                replies.append({"turn": k, "text": out["answer"]})
            if not out["calls"]:
                break
            for c in out["calls"]:
                res = clinic.call(c["name"], c["args"])
                clinic.events[-1]["turn"] = k
                turn_events.append(clinic.events[-1])
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(res, ensure_ascii=False)})
            s += 1
        turns_log.append({"turn": k, "patient": utext, "wall_s": round(turn_wall, 3), "steps": s + 1,
                          "replied": any(r["turn"] == k and r["text"].strip() for r in replies)})
        if flags["cap"] or flags["loop"] or clinic.handoffs:
            break                                     # customer gave up / human took over
    final = {"added": [b for b in clinic.appointments.values() if b["booking_id"] not in clinic.initial_ids],
             "removed": sorted(clinic.initial_ids - set(clinic.appointments)),
             "handoffs": [{"reason": e["args"].get("reason"), "summary": e["args"].get("summary"), "turn": e["turn"]}
                          for e in clinic.events if e["tool"] == "handoff_to_human" and e["result"].get("ok")]}
    return {"turns": turns_log, "replies": replies, "events": clinic.events, "final": final, "flags": flags,
            "steps": steps, "messages": messages}


# ------------------------------------------------------------------ main
def current_model():
    try:
        return json.load(urllib.request.urlopen(BASE + "/props", timeout=10)).get("model_path")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--mode", choices=["jais", "chat", "prompted", "oracle"], required=True)
    ap.add_argument("--arms", nargs="+", default=["base", "table", "tool"], choices=["base", "table", "tool"])
    ap.add_argument("--efforts", nargs="+", default=["high"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--safety-reps", type=int, default=2, help="extra reps for emergency/complaint/medical episodes")
    ap.add_argument("--split", choices=["test", "dev", "all"], default="test")
    ap.add_argument("--only", nargs="*", help="only these episode ids")
    ap.add_argument("--episodes", default="corpus/frontdesk_v2.jsonl")
    ap.add_argument("--n-predict", type=int, default=8192)
    ap.add_argument("--out-root", default="results/frontdesk_v2")
    ap.add_argument("--sampling", choices=sorted(SAMPLING), help="force one sampling preset for chat mode (default: Job Trial #1 behaviour)")
    a = ap.parse_args()
    global SAMPLING_OVERRIDE
    SAMPLING_OVERRIDE = a.sampling

    eps = [json.loads(l) for l in open(a.episodes, encoding="utf-8") if l.strip()]
    eps = [e for e in eps if a.split == "all" or e["split"] == a.split]
    if a.only:
        eps = [e for e in eps if e["id"] in a.only]
    out_dir = f"{a.out_root}/{a.label}"
    os.makedirs(out_dir, exist_ok=True)
    out = f"{out_dir}/runs.jsonl"
    done = set()
    if os.path.exists(out):
        for l in open(out, encoding="utf-8"):
            d = json.loads(l)
            if "error" not in d:
                done.add((d["episode"], d["arm"], d["effort"], d["rep"]))

    model_path = None
    if a.mode != "oracle":
        try:
            urllib.request.urlopen(BASE + "/health", timeout=5)
        except Exception as ex:
            sys.exit(f"llama-server is not reachable at {BASE} ({ex}). Start it first.")
        props = json.load(urllib.request.urlopen(BASE + "/props", timeout=10))
        model_path = props.get("model_path")
    meta = {"label": a.label, "mode": a.mode, "machine": platform.platform(), "model_path": model_path,
            "episodes_file": a.episodes, "split": a.split, "arms": a.arms, "efforts": a.efforts, "reps": a.reps,
            "safety_reps": a.safety_reps, "n_predict": a.n_predict, "max_steps": MAX_STEPS,
            "sampling": SAMPLING, "system_prompts": {arm: system_prompt(arm) for arm in a.arms},
            "adapter": ({"name": "prompted-json", "protocol": PROMPTED_PROTOCOL} if a.mode == "prompted" else None)}
    json.dump(meta, open(f"{out_dir}/meta.json", "w"), ensure_ascii=False, indent=1)

    # rep -> episode -> arm -> effort: every condition sees the same thermal / load history
    todo = [(e, arm, eff, r) for r in range(a.reps + a.safety_reps) for e in eps for arm in a.arms for eff in a.efforts
            if (r < a.reps or e["category"] in SAFETY) and (e["id"], arm, eff, r) not in done]
    print(f"{a.label}: {len(todo)} episode runs to do ({len(done)} already logged)")
    fails, t0 = 0, time.time()
    for i, (e, arm, eff, r) in enumerate(todo, 1):
        if a.mode != "oracle" and current_model() != model_path:
            sys.exit(f"STOP: the server's model changed to {current_model()} (expected {model_path}).")
        policy = (OraclePolicy(e, arm) if a.mode == "oracle" else
                  JaisPolicy(eff, a.n_predict) if a.mode == "jais" else
                  PromptedPolicy(eff, a.n_predict) if a.mode == "prompted" else ChatPolicy(eff, a.n_predict))
        try:
            res = run_episode(e, arm, policy, r)
            fails = 0
        except Exception as ex:
            res = {"error": f"{type(ex).__name__}: {ex}"}
            fails += 1
            print("  error:", res["error"])
            if fails >= 3:
                sys.exit("3 errors in a row — stopping. Check the server, then rerun the same command to resume.")
        rec = {"episode": e["id"], "category": e["category"], "arm": arm, "effort": eff, "rep": r,
               "model": model_path, "label": a.label, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **res}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if "error" not in res:
            w = sum(t["wall_s"] for t in res["turns"])
            eta = (time.time() - t0) / i * (len(todo) - i) / 60
            print(f"[{i:>4}/{len(todo)}] {e['id']} {arm:<5} {eff:<4} r{r} {w:6.1f}s "
                  f"booked={len(res['final']['added'])} cancelled={len(res['final']['removed'])} "
                  f"handoff={len(res['final']['handoffs'])} {'CAP' if res['flags']['cap'] else ''}"
                  f"{'LOOP' if res['flags']['loop'] else ''}  eta {eta:4.0f} min")
    print("done ->", out)


if __name__ == "__main__":
    main()
