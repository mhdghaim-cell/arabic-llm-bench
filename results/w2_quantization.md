# w2_quantization — Week 2 quantization ladder

**مقياس** · Machine A (MacBook Air 2020, Intel i7, 8 GB) · 2026-08-29

---

## What this week tested

One model, `Llama-3.2-1B-Instruct`, at four levels: Q4_K_M, Q5_K_M, Q8_0, and F16.

The ladder is built on a 1B model deliberately. F16 of a 1B is 2.30 GiB and fits in 8 GB, so the true unquantized baseline can be measured. A 16 GB machine testing a 7B cannot fit F16 and is therefore limited to comparing quantized against quantized, with no reference point. The memory constraint produces the cleaner experiment.

| Level | File size | Ollama tag |
|---|---|---|
| Q4_K_M | 763 MiB | `l1b-q4` |
| Q5_K_M | 862 MiB | `l1b-q5` |
| Q8_0 | 1.22 GiB | `l1b-q8` |
| F16 | 2.30 GiB | `l1b-f16` |

Weights from `bartowski/Llama-3.2-1B-Instruct-GGUF`. Not committed — see `results/w2/README.md` for the download commands.

---

## ⚠️ The thermal confound — read before the speed results

The first attempt at this week's measurements produced a ladder that could not be reproduced. Diagnosing why took longer than the measurement itself, and the diagnosis is the more useful finding.

### What happened

Running four models back to back with `llama-bench`, the same file measured differently depending on where it fell in the sequence.

`Llama-3.2-1B-Instruct-Q4_K_M.gguf`, generation (tg128), measured five times under different conditions:

| Condition | tg128 (tok/s) |
|---|---|
| Isolated, cool machine | **36.36 ± 1.67** |
| First in sequence, after a warmup run | 30.84 ± 0.74 |
| Second session, warm file cache | 27.53 ± 2.06 |
| Very first run of the session, cold cache | 18.33 ± 2.66 |
| Fourth in sequence, hot chassis | 16.43 ± 12.32 |

**A 2.2x spread on one file from thermal state alone.**

### Why it matters

The quantization effect this week is measured at 3.5x between F16 and Q4. The thermal artifact is 2.2x. The confound is of the same order as the signal being measured.

Two diagnostic details. Reversing the run order moved the degradation with the position, not with the model — Q4 measured 30.84 running first and 16.43 running last. And the standard deviation is the tell: a run that throttles mid-measurement produces a wide spread (±12.32) because the early repetitions are fast and the later ones are not.

One measurement was discarded entirely as invalid: Q8_0 pp512 at 28.34 ± 32.72, where the standard deviation exceeds the mean.

### The protocol that resulted

- One quantization level per session.
- At least 15 minutes idle between sessions.
- A discarded warmup run before each measured run.
- `-r 5` rather than `-r 3`.
- Machine in clean state throughout, per the Week 1 finding that background applications cost 5–22% of throughput.

`ladder.md` and `ladder_reversed.md` are retained in `results/w2/` as evidence for this section, **not as results.**

This applies to any fanless chassis. It is absent from published quantization comparisons because those are run on desktops with thermal headroom.

---

## Speed — isolated measurements

`llama-bench` build c1d0e7a00 (10621), BLAS backend, 4 threads, `-p 512 -n 128 -r 5`. Each level measured in its own session on a cool machine.

| Level | Size | pp512 (tok/s) | tg128 (tok/s) | Generation vs F16 |
|---|---|---|---|---|
| F16 | 2.30 GiB | 66.96 ± 4.30 | **10.25 ± 0.25** | baseline |
| Q8_0 | 1.22 GiB | 88.19 ± 7.31 | 22.40 ± 1.06 | 2.2x |
| Q5_K_M | 862 MiB | 80.13 ± 6.89 | 22.98 ± 0.87 | 2.2x |
| Q4_K_M | 763 MiB | 172.60 ± 12.77 | **36.36 ± 1.67** | **3.5x** |

### Three observations

**Quantization roughly doubles generation speed immediately.** Any quantized level runs at 2.2x F16 or better. This is the payoff, and quantifying it requires the unquantized baseline.

**Q5_K_M and Q8_0 are indistinguishable.** 22.98 against 22.40 tok/s, despite Q8_0 being 40% larger on disk. On this hardware Q5_K_M spends precision and buys no speed, which makes it the weakest of the three quantized options.

**Q4_K_M is a cliff, not a step.** 58% faster than either Q5 or Q8 on generation, and more than double on prompt processing. The ladder is not gradual — there is a discontinuity at Q4 and a plateau above it.

---

## Quality — five Arabic prompts at each level

Prompts P1 to P5 from `data/prompts.json`, run through the Ollama HTTP API at `num_predict: 500, temperature: 0.7, seed: 42`. Same isolation protocol between levels.

| Prompt | Tests | Q4_K_M | Q5_K_M | Q8_0 | F16 |
|---|---|---|---|---|---|
| P1 | regional facts | 1/5 | 1/5 | **2/5** | 1/5 |
| P2 | reasoning | 1/5 | 1/5 | 1/5 | 1/5 |
| P3 | instruction-following | 3/4 | **4/4** | 3/4 | 1/4 |
| P4 | Gulf dialect | 1/5 | 1/5 | 1/5 | 1/5 |
| P5 | formal writing | 1/5 | 2/5 | 2/5 | 1/5 |
| **Total** | | **7/24** | **9/24** | **9/24** | **5/24** |

### The result is negative, and that is the finding

**F16 — the unquantized baseline — scored lowest of the four.**

The hypothesis this week set out to test was that quantization damages Arabic output disproportionately, because quantization harms rare tokens and Arabic is underrepresented in training data. The data does not support it. The unquantized model performed worst, and carried more foreign-script contamination than any quantized level.

The likely explanation is capacity rather than compression: a 1B model does not have the parameters to handle these tasks in Arabic, and the failures observed are capacity failures rather than quantization artifacts. Quantization is not implicated because the same failures appear where no quantization has occurred.

**This does not settle the question.** One model, one size, five prompts, one scorer. The correct reading is that the effect is not detectable at 1B with this sample — not that it is absent at larger sizes. Week 8 re-runs this design on models where capacity is not the binding constraint.

### Q8_0 on P1

Q8_0 was the only level to answer **six emirates** at founding — the discriminator P1 was designed around, and one that `qwen3:8b` on Machine B also failed. It gave the wrong year (1961) and a circular answer on the Saudi question, so the score is 2/5, but the emirate count is a genuine hit.

At this sample size this is more likely noise than signal. Flagged rather than claimed.

---

## Foreign-script contamination by level

Contamination appeared at every level including F16.

| Level | Prompts affected | Artifacts |
|---|---|---|
| Q4_K_M | 4 / 5 | `ประสิทธิภาพ` ×2 (Thai, full word), `التأسيسของ`, `للคำputation`, `nghĩa` ×2 (Vietnamese), `sẽ`, `الميلadera` |
| Q5_K_M | 4 / 5 | `في Arabia`, `maintenant` (French), `raison` (French), `يسद्द` (**Devanagari** U+0926) |
| Q8_0 | 1 / 5 | `句话` (**Chinese**) |
| F16 | 4 / 5 | `2 tháng`, `việc`, `tôi` (Vietnamese), `المترipple`, `ประสิทธิภาพ` ×3, `ประสิทธividad` (Thai + Spanish) |

**The source languages shift by level** — Thai and Vietnamese at Q4, French and Devanagari at Q5, Chinese at Q8, Thai and Vietnamese again at F16. The pattern is not a monotonic increase with compression.

Two artifacts are worth noting individually. `ประสิทธividad` fuses a Thai stem with a Spanish suffix in a single token sequence. `يسد्द` substitutes Devanagari द for Arabic د — visually similar characters from unrelated scripts, which suggests the failure operates on glyph-adjacent representations rather than on semantics.

Combined with Week 1, the observed source languages now number nine: Thai, Cyrillic, Vietnamese, German, English, Russian, French, Devanagari, Chinese.

Since contamination appears at F16, it is a property of the model rather than of quantization.

---

## Known limitations

- One model at one parameter size. Findings may not generalise beyond 1B.
- Five prompts, single human scorer, no inter-rater reliability measure.
- Speed and quality measured on one machine. The thermal protocol has not been validated on other chassis.
- Quality scoring was done from a single generation per prompt per level. Given the Week 1 finding that a fixed seed does not guarantee identical output, repeated generations may score differently.

---

## Raw artifacts

Speed: `results/w2/{q4,q5,q8,f16}_isolated.md` — the reported measurements.
`results/w2/ladder.md` and `ladder_reversed.md` — the invalidated sequential runs, retained as evidence for the thermal section.
Quality: `results/raw/w2_*.json` — full API responses, one file per prompt per level.
