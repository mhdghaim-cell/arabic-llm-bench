# Quick Trial qt-01 · ALLaM 7B on the clinic front desk

**Quick Trial · exploratory · numbers only, no verdict** (Job Trial Standard v1.1). October 2026.

Can `ALLaM-AI/ALLaM-7B-Instruct-preview` (the open 7B preview, now also hosted as `humain-ai/ALLaM-7B-Instruct-preview`; not ALLaM 34B) run a dental clinic's WhatsApp front desk? Same job and public test set as Job Trial #1: 42 scenarios × 3 runs, plus 2 extra runs on each safety scenario (144 conversations).

| | ALLaM 7B | Qwen3 4B, no thinking (reference, Job Trial #1) |
|---|---|---|
| Fully correct conversations | **8.7%** (11/126, 95% CI 3.2–16.7%) | 27.8% |
| Correct in all 3 runs | 4.8% | 16.7% |
| Emergencies handed to staff in time | 1/25 | 20/25 |
| Complaints + medical questions handed over | 0/20 | 5/20 |
| Wait per message, RTX 4090 (median / p90) | 0.6 s / 1.0 s | — |

**Post-hoc observation (not pre-registered):** in 21 of 144 conversations, including 12 of 25 emergencies, the model gave the patient a phone number that is not in the clinic's instructions, instead of handing over. Phone-like numbers are redacted in the published transcripts (`scripts/redact_phones.py`); scores were recomputed after redaction and are identical.

## Setup
- Model: Q4_K_M, converted with llama.cpp `8642541`; sha256 in `results/qt01/model_provenance.txt`. Licence: Apache-2.0.
- Sampling from the model card: temperature 0.6, top_k 50, top_p 0.95. 4,096-token window (no overflows occurred).
- Tool arm (date tool, no calendar in the prompt). The model card does not mention tool calling and the chat template has no tool syntax, so it ran through a **prompted-JSON adapter** (`scripts/run_v2.py --mode prompted`): tools and a two-form JSON reply format in the system prompt, replies constrained to that JSON by grammar, tool results returned as a user message. Job Trial #1 models used their native tool syntax; this difference may explain part of the gap.
- Public test set only; the private held-out set is not written yet. Laptop (floor) wait was not measured in this Quick Trial.

## Files
- Pre-registration and amendments: [`trials/qt-01-allam-7b-clinic.yaml`](../../trials/qt-01-allam-7b-clinic.yaml). Amendment 2 records why the adapter changed after the DEV pilot (llama.cpp's built-in tool calling dropped the tools for this template) and before any test run.
- Raw conversations and scores: [`results/qt01/`](../../results/qt01/) (test run plus both DEV pilots).
- Numbers: [`results.json`](results.json), built by [`make_results.py`](make_results.py).
- Scorecard: `scorecard_x.png` (source `scorecard_x_source.html`).
