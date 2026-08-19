# w1_timing — Week 1 timing and quality runs

**مقياس** · Machine A (local) · 2026-08-17

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
| Runtime | Ollama, CPU backend |

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

## Clean state — llama3.2:3b control

| Run | Eval rate | Prompt rate | Tokens |
|---|---|---|---|
| 1 | 14.36 | 53.38 | 116 |
| 2 | **12.87** | 1583.11 | 182 |
| 3 | 12.56 | 75.03 | 182 |

**Median: 12.87 tok/s.**

### Finding — background applications cost 29% of inference speed

| State | Median | Swap used |
|---|---|---|
| Loaded | 10.00 tok/s | 2.48 GB |
| Clean | 12.87 tok/s | 657 MB |
| **Delta** | **+28.7%** | **−1.82 GB** |

Memory pressure remained green in both states, so no thrashing occurred and both datasets are valid. The difference is swap activity, not pressure. On an 8 GB machine, ordinary working applications consume roughly a third of available inference throughput — an effect invisible on higher-memory hardware.

### Memory snapshots

| Metric | Loaded | Clean |
|---|---|---|
| Memory used | 6.71 GB | 6.82 GB |
| Swap used | 2.48 GB | 657 MB |
| Cached files | 1.34 GB | 1.15 GB |
| App memory | 3.46 GB | 3.26 GB |
| Wired | 2.33 GB | 2.31 GB |
| Compressed | 871.9 MB | 1.22 GB |

`llama-server` held 2.53 GB in both states. In the loaded state, Claude desktop across five processes held approximately 3.0 GB — more than the model being benchmarked.

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

| Model | Machine A | Machine B | Generation ratio | Prompt ratio |
|---|---|---|---|---|
| llama3.2:1b | 17.29 | 71.13 | **4.1x** | 8.2x |
| qwen3:1.7b | 18.47 | 72.66 | **3.9x** | 3.7x |
| llama3.2:3b | 12.87 | 44.71 | **3.5x** | 5.7x |
| qwen3:8b | — (does not fit) | 19.48 | — | — |

**Note on qwen3 comparability:** on Machine B, qwen3 engaged reasoning mode and returned an empty `response` field with content in `thinking`. On Machine A it produced Arabic prose directly. The two machines are therefore not measuring the same behaviour for this model family, most likely due to the Ollama version difference. The speed figures remain valid as throughput measurements; the quality figures are not comparable.

---

## Finding — the reasoning tax on Arabic

Both qwen3 models on Machine B spent their entire generation budget reasoning **in English** about how to write an Arabic letter.

**qwen3:1.7b** — 300 tokens, all in `thinking`, in English. `response` field empty. Zero Arabic produced.

**qwen3:8b** — approximately 230 tokens of English reasoning, then a salutation and a truncated repeat before hitting the cap. Roughly **77% of the budget consumed by English text the user never sees.**

This compounds the Arabic token penalty rather than merely sitting alongside it. An Arabic user of a reasoning model pays twice: once because Arabic consumes more tokens per unit of meaning, and again because the model's reasoning about the Arabic task is conducted in English and billed against the same budget.

The largest model on the faster machine produced the least usable Arabic of the four.

---

## Controlled comparison — the reasoning tax isolated

`qwen3:1.7b` was re-run on Machine B with `"think": false`. Same model, same machine, same prompt, same seed. One variable.

| | Thinking on | Thinking off |
|---|---|---|
| Eval rate | 72.66 tok/s | 72.76 tok/s |
| Tokens generated | 300 | 286 |
| Stop reason | `length` (hit cap) | `stop` (natural) |
| Arabic produced | **none** | full letter |
| P5 score | 0 / 5 | 2 / 5 |

Throughput is unchanged. Disabling reasoning did not make the model faster — it changed **where the tokens landed**. With reasoning on, the entire budget was consumed by English deliberation and the model never began writing. With reasoning off, the same budget produced a complete Arabic letter and terminated on its own.

This isolates the reasoning tax as a controlled result rather than an inference from observation.

**Quality of the think-disabled output (2/5):** coherent formal Arabic and the data-sovereignty argument is present, but the model restates the prompt before beginning, produces roughly seven sentences against a four-sentence instruction, adds an unrequested apologetic clause (`أعذر أي تأثيرات`), leaves template placeholders (`[اسمك]`, `[الموقع]`), and contains a grammatical error in the key phrase — `السيادة البيانات` where `سيادة البيانات` is correct. Better than producing nothing; worse than `llama3.2:3b`.

---

## Finding — bigger is slower and, here, worse

On Machine B, ranked by speed: qwen3:1.7b (72.66) > llama3.2:1b (71.13) > llama3.2:3b (44.71) > qwen3:8b (19.48).

Ranked by usable Arabic output: llama3.2:3b (complete letter) > llama3.2:1b (complete but contaminated) > qwen3:8b (salutation only) > qwen3:1.7b (nothing).

`qwen3:8b` on Apple Silicon (19.48 tok/s) is only marginally faster than `llama3.2:1b` on a 2020 Intel Air (17.29 tok/s) — and produced far less Arabic.

---

## Contamination artifacts — Machine B

Foreign-script contamination persisted on Apple Silicon, confirming it is a property of the models rather than of the hardware or runtime.

| Model | Machine | Artifact | Composition |
|---|---|---|---|
| llama3.2:1b | A | `البตENTIALية` | Arabic + Thai (U+0E15) + Latin + Arabic |
| llama3.2:1b | A | `xйление` | Latin + 6 × Cyrillic |
| llama3.2:1b | B | `verbessاء` | German stem + Arabic suffix |
| llama3.2:1b | B | `accuracy` | Latin, mid-Arabic-sentence |
| llama3.2:3b | B | `Confidentiality` و`Anonymity` | Latin, mid-Arabic-sentence |

`verbess` is the stem of the German *verbessern* (to improve). Notably, `llama3.2:3b` used `Confidentiality` and `Anonymity` in Latin while correctly using السرية in the same sentence — the Arabic term was available to it.

**Four distinct source languages observed** — Thai, Cyrillic, German, English — across two machines, two runtime versions, and two macOS versions.

---

## Outstanding

- [ ] Log CPU temperature / clock throttling across a long run (Machine A)
- [ ] Record Ollama version on Machine A to quantify the runtime variable
- [ ] P1, P2, P3, P4, P6, P7 quality runs on both machines
- [ ] Screenshot: memory pressure graph showing yellow (loaded) → green (clean) transition
- [ ] Screenshot: `البตENTIALية` corruption artifact

---

## Raw artifacts to retain

Full generations for every run above are required for the receipts links. Save terminal output verbatim to `results/raw/` before overwriting anything.
