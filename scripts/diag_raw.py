#!/usr/bin/env python3
"""
miqyas · diagnose a missing tool call — show every token the model generated,
including special (control) tokens that the chat endpoint hides.

Usage (llama-server running on :8080):
    python3 scripts/diag_raw.py "<message>" [low|medium|high]

Uses the same system prompt and tools as try_tools.py.
Output also saved to results/frontdesk/diag_<timestamp>.json
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from try_tools import SYSTEM, TOOLS  # noqa: E402

BASE = "http://localhost:8080"


def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


def main():
    msg = sys.argv[1]
    effort = sys.argv[2] if len(sys.argv) > 2 else "medium"
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}]

    # 1. The exact prompt the server builds from the chat template.
    prompt = post("/apply-template", {"messages": messages, "tools": TOOLS,
                                      "chat_template_kwargs": {"reasoning_effort": effort}})["prompt"]

    # 2. Raw completion on that prompt, keeping the token ids.
    r = post("/completion", {"prompt": prompt, "n_predict": 2048, "temperature": 0.7, "top_p": 0.95,
                             "top_k": 20, "return_tokens": True, "cache_prompt": True})
    ids = r.get("tokens", [])

    # 3. Turn each id back into its text piece, special tokens included.
    pieces = []
    for i in ids:
        try:
            p = post("/detokenize", {"tokens": [i]}).get("content", "")
        except Exception:
            p = "?"
        pieces.append(p)

    print("== PROMPT TAIL (last 600 chars — shows how tools and effort were injected) ==")
    print(prompt[-600:])
    print(f"\n== GENERATED: {len(ids)} tokens | stop_type={r.get('stop_type')} | stopping_word={r.get('stopping_word')!r} ==")
    print(r.get("content"))
    print("\n== LAST 40 TOKENS (id → piece) ==")
    for i, p in list(zip(ids, pieces))[-40:]:
        print(f"{i:>7}  {p!r}")

    os.makedirs("results/frontdesk", exist_ok=True)
    out = f"results/frontdesk/diag_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"msg": msg, "effort": effort, "prompt": prompt, "content": r.get("content"),
                   "stop_type": r.get("stop_type"), "stopping_word": r.get("stopping_word"),
                   "tokens": [{"id": i, "piece": p} for i, p in zip(ids, pieces)]},
                  f, ensure_ascii=False, indent=1)
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
