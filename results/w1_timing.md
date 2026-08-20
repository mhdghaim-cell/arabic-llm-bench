# w1_timing — Week 1 timing and quality runs

**مقياس** · Machine A (MacBook Air, Intel) and Machine B (Mac mini M4, rented) · 2026-08-17 to 2026-08-19

---

## Machine A — specification

| Field | Value |
|---|---|
| Model | MacBook Air (Retina, 13-inch, 2020) |
| CPU | 1.2 GHz Quad-Core Intel Core i7 (Ice Lake, 4C/8T) |
| GPU | Intel Iris Plus, 1536 MB shared — unused, CPU-only inference |
| RAM | 8 GB LPDDR4X 3733 MHz |
| Disk free | 122 GB of 233 GB |
| OS | macOS Sequoia 15.7.7 |
| Base clock | 1.2 GHz — low-power chassis, sustained clocks limited by thermals |
| Runtime | Ollama 0.32.11, CPU backend |

---

## Method

Timing prompt is **P5** (formal writing) for every run. All figures below come from P5 and only P5.

Request parameters, identical across all models:

```json
{"num_predict": 300, "temperature": 0.7, "seed": 42}
```

Three consecutive runs per model via the local Ollama HTTP API. Median reported. The 300-token cap is a measurement decision, applied uniformly, and is disclosed rather than hidden — it was introduced after run 0 (below) showed unbounded generation making comparison impossible.

Two machine states were measured:

- **Loaded** — normal working conditions: Claude desktop (~3 GB across five processes), Creative Cloud, Notes, Spotlight, Mail active.
- **Clean** — those applications quit.

---

## Run 0 — uncapped exploratory run (llama3.2:1b, loaded)

Run before the token cap was introduced. Retained because the failure is the finding.

| Metric | Value |
|---|---|
| Total duration | 5m 37.19s |
| Load duration | 5.04s |
| Prompt eval | 93 tokens @ 64.75 tok/s |
| Generation | **3,756 tokens** @ 11.36 tok/s |

**Requested:** four sentences. **Produced:** roughly fifteen repetitions of the same paragraph over five and a half minutes.

Failure modes observed:
- **Repetition loop** — same paragraph cycled until manually bounded.
- **Code-switching** — `managerial`, `needness`, `faster` emitted inside Arabic text.
- **Non-words** — `تeleratime` (Arabic + English fused).
- **Script corruption** — `خوADMAMES الJHATHEM`, degrading further as the loop continued.

---

## Loaded state — all three models

| Model | Run 1 | Run 2 | Run 3 | **Median** | Prompt (cold) | Tokens | Stopped |
|---|---|---|---|---|---|---|---|
| llama3.2:1b | 19.59 | 17.29 | 16.31 | **17.29** | 80.66 | 291 | at cap |
| qwen3:1.7b | 20.86 | 18.47 | 16.99 | **18.47** | 87.25 | 300 | at cap |
| llama3.2:3b | 10.81 | 10.00 | 9.16 | **10.00** | 33.49 | 182 | naturally |

All rates in tokens/second.

**Prompt-rate caching artifact:** runs 2 and 3 report inflated prompt eval rates (2,471 / 2,464 tok/s on the 1B; 2,375 / 2,248 on qwen; 1,146 / 1,113 on the 3B) because Ollama caches the prompt across consecutive identical calls. Only the run-1 cold figure is meaningful.

---

## Clean state — all three models (2026-08-19)

Re-run of every model in clean state, with automatic logging, after the initial session recorded only `llama3.2:1b` to file. This closes the raw-log gap and provides a consistent clean-state baseline for cross-machine comparison.

| Model | Run 1 | Run 2 | Run 3 | **Median** | Prompt (cold) | Tokens |
|---|---|---|---|---|---|---|
| llama3.2:1b | 21.57 | 20.61 | 18.50 | **20.61** | 68.54 | 291 (capped) |
| qwen3:1.7b | 19.92 | 19.39 | 17.75 | **19.39** | 90.89 | 300 (capped) |
| llama3.2:3b | 12.55 | 11.60 | 12.18 | **12.18** | 45.94 | 182 (natural) |

---

## ⚠️ CORRECTION REQUIRED — the 29% figure was published and is wrong

**Published on X and LinkedIn, 2026-08-18:** "closing background applications made the model 29% faster (10.00 → 12.87 tok/s)."

**Status: overstated.** That figure came from a single model measured in a single session. Re-running all three models in clean state on 2026-08-19 produces a materially different picture.

| Model | Loaded | Clean | Effect |
|---|---|---|---|
| llama3.2:1b | 17.29 | 20.61 | **+19%** |
| qwen3:1.7b | 18.47 | 19.39 | **+5%** |
| llama3.2:3b | 10.00 | 12.18 | **+22%** |

**Corrected claim: background applications cost 5–22% of inference throughput on an 8 GB machine, varying by model.**

Two compounding sources of error in the original figure:

1. **Single-model generalisation.** `llama3.2:3b` showed the largest effect; `qwen3:1.7b` showed roughly a quarter of it. Reporting one model's result as a general number was unjustified.
2. **Session variance.** The same model in the same clean state measured 12.87 on 2026-08-18 and 12.18 on 2026-08-19 — a 5% spread between sessions on an identical configuration. That variance is of the same order as the smallest observed effect, which means single-session measurements on this hardware cannot support tight claims.

**Action:** publish the correction in the Week 1 Sunday thread as a dedicated section, not as a quiet edit. State the original number, the corrected range, and both reasons it was wrong.

---

## Quality — P5 (formal writing, 4 sentences, data sovereignty argument)

| Model | Score | Notes |
|---|---|---|
| llama3.2:1b | **1 / 5** | Repetition loop; script corruption including a Thai character (`البตENTIALية`); code-switching; never produced a letter. |
| qwen3:1.7b | **3 / 5** | Run 1 produced a correctly formed letter with subject line and salutation, no corruption. Runs 2–3 diverged and looped on `الموضوع`. |
| llama3.2:3b | **4 / 5** | Coherent formal letter, correct register, data sovereignty argument present (privacy, no external connection). Unrequested preamble `هذه رسالة رسمية:`. One malformed phrase: `يقلل من احتياطية البيانات`. |

### Headline observation

Speed and usefulness ran in opposite directions. The fastest model (qwen3:1.7b, 18.47 tok/s) failed the task; the slowest (llama3.2:3b, 12.87 tok/s clean) was the only one to complete it, and the only one to stop generating naturally rather than hitting the cap.

---

## Reproducibility caveat — seed is insufficient

A fixed seed (42) did **not** guarantee identical output. Observed:

- **llama3.2:1b** — all three runs identical.
- **qwen3:1.7b** — run 1 differed from runs 2–3.
- **llama3.2:3b, clean** — run 1 produced 116 tokens and a different letter, closing with the template artifact `ال Respect,` and `[أسمك]`. Runs 2–3 produced 182 tokens matching the earlier loaded-state output exactly.

Ollama's KV cache state across consecutive calls affects generation independently of the seed. Any reproduction attempt must account for cache state, not only seed.

---

## Machine B — specification

| Field | Value |
|---|---|
| Model | Mac mini (rented, Macly) |
| CPU | Apple M4 |
| RAM | 16 GB unified |
| OS | macOS 26.6.1 |
| Runtime | Ollama 0.32.14, Metal backend |
| Cost | $14.99 / day |

**Uncontrolled variables, disclosed:** Machine B runs a different macOS version (26.6.1 vs 15.7.7) and a different Ollama version than Machine A. Model IDs were verified identical across both machines (`baf6a787fdff`, `8f68893c685c`, `a80c4f17acd5`), so the weights are the same; the runtime and OS are not.

---

## Machine B — results

| Model | Run 1 | Run 2 | Run 3 | **Median** | Prompt (cold) | Tokens | Stopped |
|---|---|---|---|---|---|---|---|
| llama3.2:1b | 70.82 | 71.16 | 71.13 | **71.13** | 660.23 | 149 | naturally |
| qwen3:1.7b | 72.01 | 72.84 | 72.66 | **72.66** | 322.34 | 300 | at cap |
| llama3.2:3b | 44.38 | 44.71 | 44.98 | **44.71** | 306.65 | 204 | naturally |
| qwen3:8b | 19.46 | 19.48 | 19.52 | **19.48** | 143.94 | 300 | at cap |

All rates in tokens/second. Run-to-run spread under 1% on every model, versus roughly 20% on Machine A — Metal acceleration is not only faster but markedly more consistent than a thermally-constrained fanless Intel chassis.

---

## Cross-machine comparison

Machine A figures are clean-state medians from 2026-08-19; Machine B figures are from 2026-08-19. Both machines measured with the same script, prompt, parameters, and three-run protocol.

| Model | Machine A | Machine B | Generation ratio | Prompt ratio |
|---|---|---|---|---|
| llama3.2:1b | 20.61 | 71.13 | **3.5x** | 9.6x |
| qwen3:1.7b | 19.39 | 72.66 | **3.7x** | 3.5x |
| llama3.2:3b | 12.18 | 44.71 | **3.7x** | 6.7x |
| qwen3:8b | — (does not fit) | 19.48 | — | — |

Generation speedup is consistent at roughly **3.5–3.7x** across all three models. Prompt-processing speedup is larger and more variable (3.5–9.6x), reflecting that prompt processing is compute-bound and parallelisable — the workload a GPU is built for — while generation is bound by memory bandwidth.

**Note on qwen3 comparability:** on Machine B, qwen3 engaged reasoning mode and returned an empty `response` field with content in `thinking`. On Machine A it produced Arabic prose directly. Ollama versions differ (0.32.11 vs 0.32.14), though the gap is small enough that a changed default or template handling is a likelier explanation than the version itself. Speed figures remain valid as throughput measurements; quality figures for this model family are not directly comparable across machines.

---

## Finding — the reasoning tax on Arabic

Both qwen3 models on Machine B spent their entire generation budget reasoning **in English** about how to write an Arabic letter.

**qwen3:1.7b** — 300 tokens, all in `thinking`, in English. `response` field empty. Zero Arabic produced.

**qwen3:8b** — approximately 230 tokens of English reasoning, then a salutation and a truncated repeat before hitting the cap. Roughly **77% of the budget consumed by English text the user never sees.**

This compounds the Arabic token penalty rather than merely sitting alongside it. An Arabic user of a reasoning model pays twice: once because Arabic consumes more tokens per unit of meaning, and again because the model's reasoning about the Arabic task is conducted in English and billed against the same budget.

The largest model on the faster machine produced the least usable Arabic of the four.

---

## Controlled comparison — the reasoning tax isolated

Both qwen3 models were re-run on Machine B with `"think": false`. Same model, same machine, same prompt, same seed, three runs each. One variable.

### qwen3:1.7b

| | Thinking on | Thinking off |
|---|---|---|
| Median eval rate | 72.66 tok/s | 72.76 tok/s |
| Tokens generated | 300 | 286 |
| Stop reason | `length` (hit cap) | `stop` (natural) |
| Arabic produced | **none** | full letter |
| P5 score | 0 / 5 | 2 / 5 |

### qwen3:8b

| | Thinking on | Thinking off |
|---|---|---|
| Median eval rate | 19.48 tok/s | 19.40 tok/s |
| Tokens generated | 300 | 121 |
| Stop reason | `length` (hit cap) | `stop` (natural) |
| Arabic produced | salutation only | **complete 4-sentence letter** |
| Contamination | — | **none** |
| P5 score | 1 / 5 | **5 / 5** |

Throughput is unchanged in both cases. Disabling reasoning did not make either model faster — it changed **where the tokens landed**. With reasoning on, the budget was consumed by English deliberation. With reasoning off, the same budget produced Arabic and the models terminated on their own.

`qwen3:8b` with reasoning disabled produced the best Arabic output recorded across both machines and all models: four sentences as instructed, correct formal register, `سيادة البيانات` spelled correctly, proper salutation and closing, and no foreign-script contamination of any kind.

**The best result of the week came from turning off a model's default behaviour.**

---

## Correction — "bigger is worse" was an artifact

An earlier reading of the thinking-enabled data suggested that larger models produced worse Arabic. The `think: false` runs disprove this.

| Model | Thinking on | Thinking off |
|---|---|---|
| qwen3:1.7b | 0 / 5 | 2 / 5 |
| qwen3:8b | 1 / 5 | **5 / 5** |

With reasoning disabled, the larger model is clearly better. The apparent inversion was caused entirely by the reasoning tax consuming a fixed token budget — the 8B spends more tokens deliberating, so under a cap it has proportionally less left for output. Scale helps; the default configuration hides it.

Speed still declines with size (72.76 → 19.40 tok/s), but quality no longer moves against it.

---

## Contamination artifacts — five source languages

Foreign-script contamination appeared on both machines, across two runtime versions and two macOS versions. This rules out hardware and runtime as the cause; it is a property of the models.

| Model | Machine | Artifact | Composition | Unicode verified |
|---|---|---|---|---|
| llama3.2:1b | A | `البตENTIALية` | Arabic + **Thai** + Latin + Arabic | U+0E15 THAI CHARACTER TO TAO |
| llama3.2:1b | A | `xйление` | Latin + 6 × **Cyrillic** | U+0439 CYRILLIC SHORT I |
| llama3.2:1b | A | `xửление` | Latin + **Vietnamese** + 5 × Cyrillic | U+1EED LATIN U WITH HORN AND HOOK |
| llama3.2:1b | B | `verbessاء` | **German** stem + Arabic suffix | — |
| llama3.2:1b | B | `accuracy` | **English**, mid-Arabic-sentence | — |
| llama3.2:3b | B | `Confidentiality` و`Anonymity` | **English**, mid-Arabic-sentence | — |

**Five source languages: Thai, Cyrillic, Vietnamese, German, English.**

The Cyrillic and Vietnamese artifacts are the same failure with different fillers. Both are `x_ление`-shaped, with a single character substituted in the second position — `й` in one run, `ử` in another. The model is repeatedly reaching for a similar token sequence and filling one slot with whatever is available, rather than producing random noise.

`llama3.2:3b` used `Confidentiality` and `Anonymity` in Latin while correctly using السرية in the same sentence, so the Arabic term was available to it and was not selected.

---

## Outstanding

- [ ] **Publish the 29% correction in the Sunday thread** — see the flagged section above
- [ ] LM Studio screenshots on Machine B (requires VNC; Apple Screen Sharing rejects the host)
- [ ] P1, P2, P3, P4, P6, P7 quality runs on both machines
- [ ] Log CPU temperature / clock throttling across a long run (Machine A)
- [ ] Investigate whether the qwen3 thinking-mode difference is version-driven or template-driven

---

## Raw artifacts to retain

Full generations for every run above are required for the receipts links. Save terminal output verbatim to `results/raw/` before overwriting anything.
