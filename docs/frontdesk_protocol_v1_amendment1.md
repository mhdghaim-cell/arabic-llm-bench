# Protocol v1 — Amendment 1 (2026-10-19, before any of the affected runs)

**What changed.** The four "Mac mini M4" configurations in protocol v1 move to a rented **Linux machine with an NVIDIA GPU (≥ 16 GB; the exact model is recorded in the run log)**, running the same llama.cpp server (built with CUDA), the same models, quantisations, prompt v1, cases v1, sampling, seeds, reps and scorer.

**Why.** No M4 could be rented: Macly stopped individual rentals and Scaleway had no M4 stock on 2026-10-19. The GPU model is whichever suitable card was available; it affects speed only, not correctness.

**What this does and does not affect.**
- **Unaffected:** every correctness measure — correct action, emergency handovers, premature bookings, reasoning language, dialect. These depend on the model and its settings, not on the hardware. The ceiling check (Jais 3 7B must reach ≥ 90% correct action) is unchanged.
- **Affected:** wait times. A datacenter GPU is far faster than any machine a small clinic would own, so GPU timings are reported only as "the model's best case", never compared with the Intel Air or used for the buyer's speed bar.
- **Dropped:** the "same 0.9B on a modest Apple Silicon Mac" speed comparison. If an M4 becomes available later, it can be added as a separate run.
- **Added:** Jais 3 0.9B Q8 on the GPU. Same model and seeds as the Air run, so it doubles as a cross-hardware check: correctness should be close; only speed should differ.

Labels: `jais3-7b-q4-gpu-v1`, `jais3-3.7b-q4-gpu-v1`, `qwen3-4b-q4-gpu-v1`, `jais3-0.9b-q8-gpu-v1`.
