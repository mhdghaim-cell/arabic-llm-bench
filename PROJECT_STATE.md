# مقياس — Project State

**Last updated:** 2026-08-19, end of Week 1
**Purpose:** everything a new conversation needs to pick this up mid-stream without re-explaining. Read this first.

---

## What this project is

A 12-week program producing **original measurements** of how locally-run AI models handle Arabic, published publicly in Arabic on X and in English on LinkedIn, with all data open on GitHub.

**The strategic premise:** translated tutorials are commodity. Nobody has measured Arabic-specific behaviour — tokenizer efficiency, quantization damage, dialect handling, retrieval accuracy. That data doesn't exist in any language. That gap is the entire differentiation.

**Three compounding assets** come out of it:
1. **المسرد** (glossary) — Arabic terminology for local inference. Whoever fixes the vocabulary becomes the reference.
2. **المعيار** (benchmark) — open Arabic eval set, community-contributable.
3. **الحاسبة** (calculator) — local-vs-API TCO, calibrated on Arabic token ratios.

---

## Non-negotiable rules

1. **Never post without an original measurement.** No translated tutorials.
2. **Always publish the command, model version, and hardware.** Reproducibility is the moat.
3. **Publish results that contradict expectations.** Explicitly.
4. **Correct publicly and fast**, crediting whoever caught it.
5. **Never invent a number.** Unmeasured values render as «لم يُقَس بعد», never a plausible-looking placeholder.
6. **Disclose the rented machine.** Two-tier results, always labelled. Never present M4 numbers as laptop numbers.

---

## Hardware

**Machine A** — MacBook Air (Retina, 13-inch, 2020)
1.2 GHz Quad-Core Intel Core i7 (Ice Lake) · Intel Iris Plus 1536 MB (unused, CPU-only) · 8 GB LPDDR4X 3733 MHz · macOS Sequoia 15.7.7 · Ollama 0.32.11

Real model budget is ~4–4.5 GB after macOS overhead. Ceiling is 3B–4B at Q4. Fanless chassis, so sustained clocks are thermally limited.

**Machine B** — Mac mini M4, rented from Macly at $14.99/day
Apple M4 · 16 GB unified · macOS 26.6.1 · Ollama 0.32.14 · Metal backend
IP at time of writing: 45.74.245.11 · SSH works · **Apple Screen Sharing rejects the host** ("software appears incompatible") — needs RealVNC or similar for GUI access.

**Standard methodology line for posts:**
`MacBook Air 2020 · Intel i7 1.2GHz · 8GB · macOS 15.7.7 · Ollama CPU`

---

## Measurement method (frozen — do not change mid-program)

**Timing prompt is P5 and only P5.** Formal-writing task, produces a predictable 80–120 tokens, keeps speed comparable. P2 varies too widely in output length.

**Parameters, identical on every run:**
```json
{"num_predict": 300, "temperature": 0.7, "seed": 42}
```

**Protocol:** three consecutive runs per model via the Ollama HTTP API. Median reported. First run of a session has cold prompt cache — only its `prompt_eval_rate` is meaningful; subsequent runs report inflated prompt rates from caching.

**Why the 300-token cap exists:** the first uncapped run generated 3,756 tokens over 5m37s in a repetition loop. Without a cap, comparison is impossible. The cap is a disclosed measurement decision, applied uniformly, not a hidden tweak.

**Machine states:** *loaded* means normal working conditions with browser and apps open; *clean* means those quit. Both are measured and labelled.

**Reproducibility caveat that must appear in methodology:** a fixed seed does **not** guarantee identical output. Ollama's KV cache state across consecutive calls affects generation independently of the seed. Observed on both machines.

---

## Repository

`github.com/mhdghaim-cell/arabic-llm-bench` — public, MIT.

**Local path is `~/miqyas`.** This is the folder connected to GitHub. A scratch folder previously existed at `~/arabic-llm-bench` and has been renamed to `~/bench-scratch` to prevent confusion. Always work in `~/miqyas`.

Structure: the site (Arabic-path directories, `data/*.json`, `assets/`) plus `results/` for measurements and `results/raw/` for logs. `bench.sh` at root logs every run automatically with a timestamp. `bench_nothink.sh` is the same with `"think": false` for reasoning models.

Raw logs are prefixed `m4_` for Machine B; unprefixed files are Machine A.

---

## Week 1 — findings

**1. Apple Silicon speedup: 3.5–3.7x generation, 3.5–9.6x prompt processing.**
Consistent across all three shared models. Prompt processing gains more because it is compute-bound and parallelisable; generation is memory-bandwidth-bound.

**2. Foreign-script contamination — five source languages.**
Thai (U+0E15), Cyrillic, Vietnamese (U+1EED), German, English. Appeared on both machines, both runtime versions, both macOS versions — so it is a property of the models, not hardware or runtime. `xйление` and `xửление` are the same failure with a different character substituted in one slot, which indicates a repeated token-assembly failure rather than random noise. Unicode verification files are in `results/raw/`.

**3. The reasoning tax — controlled result.**
Both qwen3 models on Machine B spent their entire generation budget reasoning **in English** about how to write an Arabic letter. Re-running with `"think": false` changed nothing about throughput but changed everything about output:

| qwen3:8b | think on | think off |
|---|---|---|
| Speed | 19.48 tok/s | 19.40 tok/s |
| Arabic output | one salutation | complete 4-sentence letter |
| Contamination | — | none |
| P5 score | 1/5 | **5/5** |

The best Arabic output of the entire week came from disabling a model's default behaviour. This compounds the token-tax thesis: Arabic users pay more per unit of meaning *and* pay again for English reasoning they never see.

**4. "Bigger is worse" was an artifact — retracted internally before publication.**
The apparent inversion (larger model producing worse Arabic) was caused entirely by the reasoning tax consuming a fixed budget. With reasoning off, 8B (5/5) clearly beats 1.7B (2/5). Scale helps; the default configuration hides it.

**5. Background applications cost 5–22% of throughput on 8 GB.** See correction below.

**6. Speed and usefulness ran in opposite directions** on Machine A: the fastest model failed the task, the slowest was the only one to terminate naturally.

---

## ⚠️ OPEN: published correction owed

**Published on X and LinkedIn on 2026-08-18:** *"closing background applications made the model 29% faster (10.00 → 12.87 tok/s)."*

**That figure is overstated.** It came from one model in one session. Re-running all three models in clean state gives:

| Model | Loaded | Clean | Effect |
|---|---|---|---|
| llama3.2:1b | 17.29 | 20.61 | +19% |
| qwen3:1.7b | 18.47 | 19.39 | +5% |
| llama3.2:3b | 10.00 | 12.18 | +22% |

**Corrected claim: 5–22%, varying by model.**

Two compounding errors: generalising from a single model, and ignoring session variance — the same model in the same clean state measured 12.87 one day and 12.18 the next, a 5% spread that is the same order as the smallest observed effect.

**Decision taken:** publish this as a dedicated section inside the Week 1 Sunday thread rather than as a standalone post or a quiet edit. State the original number, the corrected range, and both reasons it was wrong. This is Rule 4 in action and is stronger content than the original claim.

---

## Publishing

**Cadence:** Sunday 08:00 GST main thread (reports the *previous* week's work), Tuesday 20:00 short post, Thursday 13:00 short post. Daily: reply to everyone, first 48 hours especially.

**X** — Arabic, threaded, images carry the numbers.
**LinkedIn** — English hook then Arabic body, single block, one image, drives traffic to X for detail. Posted a few hours *after* X so the thread is live when people click. Never edit a LinkedIn post in the first hour; it suppresses reach.

**Language discipline:** MSA in the body, dialect in replies. One Arabic term per concept, identical every time — see the glossary. English term in parentheses on first use per thread.

**Design system for images:** ink `#12161C`, paper `#FAF9F6`, rule `#D8D5CE`, signal red `#B8342A`, verify green `#1B5E4A`, dim `#6E7178`. IBM Plex Sans Arabic for text, IBM Plex Mono with tabular figures for all numbers. **Signal red appears only on measured values** — never buttons, headings, or decoration. Every image carries the measurement strip (hardware · model · quantization · date) and the URL burned in, because images get screenshotted out of context.

Already posted: intro post (X and LinkedIn), Week 1 results post (X and LinkedIn).

---

## Outstanding

- [ ] **Publish the 29% correction** in the Sunday thread
- [ ] LM Studio screenshots on Machine B — needs RealVNC; Apple Screen Sharing rejects the host. Required for Week 3 ecosystem post and glossary UI images.
- [ ] P1, P2, P3, P4, P6, P7 quality runs on both machines (only P5 has been run)
- [ ] CPU thermal throttling test on Machine A — ten consecutive runs, watch for decline
- [ ] Determine whether the qwen3 thinking-mode difference between machines is version-driven or template-driven

---

## What comes next

**Week 2 — quantization.** One model at Q4_K_M, Q5_K_M, Q8_0, and F16. Note: build the ladder on a **1B model**, not a 7B. F16 of a 1B is ~2.5 GB and fits in 8 GB, so Machine A can run the true unquantized baseline — something a 16 GB machine testing a 7B cannot. The constraint produces the cleaner experiment; say so rather than apologising for the hardware.

**Week 3 — ecosystem map.** Synthesis week, so it needs an original element: comparative setup friction timings, plus the compatibility audit (LM Studio has no Intel build; Open WebUI needs Docker which is impractical at 8 GB; vLLM needs CUDA so no Mac at all). That audit is original reporting no M-series owner can write.

**Week 4 — the Arabic token tax.** The flagship. Pure tokenizer math, no inference, hardware-independent. 40 passages across MSA and three dialects plus English translations, six tokenizers, tokens-per-word and the penalty ratio. **Save those ratios** — the Week 11 calculator depends on them.

**Week 5** — open the benchmark for contributions. **Week 11** — ship the calculator.

Full detail in `local-ai-playbook-v2.md`. Post skeletons in `local-ai-post-sheet.xlsx`.

---

## Companion documents

| File | Contains |
|---|---|
| `local-ai-playbook-v2.md` | Week-by-week install steps, tasks, and post drafts |
| `local-ai-post-sheet.xlsx` | 36 post skeletons with Arabic drafts, numbers tracker, glossary log, spend tracker |
| `three-assets-build-spec.md` | Site architecture, design system, viral mechanics, build order |
| `prompts_v0_clean.md` | The seven fixed evaluation prompts, repo-ready |
| `results/w1_timing.md` | All Week 1 measurements, in the repo |
