#!/usr/bin/env python3
"""
miqyas · summarise diag_*.json files from diag_raw.py

Usage:
    python3 scripts/diag_summary.py            # all diag files
    python3 scripts/diag_summary.py --prompt   # also check how tools appear in the prompt
"""
import glob
import json
import re
import sys

files = sorted(glob.glob("results/frontdesk/diag_*.json"))
show_prompt = "--prompt" in sys.argv

for fn in files:
    d = json.load(open(fn, encoding="utf-8"))
    toks = d["tokens"]
    text = "".join(t["piece"] for t in toks)
    # control-looking pieces, e.g. <|ifm|...|> or <ifm|...>, and whether each is ONE token or spelled out
    specials = [(t["id"], t["piece"]) for t in toks if "ifm" in t["piece"] or t["piece"].startswith("<")]
    tags = re.findall(r"</?\|?ifm\|[a-z_]+\|?>", text)
    tool_mentions = [n for n in ("check_availability", "book_appointment", "handoff_to_human") if n in text]
    print(f"\n### {fn}  effort={d['effort']}  tokens={len(toks)}  stop={d['stop_type']}")
    print("  tags in output     :", tags or "none")
    print("  single-token specials:", specials[:12] or "none")
    print("  tool names in output:", tool_mentions or "none")
    print("  answer start       :", re.sub(r"\s+", " ", re.sub(r"</?\|?ifm\|[^>]*>", "", text))[:160])

if show_prompt and files:
    p = json.load(open(files[-1], encoding="utf-8"))["prompt"]
    print("\n### Tools in the prompt?")
    for n in ("check_availability", "book_appointment", "handoff_to_human"):
        print(f"  {n:20} {'present' if n in p else 'MISSING'}  (occurrences: {p.count(n)})")
    i = p.find("check_availability")
    print("\n  context around first tool definition:\n ", p[max(0, i - 400): i + 300] if i >= 0 else "(not found)")
    print("\n  prompt control tags:", sorted(set(re.findall(r"<\|?/?ifm\|[a-z_]+\|?>", p))))
