#!/usr/bin/env python3
"""
miqyas · adds the display fields the site needs to data/tokenizers.json.

scripts/token_tax.py writes the MEASUREMENTS (ratios per variety, CIs, tokens per word).
This script adds, without touching any measured number:
  - updated, default_tokenizer           (page headers, calculator default)
  - per tokenizer: name, provider, license, hf_model (+note)   (labels, playground loading)
  - per tokenizer: ratio / ci95 / arabic_tokens_per_word / english_tokens_per_word
    = the MSA row copied to the top level, so the calculator and playground keep working.
Run after every token_tax.py run, then `npm run build`:
    python3 scripts/publish_tokenizers.py && npm run build
"""
import json
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "data/tokenizers.json"

DISPLAY = {
    # id: (name, provider, license of the model whose tokenizer this is, hf repo loadable in the browser or None, note)
    "o200k": ("o200k (GPT-4o)", "OpenAI", "proprietary (tokenizer public via tiktoken, MIT)", "Xenova/gpt-4o", None),
    "qwen3": ("Qwen3", "Alibaba", "Apache 2.0", "Qwen/Qwen3-4B", None),
    "llama3.2": ("Llama 3.2", "Meta", "Llama 3.2 Community License", "Xenova/llama-3-tokenizer",
                 "Llama 3.2 shares the Llama 3 tokenizer (128,256 tokens); the official repo is gated, so the browser loads a public mirror."),
    "gemma3": ("Gemma 3", "Google", "Gemma Terms of Use", None, "gated repo; measured locally, not loadable in the browser"),
    "mistral-tekken": ("Mistral Tekken", "Mistral AI", "Apache 2.0", "mistralai/Mistral-Nemo-Instruct-2407", None),
    "allam": ("ALLaM", "HUMAIN / SDAIA", "ALLaM license (gated)", None, "gated repo; measured locally, not loadable in the browser"),
    "jais": ("Jais (family 6.7B)", "Inception / G42", "Apache 2.0 (gated repo)", "derek-thomas/jais-13b-chat-hf",
             "official repo is gated; the browser loads a community mirror with the same 84,992-token vocabulary"),
    "jais2": ("Jais 2", "Inception", "gated repo", None, "gated repo; measured locally, not loadable in the browser"),
    "jais3": ("Jais 3 (3.7B–375B)", "MBZUAI IFM / Inception", "Apache 2.0", "IFM/Jais-3-7B-FP8", None),
    "jais3-0.9b": ("Jais 3 0.9B", "MBZUAI IFM / Inception", "Apache 2.0", "IFM/Jais-3-0.9B-MLX-bf16", None),
    "fanar": ("Fanar", "QCRI", "gated repo", None, "gated repo; measured locally, not loadable in the browser"),
}


def main():
    d = json.load(open(PATH, encoding="utf-8"))
    d["updated"] = d.get("generated")
    d.setdefault("default_tokenizer", "o200k")
    d["note"] = ("ratio = مجموع رموز النص العربي ÷ مجموع رموز النص الإنجليزي على الجمل المتوازية نفسها (FLORES+). "
                 "الحقول العلوية ratio/ci95/tokens_per_word هي صف الفصحى (msa) منسوخًا لتوافق الصفحات؛ التفاصيل لكل لهجة في ratios.")
    for t in d["tokenizers"]:
        name, provider, lic, hf, note = DISPLAY.get(t["id"], (t["id"], None, None, None, None))
        t["name"], t["provider"], t["license"] = name, provider, lic
        t["hf_model"] = hf
        if note:
            t["hf_model_note"] = note
        msa, eng = t["ratios"].get("msa"), t["ratios"].get("eng")
        if msa:
            t["ratio"], t["ci95"] = msa["ratio"], msa["ci95"]
            t["arabic_tokens_per_word"] = msa["tokens_per_word"]
        if eng:
            t["english_tokens_per_word"] = eng["tokens_per_word"]
    unknown = [t["id"] for t in d["tokenizers"] if t["id"] not in DISPLAY]
    if unknown:
        print("WARNING: no display entry for", unknown, "(add it to DISPLAY)")
    json.dump(d, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{PATH}: {len(d['tokenizers'])} tokenizers, updated {d['updated']}, "
          f"{sum(1 for t in d['tokenizers'] if t['hf_model'])} loadable in the browser")


if __name__ == "__main__":
    main()
