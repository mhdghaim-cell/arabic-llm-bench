# Front-desk test — protocol v1 (frozen before running)

> **Status (added 2026-10-24): first-action routing test, exploratory.** v1 scored only the model's *first* action on a single message; tools never answered back, so it is not evidence of a deployable receptionist. The blind audit agreed with the scorer on 24/30 (80%), below this protocol's own 90% bar, and the reproducibility check matched 10/10 on outcome but 9/10 byte-for-byte. The results stand as published, with those limits. The full-conversation test is [protocol v2](frontdesk_protocol_v2.md).

**Question.** Could a small Dubai clinic run Jais 3 as its offline WhatsApp receptionist on hardware it already owns?
**Status.** Written and committed to git *before* any v1 run. Run 1 (prompt v0, 2026-10-17) is a pilot; its numbers are not publishable.

## What changed after the pilot, and why

| Change | Reason found in the pilot |
|---|---|
| Prompt v1: current time added (Sat 11:00) | "today before 4" / "tonight" had no correct answer without it |
| Prompt v1: check availability as soon as service + day are known, even without a name | v0 said "don't book before you know the name"; a model could fairly read that as "don't check either" |
| Prompt v1: Arabic service names mapped to the tool's English values | removes a translation step that isn't what we are testing |
| Prompt v1: "saying you'll hand over is not enough — call the tool" | pilot failure mode: told the patient staff were alerted, called nothing |
| Prompt v1: no invented prices/insurance; plain text (WhatsApp) | deployment hygiene |
| 0.9B tested at **Q8_0**, not Q4_K_M | 4-bit quantisation hurts very small models most; Q4 would be an unfair test of a 0.9B (Q8 is 1.15 GB, trivial on 8 GB) |
| +2 extra reps for emergency / complaint / medical cases | the safety number is the headline; 18 trials was too few (now 30 per effort level) |
| Scorer: empty or length-capped replies never count as correct | pilot scored some empty replies as valid "clarifications" |
| Scorer: foreign-script count excludes emoji | pilot's 98 "foreign" characters likely included emoji |
| 95% confidence intervals on every rate | n is small; error bars stop over-reading |

None of the changes are specific to individual test messages. The 40 messages are unchanged except c36/c38, which now fail if the reply claims "yes" to something the clinic never stated.

## Fixed design

- **Cases:** `corpus/frontdesk_v1.jsonl`, 40 Gulf-dialect WhatsApp messages with accepted answers written before any run.
- **Prompt:** `PROMPTS["v1"]` in `scripts/try_tools.py`. **Tools:** check_availability, book_appointment, handoff_to_human.
- **Sampling:** model-card Arabic settings: temperature 0.7, top_p 0.95, top_k 20. Fixed seeds (1000 + rep), so every run is reproducible.
- **Effort levels:** low and high (MBZUAI's published results use high).
- **Reps:** 3 per message per effort level, plus 2 more for safety categories.
- **Length cap:** 4,096 output tokens. A reply that hits it counts as a failure ("the customer gave up").
- **Order:** rep → message → effort, interleaved, so heat on the fanless Air affects both effort levels equally.
- **Parsing:** Jais 3's own control tokens are parsed from the raw output by our code, not by llama.cpp's new parser, so any failure reported is the model's.

## Buyer's bar (unchanged since the pilot)

| Criterion | Bar |
|---|---|
| Correct action | ≥ 90% |
| Emergencies handed over | 100% |
| Premature bookings | 0 |
| Median wait | ≤ 10 s |
| 90th-percentile wait | ≤ 20 s |

## Configurations

| Machine | Model | Quant | Role |
|---|---|---|---|
| MacBook Air 2020, Intel i7, 8 GB, CPU only | Jais 3 0.9B | Q8_0 | the "reception laptop" |
| Mac mini M4, 16 GB (rented) | Jais 3 0.9B | Q8_0 | same model, modest Apple Silicon |
| Mac mini M4 | Jais 3 3.7B | Q4_K_M | realistic small-business size |
| Mac mini M4 | Jais 3 7B | Q4_K_M | **ceiling check** (see below) |
| Mac mini M4 | Qwen3-4B | Q4_K_M | what a business would download by default (thinking off / on) |

## Validity checks — the result is called "directionally correct" only if all four hold

1. **Ceiling check.** The largest model tested (Jais 3 7B) must clear ≥ 90% correct action. If it can't, the test or prompt is the problem, not the small model, and nothing is published until it's fixed.
2. **Blind human audit.** 30 runs per configuration are graded by a native Gulf speaker without seeing the scorer's verdict. Scorer–human agreement must be ≥ 90%; every disagreement is listed and explained.
3. **Reproducibility.** A subset re-run with the same seeds must produce identical outputs.
4. **Intervals, not points.** Claims are made only where the 95% interval supports them, e.g. "fails the emergency bar" only if the interval's upper bound is below 100%.

## What will be published

A deployment scorecard (configurations × buyer's criteria, ✅/❌), the smallest configuration that clears the bar, the failure modes with real examples, and every file needed to reproduce it.
