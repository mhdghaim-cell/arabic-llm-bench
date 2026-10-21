# Protocol v2 — Amendment 1 (2026-10-24, before any test run)

Made after the pre-registration commit `9a83bfe` and before any model ran on the test episodes.

**Reporting additions only. Nothing that decides success or failure changed:** episodes, accepted end states, critical failures, prompt, tools, sampling, bar and hypotheses are identical to `9a83bfe`.

| Change | File | Why |
|---|---|---|
| The scorecard also reports compute seconds and generated tokens **per correctly completed conversation**, with failed conversations counted in the numerator (`MIQYAS_GPU_USD_H` optionally converts to dollars) | `scripts/score_v2.py` | A buyer pays for every attempt, not only the ones that work |
| `run_gpu_v2.sh setup` records the SHA-256 of every model file in `results/frontdesk_v2/models_sha256.txt` | `scripts/run_gpu_v2.sh` | Lets anyone confirm they are reproducing with the exact same files |

Self-tests rerun after the change: oracle 100% on 54 episodes × 3 arms, all negative controls caught.
