# Protocol v2 — Amendment 2 (2026-10-24, after the pilot, before any test run)

**What the pilot found.** On dev episode d03, Jais 3 3.7B ran the conversation correctly and booked the right slot, but saved the patient's name **ريم** as **"Rima"**. The scorer only accepted the Arabic spelling and marked it a failure. A clinic would accept "Rima" for ريم, so this was a scorer error, not a model error. It would have penalised any model that transliterates names, on most test episodes.

**Change.** `scripts/score_v2.py` now also accepts a booked name whose consonant skeleton matches the patient's name across scripts (ريم = Rima = Reem; محمد = Mohammed; عبدالله = Abdullah). Generic placeholders still fail ("العميل", "Customer", empty). `scripts/test_v2.py` gained 23 name checks (18 must match, 5 must not).

**What did not change.** Episodes, accepted end states, critical failures, prompt, tools, sampling, bar and hypotheses are identical to `9a83bfe`. The fix is model-agnostic and was found on dev episodes only; no test episode has been run.

**The other 9 pilot failures** (all Qwen3) were reviewed conversation by conversation and are genuine model behaviour: wrong weekday mapping, asking for a phone number instead of calling `list_my_appointments`, saying "I'll transfer you" without calling the handoff tool, claiming a day had no slots without checking, booking under the placeholder name "العميل". The harness handled every one correctly; no other change was needed.

Self-tests after the change: oracle 100% on 54 episodes × 3 arms, all negative controls caught, all name checks pass.
