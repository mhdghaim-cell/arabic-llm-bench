# Protocol v2 — Amendment 3 (2026-10-25): laptop speed validation run

**What happened.** The first attempt at the laptop validation (§8, Jais 3 3.7B, tool arm, low effort, 10 test episodes) stalled on its first conversation (t02): the model's first reply did not stop. The server log shows 2,612 tokens generated at ~1.9 tokens/s before the 30-minute request limit cut it off. On the GPU, low-effort replies had a median of ~35 tokens and no length-cap hits; the laptop's different arithmetic led this one conversation down a different path.

**Change (laptop validation only).** Replies are capped at 1,024 tokens instead of 8,192 (`--n-predict 1024` in `scripts/run_air_v2.sh validate`). This run exists only to check that the speed model (§8) predicts measured time from token counts; a call that hits the cap still has measured time and token counts, so it remains a valid data point. The server is also started with `-ngl 0` (CPU only), matching the llama-bench measurement.

**Unchanged.** All GPU results, episodes, scoring, bars and hypotheses. The laptop's own success rate in this run is not part of any published claim.
