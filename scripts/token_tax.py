#!/usr/bin/env python3
"""
miqyas · Week 4 — the Arabic token tax.

Counts tokens for the SAME FLORES+ sentences in English and seven Arabic
varieties, across several tokenizers. No model inference; runs on any laptop.

Usage (from ~/miqyas, venv active):
    python3 scripts/token_tax.py

Outputs:
    results/w4/per_sentence.csv   every sentence x variety x tokenizer count
    results/w4/summary.csv        one row per tokenizer x variety
    results/w4/summary.md         readable tables + environment
    data/tokenizers.json          data spine (the calculator reads this)
"""
import datetime
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus_raw" / "flores_plus"
OUT = ROOT / "results" / "w4"
SPINE = ROOT / "data" / "tokenizers.json"
GULF = ROOT / "corpus" / "gulf_v0.txt"   # optional, author-written
SPLITS = ["dev", "devtest"]
BOOTSTRAP = 2000
SEED = 42

# code, FLORES+ file stem, Arabic label, English label
VARIETIES = [
    ("eng", "eng_Latn", "الإنجليزية", "English"),
    ("msa", "arb_Arab", "الفصحى", "Modern Standard Arabic"),
    ("najdi", "ars_Arab", "النجدية", "Najdi"),
    ("mesopotamian", "acm_Arab", "العراقية", "Mesopotamian"),
    ("egyptian", "arz_Arab", "المصرية", "Egyptian"),
    ("levantine_n", "apc_Arab_nort3139", "الشامية الشمالية", "North Levantine"),
    ("levantine_s", "apc_Arab_sout3123", "الشامية الجنوبية", "South Levantine"),
    ("moroccan", "ary_Arab", "المغربية", "Moroccan"),
]
ARABIC = [v[0] for v in VARIETIES if v[0] != "eng"]

# id, kind, source, loader kwargs
TOKENIZERS = [
    ("o200k", "tiktoken", "o200k_base", {}),
    ("qwen3", "hf", "Qwen/Qwen3-4B", {}),
    ("llama3.2", "hf", "meta-llama/Llama-3.2-1B-Instruct", {}),
    ("gemma3", "hf", "google/gemma-3-1b-it", {}),
    # Tekken ships with a faulty pre-tokenizer regex; the flag fixes it.
    ("mistral-tekken", "hf", "mistralai/Mistral-Nemo-Instruct-2407", {"fix_mistral_regex": True}),
    ("allam", "hf", "humain-ai/ALLaM-7B-Instruct-preview", {}),
    ("jais", "hf", "inceptionai/jais-family-6p7b-chat", {}),
    ("jais2", "hf", "inception42/Jais-2-8B-Chat", {}),
    ("fanar", "hf", "QCRI/Fanar-1-9B-Instruct", {}),
]


# ---------------------------------------------------------------- corpus
def load_corpus():
    rows = []
    for split in SPLITS:
        for code, stem, _, _ in VARIETIES:
            path = CORPUS / split / f"{stem}.jsonl"
            if not path.exists():
                sys.exit(f"Missing corpus file: {path}")
            with open(path, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    if "text" not in r or "id" not in r:
                        sys.exit(f"Unexpected fields in {path}: {sorted(r)}")
                    rows.append({"split": split, "id": r["id"], "variety": code, "text": r["text"]})
    long = pd.DataFrame(rows)
    wide = long.pivot_table(index=["split", "id"], columns="variety", values="text", aggfunc="first")
    before = len(wide)
    wide = wide.dropna()  # keep only sentences present in every variety
    dropped = before - len(wide)
    wide = wide.reset_index().sort_values(["split", "id"]).reset_index(drop=True)
    return wide, dropped


def load_gulf():
    """Parse corpus/gulf_v0.txt. Blocks of:  # id / gulf: / msa: / en:"""
    if not GULF.exists():
        return None
    items, cur = [], None
    for ln, raw in enumerate(GULF.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if cur:
                items.append(cur)
            cur = {"id": line.lstrip("#").strip(), "_line": ln}
            continue
        key, sep, val = line.partition(":")
        key = key.strip().lower()
        if not sep or key not in ("gulf", "msa", "en") or cur is None:
            sys.exit(f"{GULF.name} line {ln}: expected '# id' or 'gulf: / msa: / en:' — got: {raw[:60]}")
        cur[key] = val.strip()
    if cur:
        items.append(cur)
    # blocks left completely blank (unfilled template slots) are ignored
    items = [it for it in items if any(it.get(k) for k in ("gulf", "msa", "en"))]
    for it in items:
        missing = [k for k in ("gulf", "msa", "en") if not it.get(k)]
        if missing:
            sys.exit(f"{GULF.name} item '{it['id']}' (line {it['_line']}) is missing: {', '.join(missing)}")
    ids = [it["id"] for it in items]
    if len(ids) != len(set(ids)):
        sys.exit(f"{GULF.name}: duplicate ids")
    return items


# ------------------------------------------------------------ tokenizers
def load_tokenizer(kind, source, kwargs):
    """Returns (count_fn(list_of_texts) -> list_of_ints, meta dict)."""
    if kind == "tiktoken":
        import tiktoken
        enc = tiktoken.get_encoding(source)

        def count(texts):
            return [len(t) for t in enc.encode_ordinary_batch(texts)]

        return count, {"vocab": enc.n_vocab, "revision": f"tiktoken {tiktoken.__version__}"}

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(source, **kwargs)
    revision = None
    try:
        from huggingface_hub import HfApi
        revision = HfApi().model_info(source).sha
    except Exception:
        pass

    def count(texts):
        # No BOS/EOS: we measure the text, not the chat wrapper.
        return [len(ids) for ids in tok(texts, add_special_tokens=False)["input_ids"]]

    return count, {"vocab": len(tok), "revision": revision}


def classify_error(e):
    m = str(e)
    if "gated" in m.lower() or "401" in m or "403" in m:
        return "gated — access not yet granted"
    if "trust_remote_code" in m:
        return "requires remote code — not enabled"
    return f"{type(e).__name__}: {m.splitlines()[0][:120] if m else '(no message)'}"


def md_table(df):
    """Markdown table without needing the 'tabulate' package."""
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        out.append("| " + " | ".join([str(idx)] + [str(v) for v in row.tolist()]) + " |")
    return "\n".join(out)


# ------------------------------------------------------------------ main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SPINE.parent.mkdir(parents=True, exist_ok=True)

    corpus, dropped = load_corpus()
    n = len(corpus)
    print(f"Corpus: {n} parallel sentences x {len(VARIETIES)} varieties ({dropped} dropped as incomplete)")

    per_sentence = corpus[["split", "id"]].copy()
    for code, _, _, _ in VARIETIES:
        per_sentence[f"{code}__words"] = corpus[code].str.split().str.len()
        per_sentence[f"{code}__chars"] = corpus[code].str.len()

    measured, skipped = [], []
    counters = {}
    for tid, kind, source, kwargs in TOKENIZERS:
        try:
            count, meta = load_tokenizer(kind, source, kwargs)
        except Exception as e:
            reason = classify_error(e)
            print(f"  SKIP  {tid:15} {reason}")
            skipped.append({"id": tid, "source": source, "status": "not_measured", "reason": reason})
            continue
        counters[tid] = count
        for code, _, _, _ in VARIETIES:
            per_sentence[f"{code}__{tid}"] = count(corpus[code].tolist())
        measured.append({"id": tid, "kind": kind, "source": source, "loader_kwargs": kwargs, **meta})
        print(f"  OK    {tid:15} vocab={meta['vocab']}")

    if not measured:
        sys.exit("No tokenizer could be loaded.")

    # One shared set of bootstrap resamples, so every CI uses the same draws.
    rng = np.random.default_rng(SEED)
    boot_idx = rng.integers(0, n, size=(BOOTSTRAP, n))
    split_mask = {s: (per_sentence["split"] == s).to_numpy() for s in SPLITS}

    summary = []
    for t in measured:
        tid = t["id"]
        eng = per_sentence[f"eng__{tid}"].to_numpy()
        eng_boot = eng[boot_idx].sum(axis=1)
        for code, _, ar_label, en_label in VARIETIES:
            tok = per_sentence[f"{code}__{tid}"].to_numpy()
            words = per_sentence[f"{code}__words"].to_numpy()
            ratio = tok.sum() / eng.sum()
            boot = tok[boot_idx].sum(axis=1) / eng_boot
            row = {
                "tokenizer": tid,
                "variety": code,
                "label_ar": ar_label,
                "label_en": en_label,
                "sentences": n,
                "tokens": int(tok.sum()),
                "words": int(words.sum()),
                "tokens_per_word": round(tok.sum() / words.sum(), 3),
                "ratio_vs_eng": round(ratio, 3),
                "ci95_low": round(float(np.percentile(boot, 2.5)), 3),
                "ci95_high": round(float(np.percentile(boot, 97.5)), 3),
                "median_sentence_ratio": round(float(np.median(tok / np.maximum(eng, 1))), 3),
            }
            for s in SPLITS:
                m = split_mask[s]
                row[f"ratio_{s}"] = round(tok[m].sum() / eng[m].sum(), 3)
            summary.append(row)

    summary = pd.DataFrame(summary)
    per_sentence.to_csv(OUT / "per_sentence.csv", index=False)
    summary.to_csv(OUT / "summary.csv", index=False)

    # ------------------------------------------------ custom Gulf set
    gulf = load_gulf()
    gulf_rows = []
    if gulf:
        g = len(gulf)
        print(f"\nGulf set: {g} items (gulf / msa / en)")
        if g < 20:
            print(f"  note: only {g} items — confidence intervals will be wide")
        g_idx = np.random.default_rng(SEED).integers(0, g, size=(BOOTSTRAP, g))
        g_sent = pd.DataFrame({"id": [it["id"] for it in gulf]})
        for k in ("gulf", "msa", "en"):
            g_sent[f"{k}__words"] = [len(it[k].split()) for it in gulf]
        for t in measured:
            tid = t["id"]
            c = {k: np.array(counters[tid]([it[k] for it in gulf])) for k in ("gulf", "msa", "en")}
            for k in c:
                g_sent[f"{k}__{tid}"] = c[k]
            row = {"tokenizer": tid, "items": g}
            for num, den in (("gulf", "en"), ("msa", "en"), ("gulf", "msa")):
                boot = c[num][g_idx].sum(axis=1) / c[den][g_idx].sum(axis=1)
                key = f"{num}_vs_{den}"
                row[key] = round(c[num].sum() / c[den].sum(), 3)
                row[f"{key}_ci95"] = f"{np.percentile(boot, 2.5):.3f}–{np.percentile(boot, 97.5):.3f}"
            gulf_rows.append(row)
        gulf_df = pd.DataFrame(gulf_rows).set_index("tokenizer")
        g_sent.to_csv(OUT / "gulf_per_item.csv", index=False)
        gulf_df.to_csv(OUT / "gulf_summary.csv")
        print("\nGulf set — gulf vs MSA is the dialect effect on identical content:\n")
        print(gulf_df[["gulf_vs_en", "msa_vs_en", "gulf_vs_msa", "gulf_vs_msa_ci95"]].to_string())

    # ---------------------------------------------------------- readable
    order = [t["id"] for t in measured]
    ratio = summary.pivot(index="tokenizer", columns="variety", values="ratio_vs_eng").loc[order, ["eng"] + ARABIC]
    tpw = summary.pivot(index="tokenizer", columns="variety", values="tokens_per_word").loc[order, ["eng"] + ARABIC]
    msa = summary[summary.variety == "msa"].set_index("tokenizer").loc[order]

    import transformers, tiktoken  # noqa: E401  (versions for the record)
    env = {
        "date": datetime.date.today().isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "transformers": transformers.__version__,
        "tiktoken": tiktoken.__version__,
    }

    md = [
        "# Week 4 — Arabic token tax",
        "",
        f"FLORES+ dev + devtest · {n} parallel sentences · {len(measured)} tokenizers · no special tokens",
        "",
        "## Token ratio vs English (same sentences, same tokenizer)",
        "",
        md_table(ratio),
        "",
        "## MSA ratio with 95% bootstrap CI and split stability",
        "",
        md_table(msa[["ratio_vs_eng", "ci95_low", "ci95_high", "ratio_dev", "ratio_devtest", "median_sentence_ratio"]]),
        "",
        "## Tokens per whitespace word (reference only — Arabic words carry clitics)",
        "",
        md_table(tpw),
        "",
        "## Not measured",
        "",
    ]
    md += [f"- {s['id']} ({s['source']}): {s['reason']}" for s in skipped] or ["- none"]
    if gulf_rows:
        md += ["", f"## Author-written Gulf set ({len(gulf)} items, same meaning in Gulf, MSA, English)", "",
               "AI-drafted (Claude), reviewed and edited by a native Gulf speaker; not independently sourced. gulf_vs_msa isolates the dialect effect.", "",
               md_table(gulf_df)]
    md += ["", "## Environment", "", "```", json.dumps(env, indent=2), "```"]
    (OUT / "summary.md").write_text("\n".join(md), encoding="utf-8")

    # ------------------------------------------------------- data spine
    spine = {
        "version": "0.1",
        "generated": env["date"],
        "method": {
            "corpus": "FLORES+ (openlanguagedata/flores_plus), dev + devtest, CC BY-SA 4.0",
            "sentences": n,
            "metric": "sum(Arabic tokens) / sum(English tokens) over identical parallel sentences",
            "ci": f"95% percentile bootstrap over sentences, {BOOTSTRAP} resamples, seed {SEED}",
            "special_tokens": "excluded",
            "environment": env,
        },
        "varieties": [{"id": c, "flores": s, "label_ar": a, "label_en": e} for c, s, a, e in VARIETIES],
        "tokenizers": [],
    }
    for t in measured:
        rows = summary[summary.tokenizer == t["id"]].set_index("variety")
        spine["tokenizers"].append({
            **{k: t[k] for k in ("id", "source", "vocab", "revision")},
            "status": "measured",
            "ratios": {
                v: {
                    "ratio": float(rows.loc[v, "ratio_vs_eng"]),
                    "ci95": [float(rows.loc[v, "ci95_low"]), float(rows.loc[v, "ci95_high"])],
                    "tokens_per_word": float(rows.loc[v, "tokens_per_word"]),
                }
                for v in ["eng"] + ARABIC
            },
        })
    if gulf_rows:
        spine["custom_sets"] = {"gulf_v0": {
            "source": "drafted with AI assistance (Claude), reviewed and edited by a native Gulf speaker; corpus/gulf_v0.txt, MIT",
            "items": len(gulf),
            "results": {r["tokenizer"]: {k: v for k, v in r.items() if k not in ("tokenizer", "items")} for r in gulf_rows},
        }}
    spine["tokenizers"] += skipped  # rendered as «لم يُقَس بعد»
    SPINE.write_text(json.dumps(spine, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nToken ratio vs English:\n")
    print(ratio.to_string())
    print(f"\nWrote {OUT}/per_sentence.csv, summary.csv, summary.md and {SPINE}")


if __name__ == "__main__":
    main()
